import sys
from pathlib import Path

import requests
from datetime import datetime, timezone, timedelta

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_loader import env, env_int


class GitHubTrendingAI:

    def __init__(
        self,
        top_n=8,
        search_per_query=20
    ):
        self.top_n = top_n
        self.search_per_query = search_per_query

        self.token = env("GITHUB_TOKEN")
        self.base_url = env("GITHUB_API_BASE_URL").rstrip("/")
        self.timeout = env_int("GITHUB_TIMEOUT_SECONDS")

        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": env("GITHUB_API_VERSION")
        }

        # Broad AI topics.
        # We use these only to discover candidate repositories.
        self.search_queries = [
            "AI agents",
            "agentic AI",
            "LLM",
            "RAG",
            "MCP",
            "generative AI",
            "multimodal AI",
            "AI coding",
            "reasoning models",
            "multi agent",
            "computer use AI",
            "context engineering",
            "AI memory",
            "AI inference",
            "AI evaluation",
            "AI safety",
            "AI observability",
            "AI infrastructure",
            "AI model"
        ]

    # ---------------------------------------------------------
    # GitHub GET
    # ---------------------------------------------------------

    def _get(self, endpoint, params=None):

        response = requests.get(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            params=params,
            timeout=self.timeout
        )

        response.raise_for_status()

        return response.json()

    # ---------------------------------------------------------
    # Search repositories
    # ---------------------------------------------------------

    def search_repositories(self):

        repositories = {}

        for query in self.search_queries:

            print(
                f"Searching: {query}"
            )

            params = {
                "q": f"{query} stars:>50",
                "sort": "stars",
                "order": "desc",
                "per_page": self.search_per_query
            }

            try:

                data = self._get(
                    "/search/repositories",
                    params
                )

            except requests.RequestException as e:

                print(
                    f"Search failed: {e}"
                )

                continue

            for repo in data.get(
                "items",
                []
            ):

                repositories[
                    repo["full_name"]
                ] = repo

        return list(
            repositories.values()
        )

    # ---------------------------------------------------------
    # Check whether repository is AI related
    # ---------------------------------------------------------

    def is_ai_repository(self, repo):

        text = " ".join([
            repo.get("name", ""),
            repo.get("description") or "",
            " ".join(
                repo.get("topics", [])
            )
        ]).lower()

        ai_keywords = [
            "ai",
            "artificial intelligence",
            "agent",
            "agentic",
            "llm",
            "language model",
            "rag",
            "retrieval",
            "generative",
            "multimodal",
            "machine learning",
            "deep learning",
            "transformer",
            "embedding",
            "vector",
            "mcp",
            "reasoning",
            "inference",
            "coding agent"
        ]

        return any(
            keyword in text
            for keyword in ai_keywords
        )

    # ---------------------------------------------------------
    # Get star history
    # ---------------------------------------------------------

    def get_star_history(
        self,
        full_name
    ):

        endpoint = (
            f"/repos/{full_name}"
            "/stargazers/history"
        )

        try:

            return self._get(
                endpoint
            )

        except requests.RequestException as e:

            print(
                f"Star history failed for "
                f"{full_name}: {e}"
            )

            return []

    # ---------------------------------------------------------
    # Calculate stars gained during last 30 days
    # ---------------------------------------------------------

    def calculate_30_day_growth(
        self,
        history
    ):

        if not history:
            return 0

        now = datetime.now(
            timezone.utc
        )

        cutoff = (
            now - timedelta(days=30)
        )

        total_growth = 0

        for week in history:

            week_timestamp = week.get(
                "week"
            )

            if not week_timestamp:
                continue

            week_date = datetime.fromtimestamp(
                week_timestamp,
                tz=timezone.utc
            )

            days = week.get(
                "days",
                []
            )

            # -------------------------------------------------
            # Star history gives a weekly total and daily
            # breakdown.
            #
            # We use the daily breakdown so we can approximate
            # an exact 30-day window.
            # -------------------------------------------------

            for index, stars in enumerate(
                days
            ):

                day_date = (
                    week_date
                    + timedelta(days=index)
                )

                if day_date >= cutoff:
                    total_growth += stars

        return total_growth

    # ---------------------------------------------------------
    # Run
    # ---------------------------------------------------------

    def run(self):

        print()
        print("=" * 80)
        print(
            "        GITHUB AI TRENDING - LAST 30 DAYS"
        )
        print("=" * 80)

        # -----------------------------------------------------
        # 1. Discover candidates
        # -----------------------------------------------------

        repositories = (
            self.search_repositories()
        )

        print()
        print(
            f"Repositories discovered: "
            f"{len(repositories)}"
        )

        # -----------------------------------------------------
        # 2. Filter AI repositories
        # -----------------------------------------------------

        repositories = [
            repo
            for repo in repositories
            if self.is_ai_repository(repo)
        ]

        print(
            f"AI repositories: "
            f"{len(repositories)}"
        )

        # -----------------------------------------------------
        # 3. Calculate star growth
        # -----------------------------------------------------

        results = []

        for index, repo in enumerate(
            repositories,
            start=1
        ):

            full_name = repo[
                "full_name"
            ]

            print(
                f"[{index}/{len(repositories)}] "
                f"{full_name}"
            )

            history = (
                self.get_star_history(
                    full_name
                )
            )

            stars_gained = (
                self.calculate_30_day_growth(
                    history
                )
            )

            if stars_gained <= 0:
                continue

            results.append({
                "repo": full_name,

                "description": (
                    repo.get(
                        "description"
                    ) or ""
                ),

                "url": repo.get(
                    "html_url"
                ),

                "current_stars": repo.get(
                    "stargazers_count",
                    0
                ),

                "current_forks": repo.get(
                    "forks_count",
                    0
                ),

                "stars_gained_30d": (
                    stars_gained
                ),

                "language": repo.get(
                    "language"
                ),

                "topics": repo.get(
                    "topics",
                    []
                )
            })

        # -----------------------------------------------------
        # 4. Sort by star growth
        # -----------------------------------------------------

        results.sort(
            key=lambda x: x[
                "stars_gained_30d"
            ],
            reverse=True
        )

        # -----------------------------------------------------
        # 5. Top N
        # -----------------------------------------------------

        top_repositories = results[
            :self.top_n
        ]

        # -----------------------------------------------------
        # 6. Print
        # -----------------------------------------------------

        print()
        print("=" * 80)
        print(
            "        TOP AI REPOSITORIES - 30 DAY STAR GROWTH"
        )
        print("=" * 80)

        for index, repo in enumerate(
            top_repositories,
            start=1
        ):

            print()
            print(
                f"{index}. {repo['repo']}"
            )

            print(
                f"   Stars gained: "
                f"+{repo['stars_gained_30d']:,}"
            )

            print(
                f"   Current stars: "
                f"{repo['current_stars']:,}"
            )

            print(
                f"   Forks: "
                f"{repo['current_forks']:,}"
            )

            print(
                f"   Language: "
                f"{repo['language']}"
            )

            print(
                f"   URL: "
                f"{repo['url']}"
            )

        return {
            "tags": top_repositories
        }


# Alias used by discovery.py and test_github.py
GitHubRepoDiscovery = GitHubTrendingAI


# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------

def main():

    github = GitHubTrendingAI(
        top_n=8,
        search_per_query=20
    )

    result = github.run()

    print()
    print("=" * 80)
    print("FINAL JSON")
    print("=" * 80)

    import json

    print(
        json.dumps(
            result,
            indent=4
        )
    )


if __name__ == "__main__":
    main()
