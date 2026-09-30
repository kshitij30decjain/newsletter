import json

import requests

from paper_common import (
    TEST_ITEMS,
    LLMClient,
    empty_result,
    env,
    env_int,
    env_optional,
    paper_result,
    search_query,
    select_relevant_paper,
    summarize_paper,
    truncate,
    validate_item,
)


class HuggingFacePapersSearchTool:

    def __init__(self):
        self.search_url = env("HUGGINGFACE_PAPERS_SEARCH_URL")
        self.search_limit = env_int("HUGGINGFACE_PAPERS_SEARCH_LIMIT")
        self.timeout = env_int("HUGGINGFACE_PAPERS_TIMEOUT_SECONDS")
        self.abstract_char_limit = env_int("PAPER_ABSTRACT_CHAR_LIMIT")
        self.hf_base_url = env("HUGGINGFACE_BASE_URL").rstrip("/")
        self.hf_token = env_optional("HF_TOKEN")
        self.llm = LLMClient()

    def _headers(self):
        headers = {
            "Accept": "application/json",
        }
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        return headers

    def _search_papers(self, query):
        print(f"Searching Hugging Face Papers for: {query}")

        response = requests.get(
            self.search_url,
            params={
                "q": query[:250],
                "limit": self.search_limit,
            },
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        if isinstance(data, list):
            return data[:self.search_limit]
        if isinstance(data, dict):
            return (data.get("papers") or data.get("data") or [])[:self.search_limit]
        return []

    def _paper_payload(self, hit):
        if not isinstance(hit, dict):
            return {}
        paper = hit.get("paper")
        if isinstance(paper, dict):
            return paper
        return hit

    def _author_names(self, authors):
        names = []
        for author in authors or []:
            if isinstance(author, dict):
                name = author.get("name") or author.get("fullname")
                if name:
                    names.append(name)
            elif author:
                names.append(str(author))
        return names

    def _year(self, paper, hit):
        published = (
            paper.get("publishedAt")
            or hit.get("publishedAt")
            or ""
        )
        if isinstance(published, str) and len(published) >= 4 and published[:4].isdigit():
            return int(published[:4])
        return None

    def _venue(self, paper, hit):
        organization = paper.get("organization") or hit.get("organization")
        if isinstance(organization, dict):
            return organization.get("fullname") or organization.get("name")
        if isinstance(organization, str):
            return organization
        return "Hugging Face Papers"

    def _abstract(self, paper, hit):
        abstract = (
            paper.get("summary")
            or hit.get("summary")
            or paper.get("ai_summary")
            or ""
        )
        return truncate(abstract, self.abstract_char_limit)

    def _paper_id(self, paper, hit):
        return paper.get("id") or hit.get("id")

    def _paper_url(self, paper, hit):
        paper_id = self._paper_id(paper, hit)
        if paper_id:
            return f"{self.hf_base_url}/papers/{paper_id}"
        return None

    def _candidate(self, index, hit):
        paper = self._paper_payload(hit)
        return {
            "index": index,
            "paper_id": self._paper_id(paper, hit),
            "title": paper.get("title") or hit.get("title"),
            "abstract": truncate(self._abstract(paper, hit), 800),
            "authors": self._author_names(paper.get("authors")),
            "year": self._year(paper, hit),
            "venue": self._venue(paper, hit),
            "upvotes": paper.get("upvotes") or hit.get("upvotes") or 0,
            "url": self._paper_url(paper, hit),
        }

    def _process_paper(self, hit):
        paper = self._paper_payload(hit)
        title = paper.get("title") or hit.get("title") or ""
        authors = self._author_names(paper.get("authors"))
        abstract = self._abstract(paper, hit)

        print(f"Summarizing paper: {title}")

        summary = summarize_paper(
            self.llm,
            {
                "title": title,
                "authors": authors,
                "year": self._year(paper, hit),
                "venue": self._venue(paper, hit),
                "abstract": abstract,
            },
        )

        return {
            "paper_id": self._paper_id(paper, hit),
            "title": title,
            "description": abstract,
            "readme": summary,
            "authors": authors,
            "year": self._year(paper, hit),
            "venue": self._venue(paper, hit),
            "upvotes": paper.get("upvotes") or 0,
            "github_repo": paper.get("githubRepo"),
            "publication_date": paper.get("publishedAt") or hit.get("publishedAt"),
            "url": self._paper_url(paper, hit),
        }

    def search(self, item):
        item_type, item_name = validate_item(item)

        print()
        print("=" * 80)
        print(f"Processing {item_type}: {item_name}")
        print("=" * 80)

        papers = self._search_papers(search_query(item_name))

        if not papers:
            print("No Hugging Face papers found.")
            return empty_result(
                item_type,
                item_name,
                "huggingface_papers",
            )

        print(f"Found {len(papers)} candidate papers.")

        candidates = [
            self._candidate(index, hit)
            for index, hit in enumerate(papers)
        ]

        selected_index = select_relevant_paper(
            llm=self.llm,
            original_name=item_name,
            item_type=item_type,
            candidates=candidates,
        )

        if selected_index is None:
            print("No relevant Hugging Face paper found.")
            return empty_result(
                item_type,
                item_name,
                "huggingface_papers",
            )

        selected_paper = self._process_paper(papers[selected_index])
        print(f"Selected paper: {selected_paper.get('title')}")

        return paper_result(
            item_type,
            item_name,
            "huggingface_papers",
            [selected_paper],
        )


def main():
    tool = HuggingFacePapersSearchTool()
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
