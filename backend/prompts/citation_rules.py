CITATION_RULES = """CITATION RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:

You will receive a context bundle containing numbered evidence blocks.
Each block has a citation_index.

1. TAG EVERY CLAIM: Every factual statement in your report must end with
   [cite:N] where N is the citation_index of the supporting evidence block.

2. NO UNSUPPORTED CLAIMS: Do not state any fact that does not have a
   supporting evidence block. If you cannot tag it, do not write it.

3. MISSING SECTIONS: If evidence for a report section is marked UNAVAILABLE,
   write exactly: "Insufficient data available for this section."
   Do not infer, estimate, or fill the gap from your own knowledge.

4. MULTIPLE SOURCES: If a claim is supported by more than one evidence block,
   tag all of them: [cite:0][cite:1]

5. DO NOT MODIFY TAGS: Write citation tags exactly as [cite:N].
   Do not paraphrase, abbreviate, or reformat them.

Example of correct output:
  "NVIDIA revenue grew 122% year-over-year in Q4 2024 [cite:1], supported
   by a new cloud partnership announced last week [cite:0]. RSI above 70
   suggests near-term overbought conditions [cite:2]."

Example of incorrect output (do not do this):
  "NVIDIA has been performing well due to AI demand."   <- no citation tag
  "Revenue grew strongly [cite:1,2]"                   <- wrong tag format"""