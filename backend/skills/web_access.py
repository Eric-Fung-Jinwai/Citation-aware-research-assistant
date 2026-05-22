import os
from datetime import datetime, timedelta

import httpx

from backend.models.citation import CitationObject, SkillResult

NEWSAPI_BASE = "https://newsapi.org/v2"


async def fetch_news(ticker: str, company_name: str | None = None, days: int = 7) -> dict:
    api_key = os.getenv("NEWS_API_KEY")
    query = company_name or ticker
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{NEWSAPI_BASE}/everything",
                params={
                    "q": query,
                    "from": from_date,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 5,
                },
                # Key goes in a header, never the URL, so it can't leak into error/log strings
                headers={"X-Api-Key": api_key or ""},
            )
            resp.raise_for_status()
            payload = resp.json()
    except httpx.TimeoutException:
        return SkillResult(
            status="degraded",
            error="UNAVAILABLE — web-access timed out after 10s",
            source="web-access",
        ).model_dump()
    except httpx.HTTPStatusError as e:
        # Report the status code only — never echo the request URL or raw exception
        return SkillResult(
            status="degraded",
            error=f"UNAVAILABLE — NewsAPI returned HTTP {e.response.status_code}",
            source="web-access",
        ).model_dump()
    except Exception as e:
        return SkillResult(
            status="degraded",
            error=f"UNAVAILABLE — {type(e).__name__}",
            source="web-access",
        ).model_dump()

    articles = payload.get("articles", [])
    if not articles:
        return SkillResult(
            status="degraded",
            error=f"UNAVAILABLE — no news found for {query}",
            source="web-access",
        ).model_dump()

    news_items = []
    citations = []

    for article in articles[:5]:
        pub_date = (article.get("publishedAt") or "")[:10]
        source_name = article.get("source", {}).get("name") or "Unknown"
        title = article.get("title") or ""
        description = article.get("description") or ""
        url = article.get("url")

        news_items.append(
            {"title": title, "summary": description, "source": source_name, "url": url, "date": pub_date}
        )
        citations.append(
            CitationObject(
                claim=title,
                source_type="news",
                source_name=source_name,
                url=url,
                date=pub_date,
                excerpt=description[:200] if description else title[:200],
            )
        )

    return SkillResult(
        status="success",
        data={"ticker": ticker, "articles": news_items},
        citations=citations,
        source="web-access",
    ).model_dump()