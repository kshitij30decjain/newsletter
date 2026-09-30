SUMMARY_PROMPT = """
You are a senior AI/ML technical research analyst.

Analyze the GitHub repository description and README below.

Create a simple-English technical summary in BULLET POINTS.
The complete output MUST be between 70 and 80 words.

Cover only the most useful information:

- What the project does
- What problem it solves
- How it works / its main architecture
- Important technologies, models, frameworks, or protocols
- Key capabilities
- Important benchmark or performance results, if available
- What makes it technically interesting

STRICT RULES:

1. Output MUST contain 70-80 words total.
2. Use 4-6 concise bullet points.
3. Each bullet should contain useful technical information.
4. Use simple English. Avoid unnecessarily complicated terminology.
5. Remove HTML, Markdown formatting, badges, images, links,
   installation instructions, commands, configuration details,
   contributor information, and license information.
6. Remove repetitive information.
7. Do not use marketing language such as "revolutionary",
   "powerful", "cutting-edge", or "innovative".
8. Preserve important technical facts, numbers, model names,
   frameworks, and benchmark results.
9. Do not invent information.
10. If a benchmark or metric is not provided, do not fabricate one.
11. Do not explain the README itself. Explain the actual technology.
12. Return ONLY the bullet points. No title or introduction.

Repository description:
{description}

README:
{readme}
"""
