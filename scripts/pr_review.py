#!/usr/bin/env python3
"""OpenAI-based pull-request reviewer (advisory).

Runs inside the `PR Review` GitHub Actions workflow. Steps:
  1. Pull the PR's unified diff straight from the GitHub API (no git history needed).
  2. Ask an OpenAI model to review it as a senior engineer and emit a verdict +
     concrete merge / change suggestions.
  3. Post the review back as a single *sticky* PR comment (updated in place on each
     push, so the thread is not spammed).

This is advisory only — it never merges anything. A human still clicks "Merge".
A failure here must not block the PR, so any error is logged and the script exits 0.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Hidden marker so we can find-and-update our own comment instead of posting a new
# one every time the PR is updated.
MARKER = "<!-- openai-pr-reviewer -->"

# Diffs larger than this (characters) are truncated before being sent to the model.
# ~150k chars is well under gpt-4o-mini's context window and keeps cost bounded.
MAX_DIFF_CHARS = 150_000

API_ROOT = "https://api.github.com"


def env(name: str, required: bool = True, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        print(f"::error::missing required env var {name}")
        sys.exit(0)  # non-blocking
    return val or ""


def gh_request(
    path: str,
    token: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    accept: str = "application/vnd.github+json",
) -> str:
    url = path if path.startswith("http") else f"{API_ROOT}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


def fetch_diff(repo: str, pr: str, token: str) -> str:
    return gh_request(
        f"/repos/{repo}/pulls/{pr}",
        token,
        accept="application/vnd.github.v3.diff",
    )


def review_with_openai(diff: str, model: str, key: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=key)
    system = (
        "You are a senior software engineer reviewing a pull request for a "
        "Python project: a citation-aware investment-research assistant "
        "(FastAPI backend, Streamlit frontend, ChromaDB RAG, Redis cache, "
        "OpenAI synthesis). Review ONLY the diff provided.\n\n"
        "Respond in GitHub Markdown with EXACTLY this structure:\n"
        "1. A first line that is one of:\n"
        "   `**Verdict: ✅ Recommend merge**`\n"
        "   `**Verdict: ⚠️ Changes suggested**`\n"
        "   `**Verdict: ❌ Do not merge**`\n"
        "2. A 1-2 sentence summary of what the PR does.\n"
        "3. `### Suggestions` — a short bulleted list of concrete, actionable "
        "items (correctness bugs first, then tests, then style). Reference files/"
        "lines. If there is nothing to change, write 'None — looks good.'\n"
        "Be concise and specific. Do not invent issues. This is advisory; a human "
        "merges manually after CI checks are green."
    )
    user = f"Review this pull request diff:\n\n```diff\n{diff}\n```"
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


def upsert_comment(repo: str, pr: str, token: str, body: str) -> None:
    existing = json.loads(
        gh_request(f"/repos/{repo}/issues/{pr}/comments?per_page=100", token)
    )
    for c in existing:
        if MARKER in (c.get("body") or ""):
            gh_request(
                f"/repos/{repo}/issues/comments/{c['id']}",
                token,
                method="PATCH",
                data={"body": body},
            )
            print(f"updated existing review comment {c['id']}")
            return
    gh_request(
        f"/repos/{repo}/issues/{pr}/comments",
        token,
        method="POST",
        data={"body": body},
    )
    print("posted new review comment")


def main() -> None:
    token = env("GITHUB_TOKEN")
    openai_key = env("OPENAI_API_KEY")
    repo = env("GITHUB_REPOSITORY")
    pr = env("PR_NUMBER")
    model = env("OPENAI_REVIEW_MODEL", required=False, default="gpt-4o-mini")

    try:
        diff = fetch_diff(repo, pr, token)
    except urllib.error.HTTPError as e:
        print(f"::warning::could not fetch diff: {e}")
        return

    if not diff.strip():
        print("empty diff — nothing to review")
        return

    truncated = len(diff) > MAX_DIFF_CHARS
    if truncated:
        diff = diff[:MAX_DIFF_CHARS]

    try:
        review = review_with_openai(diff, model, openai_key)
    except Exception as e:  # noqa: BLE001 — advisory step must never block CI
        print(f"::warning::OpenAI review failed: {e}")
        return

    note = (
        "\n\n> ⚠️ Diff was truncated for review; very large changes may be "
        "only partially covered." if truncated else ""
    )
    body = (
        f"{MARKER}\n"
        f"## \U0001f916 OpenAI PR Review\n\n"
        f"{review}{note}\n\n"
        f"---\n"
        f"*Advisory review by `{model}`. CI gates the merge; this does not. "
        f"Merge manually once checks are green.*"
    )
    try:
        upsert_comment(repo, pr, token, body)
    except urllib.error.HTTPError as e:
        print(f"::warning::could not post comment: {e}")


if __name__ == "__main__":
    main()