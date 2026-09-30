import json
import re

import requests

from paper_common import (
    TEST_ITEMS,
    LLMClient,
    empty_result,
    env,
    env_int,
    paper_result,
    search_query,
    select_relevant_paper,
    strip_html,
    summarize_paper,
    truncate,
    validate_item,
)


class OpenAireSearchTool:

    def __init__(self):
        self.base_url = env("OPENAIRE_BASE_URL")
        self.search_limit = env_int("OPENAIRE_SEARCH_LIMIT")
        self.product_type = env("OPENAIRE_TYPE")
        self.timeout = env_int("OPENAIRE_TIMEOUT_SECONDS")
        self.abstract_char_limit = env_int("PAPER_ABSTRACT_CHAR_LIMIT")
        self.llm = LLMClient()

    def _search_papers(self, query):
        print(f"Searching OpenAIRE for: {query}")

        response = requests.get(
            self.base_url,
            params={
                "search": query,
                "type": self.product_type,
                "page": 1,
                "pageSize": self.search_limit,
            },
            headers={
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        return data.get("results") or []

    def _author_names(self, authors):
        names = []
        for author in authors or []:
            if not isinstance(author, dict):
                continue
            name = author.get("fullName")
            if not name:
                parts = [
                    author.get("name") or "",
                    author.get("surname") or "",
                ]
                name = " ".join(part for part in parts if part).strip()
            if name:
                names.append(name)
        return names

    def _abstract(self, paper):
        descriptions = paper.get("descriptions") or []
        for description in descriptions:
            cleaned = strip_html(description)
            if cleaned:
                return truncate(cleaned, self.abstract_char_limit)
        return ""

    def _year(self, paper):
        publication_date = paper.get("publicationDate") or ""
        match = re.match(r"(\d{4})", str(publication_date))
        if match:
            return int(match.group(1))
        return None

    def _venue(self, paper):
        container = paper.get("container") or {}
        return (
            container.get("name")
            or paper.get("publisher")
        )

    def _doi(self, paper):
        for pid in paper.get("pids") or []:
            if not isinstance(pid, dict):
                continue
            if str(pid.get("scheme") or "").lower() == "doi" and pid.get("value"):
                return pid.get("value")
        return None

    def _paper_url(self, paper):
        doi = self._doi(paper)
        if doi:
            return f"https://doi.org/{doi}"

        for instance in paper.get("instances") or []:
            urls = instance.get("urls") or []
            for url in urls:
                if url:
                    return url

        return None

    def _citation_count(self, paper):
        indicators = paper.get("indicators") or {}
        citation_impact = indicators.get("citationImpact") or {}
        count = citation_impact.get("citationCount")
        if count is None:
            return 0
        try:
            return int(count)
        except (TypeError, ValueError):
            return 0

    def _candidate(self, index, paper):
        return {
            "index": index,
            "paper_id": paper.get("id"),
            "title": paper.get("mainTitle"),
            "abstract": truncate(self._abstract(paper), 800),
            "authors": self._author_names(paper.get("authors")),
            "year": self._year(paper),
            "venue": self._venue(paper),
            "citation_count": self._citation_count(paper),
            "url": self._paper_url(paper),
        }

    def _process_paper(self, paper):
        title = paper.get("mainTitle") or ""
        authors = self._author_names(paper.get("authors"))
        abstract = self._abstract(paper)

        print(f"Summarizing paper: {title}")

        summary = summarize_paper(
            self.llm,
            {
                "title": title,
                "authors": authors,
                "year": self._year(paper),
                "venue": self._venue(paper),
                "abstract": abstract,
            },
        )

        return {
            "paper_id": paper.get("id"),
            "title": title,
            "description": abstract,
            "readme": summary,
            "authors": authors,
            "year": self._year(paper),
            "venue": self._venue(paper),
            "citation_count": self._citation_count(paper),
            "publication_date": paper.get("publicationDate"),
            "doi": self._doi(paper),
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
            print("No OpenAIRE papers found.")
            return empty_result(
                item_type,
                item_name,
                "openaire",
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
            print("No relevant OpenAIRE paper found.")
            return empty_result(
                item_type,
                item_name,
                "openaire",
            )

        selected_paper = self._process_paper(papers[selected_index])
        print(f"Selected paper: {selected_paper.get('title')}")

        return paper_result(
            item_type,
            item_name,
            "openaire",
            [selected_paper],
        )


def main():
    tool = OpenAireSearchTool()
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
