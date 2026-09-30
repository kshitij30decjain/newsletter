import html
import json
import re
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_loader import env, env_bool, env_float, env_int, env_optional


def search_query(name):
    return re.sub(r"[\/_]+", " ", name).strip()


def strip_html(text):
    if not text:
        return ""

    cleaned = html.unescape(str(text))
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def truncate(text, limit):
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def validate_item(item):
    if not isinstance(item, dict):
        raise ValueError("Input must be a dictionary")

    item_type = item.get("type")
    item_name = item.get("name")

    if item_type not in {"repo", "model", "tag"}:
        raise ValueError("type must be repo, model, or tag")

    if not item_name:
        raise ValueError("name is required")

    return item_type, item_name


def empty_result(item_type, item_name, source):
    return {
        "type": item_type,
        "name": item_name,
        "source": source,
        "data": None,
    }


def paper_result(item_type, item_name, source, papers):
    if not papers:
        return empty_result(item_type, item_name, source)

    return {
        "type": item_type,
        "name": item_name,
        "source": source,
        "data": {
            "papers": papers
        },
    }


def parse_json_text(text):
    if not text:
        raise json.JSONDecodeError("empty response", "", 0)

    cleaned = text.strip()
    cleaned = re.sub(
        r"<think>.*?</think>",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


class LLMClient:
    def __init__(self):
        self.api_key = env("LLM_API_KEY")
        self.api_url = env("LLM_API_URL")
        self.model = env("LLM_MODEL")
        self.temperature = env_float("LLM_TEMPERATURE")
        self.max_tokens = env_int("LLM_MAX_TOKENS")
        self.enable_thinking = env_bool("LLM_ENABLE_THINKING")
        self.timeout = env_int("LLM_TIMEOUT_SECONDS")

    def complete(self, prompt):
        response = requests.post(
            self.api_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "chat_template_kwargs": {
                    "enable_thinking": self.enable_thinking
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("LLM returned no choices")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise ValueError("LLM returned an empty message")

        return content.strip()


class RateLimiter:
    def __init__(self, min_interval_seconds):
        self.min_interval_seconds = float(min_interval_seconds)
        self._last_request_at = 0.0

    def wait(self):
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()


def select_relevant_paper(
    llm,
    original_name,
    item_type,
    candidates,
):
    if not candidates:
        return None

    candidates_json = json.dumps(
        candidates,
        indent=2,
        ensure_ascii=False,
    )

    prompt = f"""
You are a technical research agent.

We need to find the ONE research paper most relevant
to the following discovery item.

Discovery type:
{item_type}

Discovery name:
{original_name}

Below are paper search candidates:

{candidates_json}

Your task is to select the paper that is MOST
directly related to the discovery item.

Consider:

1. Paper title
2. Abstract
3. Authors and venue
4. Publication year / date
5. Whether the paper actually introduces, evaluates,
   implements, or studies the requested
   technology/model/topic.

IMPORTANT:

- Select exactly ONE paper.
- Do NOT select a paper merely because the title
  contains a similar word.
- For a MODEL, prefer the paper that introduces,
  trains, evaluates, or converts that model.
- For a REPO, prefer the paper that describes that
  project or the technology it implements.
- For a TAG, prefer the paper that is most
  technically relevant to that topic.
- When two papers are similarly relevant, prefer
  the more recent one.
- Prefer the primary/original paper over later
  commentary, reviews, or loosely related work.
- Do not select unrelated papers.
- If none of the candidates are genuinely relevant,
  return null.
- Do not invent papers.

Return ONLY valid JSON.

Format:

{{
    "selected_index": 0,
    "confidence": 0.95,
    "reason": "Short explanation"
}}

If there is no relevant paper:

{{
    "selected_index": null,
    "confidence": 0.0,
    "reason": "No relevant paper found"
}}
"""

    result_text = llm.complete(prompt)

    try:
        result = parse_json_text(result_text)
    except json.JSONDecodeError:
        print("WARNING: Invalid JSON from paper relevance LLM")
        print(result_text)
        return None

    selected_index = result.get("selected_index")
    print(f"Paper confidence: {result.get('confidence', 0)}")
    print(f"Reason: {result.get('reason')}")

    if selected_index is None:
        return None

    if not isinstance(selected_index, int):
        return None

    if selected_index < 0 or selected_index >= len(candidates):
        return None

    return selected_index


def summarize_paper(llm, paper):
    authors = paper.get("authors") or []
    if isinstance(authors, list):
        authors_text = ", ".join(str(name) for name in authors if name)
    else:
        authors_text = str(authors)

    prompt = f"""
You are writing a newsletter brief for AI engineers,
researchers, and technical product readers.

Analyze this research paper and write a
newsletter-ready summary. This text will be published
as-is, so it must be accurate, complete, and easy to
read.

Title:
{paper.get("title") or "Not available"}

Authors:
{authors_text or "Not available"}

Year:
{paper.get("year") or "Not available"}

Venue:
{paper.get("venue") or "Not available"}

Abstract:
{paper.get("abstract") or "Abstract not available"}

WRITE A NEWSLETTER SUMMARY THAT COVERS THESE POINTS,
IN THIS ORDER:

What is it?
What the paper actually contributes. Be specific.

Problem solved
The pain point or research gap it addresses.

How does it work?
The key technical approach, architecture, method,
or model. Keep important names, sizes, and methods.

Who should use it?
Researchers, engineers, or another audience only if
the source supports it.

Why is it useful?
The practical or scientific value.

Key capabilities
Important methods, datasets, modalities, and
integrations.

Performance
Important benchmarks only if the abstract provides
them. If none are present, omit this section.

Maturity/status
Preprint, peer-reviewed, or experimental only if
the source supports it. If not stated, omit this
section.

Use those labels as short section headings. Under each
heading, write 1-3 tight newsletter sentences, not a
bullet dump. Keep the voice clear and useful.

STRICT REQUIREMENTS:

1. Total length must be about 200 words. Stay close to
   200 words. Do not go under 180 or over 220.
2. Do not drop important technical information: model
   names, parameter counts, datasets, architecture
   details, and benchmark scores must be kept if they
   appear in the source.
3. Prefer concrete facts over adjectives.
4. Use clear newsletter English. Short sentences.
5. Do not invent information, numbers, audiences, or
   maturity claims.
6. If a benchmark, dataset, or status is not in the
   source, omit it. Do not guess.
7. Do not use marketing language, hype, or phrases like
   "game-changing", "revolutionary", or "must-try".
8. Remove HTML, Markdown, badges, citations lists,
   LaTeX, and links.
9. Do not include a title above the sections.
10. Return only the newsletter summary text.

The summary must be complete enough that a reader can
understand the paper without opening the PDF.
"""

    return llm.complete(prompt).strip()


TEST_ITEMS = [
    {
        "type": "repo",
        "name": "alibaba/open-code-review"
    },
    {
        "type": "model",
        "name": "prism-ml/Ternary-Bonsai-2-27B-gguf"
    },
    {
        "type": "tag",
        "name": "kimi k3"
    }
]
