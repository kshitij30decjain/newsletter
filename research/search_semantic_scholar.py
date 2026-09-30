import json
import time

import requests

from paper_common import (
    TEST_ITEMS,
    LLMClient,
    RateLimiter,
    empty_result,
    env,
    env_int,
    paper_result,
    search_query,
    select_relevant_paper,
    summarize_paper,
    truncate,
    validate_item,
)


class SemanticScholarSearchTool:

    def __init__(self):
        self.api_key = env("SEMANTIC_SCHOLAR_API_KEY")
        self.base_url = env("SEMANTIC_SCHOLAR_BASE_URL").rstrip("/")
        self.search_limit = env_int("SEMANTIC_SCHOLAR_SEARCH_LIMIT")
        self.fields = env("SEMANTIC_SCHOLAR_FIELDS")
        self.timeout = env_int("SEMANTIC_SCHOLAR_TIMEOUT_SECONDS")
        self.max_retries = env_int("SEMANTIC_SCHOLAR_MAX_RETRIES")
        self.abstract_char_limit = env_int("PAPER_ABSTRACT_CHAR_LIMIT")
        self.llm = LLMClient()
        self.rate_limiter = RateLimiter(
            env_int("SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS")
        )

    def _request(self, path, params):
        url = self.base_url + path
        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            self.rate_limiter.wait()

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = (
                    float(retry_after)
                    if retry_after
                    else self.rate_limiter.min_interval_seconds * attempt
                )
                print(
                    "WARNING: Semantic Scholar rate limited. "
                    f"Waiting {wait_seconds:.1f}s "
                    f"(attempt {attempt}/{self.max_retries})"
                )
                time.sleep(wait_seconds)
                last_error = requests.HTTPError(
                    f"429 Too Many Requests after {attempt} attempts"
                )
                continue

            response.raise_for_status()
            return response.json()

        if last_error:
            raise last_error

        raise RuntimeError("Semantic Scholar request failed")

    def _search_papers(self, query):
        print(f"Searching Semantic Scholar for: {query}")

        data = self._request(
            "/paper/search",
            {
                "query": query,
                "limit": self.search_limit,
                "fields": self.fields,
            },
        )

        return data.get("data") or []

    def _author_names(self, authors):
        names = []
        for author in authors or []:
            if isinstance(author, dict):
                name = author.get("name")
                if name:
                    names.append(name)
            elif author:
                names.append(str(author))
        return names

    def _paper_url(self, paper):
        url = paper.get("url")
        if url:
            return url

        external_ids = paper.get("externalIds") or {}
        arxiv_id = external_ids.get("ArXiv")
        if arxiv_id:
            return f"https://arxiv.org/abs/{arxiv_id}"

        doi = external_ids.get("DOI")
        if doi:
            return f"https://doi.org/{doi}"

        paper_id = paper.get("paperId")
        if paper_id:
            return f"https://www.semanticscholar.org/paper/{paper_id}"

        return None

    def _candidate(self, index, paper):
        tldr = paper.get("tldr") or {}
        abstract = paper.get("abstract") or tldr.get("text") or ""

        return {
            "index": index,
            "paper_id": paper.get("paperId"),
            "title": paper.get("title"),
            "abstract": truncate(abstract, 800),
            "authors": self._author_names(paper.get("authors")),
            "year": paper.get("year"),
            "venue": paper.get("venue"),
            "citation_count": paper.get("citationCount", 0),
            "url": self._paper_url(paper),
        }

    def _process_paper(self, paper):
        tldr = paper.get("tldr") or {}
        abstract = paper.get("abstract") or tldr.get("text") or ""
        abstract = truncate(abstract, self.abstract_char_limit)
        authors = self._author_names(paper.get("authors"))
        title = paper.get("title") or ""

        print(f"Summarizing paper: {title}")

        summary = summarize_paper(
            self.llm,
            {
                "title": title,
                "authors": authors,
                "year": paper.get("year"),
                "venue": paper.get("venue"),
                "abstract": abstract,
            },
        )

        return {
            "paper_id": paper.get("paperId"),
            "title": title,
            "description": abstract,
            "readme": summary,
            "authors": authors,
            "year": paper.get("year"),
            "venue": paper.get("venue"),
            "citation_count": paper.get("citationCount", 0),
            "publication_date": paper.get("publicationDate"),
            "url": self._paper_url(paper),
        }

    def search(self, item):
        item_type, item_name = validate_item(item)

        print()
        print("=" * 80)
        print(f"Processing {item_type}: {item_name}")
        print("=" * 80)

        papers = self._search_papers(search_query(item_name))

        if not papers:
            print("No Semantic Scholar papers found.")
            return empty_result(
                item_type,
                item_name,
                "semantic_scholar",
            )

        print(f"Found {len(papers)} candidate papers.")

        candidates = [
            self._candidate(index, paper)
            for index, paper in enumerate(papers)
        ]

        selected_index = select_relevant_paper(
            llm=self.llm,
            original_name=item_name,
            item_type=item_type,
            candidates=candidates,
        )

        if selected_index is None:
            print("No relevant Semantic Scholar paper found.")
            return empty_result(
                item_type,
                item_name,
                "semantic_scholar",
            )

        selected_paper = self._process_paper(papers[selected_index])
        print(f"Selected paper: {selected_paper.get('title')}")

        return paper_result(
            item_type,
            item_name,
            "semantic_scholar",
            [selected_paper],
        )


def main():
    tool = SemanticScholarSearchTool()
    results = []

    for item in TEST_ITEMS:
        results.append(tool.search(item))

    print()
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
