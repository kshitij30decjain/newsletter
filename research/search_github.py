import json
import sys
from pathlib import Path

import requests
# from openai import OpenAI

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_loader import env, env_int
from paper_common import LLMClient, parse_json_text


class GitHubSearchTool:

    def __init__(
        self,
        github_token=None,
        openai_api_key=None,
        openai_model=None
    ):
        self.github_token = github_token or env("GITHUB_TOKEN")
        # openai_api_key = openai_api_key or env("OPENAI_API_KEY")
        # self.openai_model = openai_model or env("OPENAI_MODEL")
        self.github_base_url = env("GITHUB_API_BASE_URL").rstrip("/")
        self.github_raw_base_url = env("GITHUB_RAW_BASE_URL").rstrip("/")
        self.timeout = env_int("GITHUB_TIMEOUT_SECONDS")
        self.search_limit = env_int("GITHUB_SEARCH_LIMIT")

        # self.openai_client = OpenAI(
        #     api_key=openai_api_key
        # )
        self.llm = LLMClient()

        self.github_headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": env("GITHUB_API_VERSION")
        }

    # =========================================================
    # GitHub API GET
    # =========================================================

    def _github_get(self, endpoint):

        response = requests.get(
            self.github_base_url + endpoint,
            headers=self.github_headers,
            timeout=self.timeout
        )

        response.raise_for_status()

        return response.json()

    # =========================================================
    # Search GitHub repositories
    # =========================================================

    def _search_repositories(self, query):

        print(
            f"Searching GitHub for: {query}"
        )

        encoded_query = requests.utils.quote(
            query
        )

        data = self._github_get(
            f"/search/repositories"
            f"?q={encoded_query}"
            f"&per_page={self.search_limit}"
        )

        return data.get("items", [])

    # =========================================================
    # Ask LLM to select the most relevant repository
    # =========================================================

    def _select_relevant_repository(
        self,
        original_name,
        item_type,
        repositories
    ):

        if not repositories:
            return None

        # -----------------------------------------------------
        # Prepare lightweight candidate information
        # -----------------------------------------------------

        candidates = []

        for index, repo in enumerate(
            repositories
        ):

            candidates.append({
                "index": index,
                "name": repo.get(
                    "full_name"
                ),
                "description": repo.get(
                    "description"
                ),
                "topics": repo.get(
                    "topics",
                    []
                ),
                "language": repo.get(
                    "language"
                ),
                "stars": repo.get(
                    "stargazers_count",
                    0
                ),
                "url": repo.get(
                    "html_url"
                )
            })

        candidates_json = json.dumps(
            candidates,
            indent=2,
            ensure_ascii=False
        )

        # -----------------------------------------------------
        # LLM prompt
        # -----------------------------------------------------

        prompt = f"""
You are a technical research agent.

We need to find the GitHub repository most relevant
to the following discovery item.

Discovery type:
{item_type}

Discovery name:
{original_name}

Below are GitHub search candidates:

{candidates_json}

Your task is to select the repository that is MOST
directly related to the discovery item.

Consider:

1. Repository name
2. Repository description
3. Topics
4. Programming language
5. Whether the repository actually implements,
   develops, documents, or directly relates to the
   requested technology/model/topic.

IMPORTANT:

- Do NOT select a repository merely because the name
  contains a similar word.
- For a MODEL, prefer the repository that actually
  contains, implements, hosts, converts, serves, or
  develops that model.
- For a TAG, prefer the repository that is most
  technically relevant to that technology/topic.
- Do not select unrelated repositories.
- If none of the candidates are genuinely relevant,
  return null.
- Do not invent repositories.

Return ONLY valid JSON.

Format:

{{
    "selected_index": 0,
    "confidence": 0.95,
    "reason": "Short explanation"
}}

If there is no relevant repository:

{{
    "selected_index": null,
    "confidence": 0.0,
    "reason": "No relevant repository found"
}}
"""

        # response = self.openai_client.responses.create(
        #     model=self.openai_model,
        #     input=prompt
        # )
        #
        # result_text = (
        #     response.output_text
        #     .strip()
        # )
        result_text = self.llm.complete(prompt)

        # -----------------------------------------------------
        # Parse LLM response
        # -----------------------------------------------------

        try:

            # result = json.loads(
            #     result_text
            # )
            result = parse_json_text(
                result_text
            )

        except json.JSONDecodeError:

            print(
                "WARNING: Invalid JSON from "
                "repository relevance LLM"
            )

            print(
                result_text
            )

            return None

        selected_index = result.get(
            "selected_index"
        )

        confidence = result.get(
            "confidence",
            0
        )

        print(
            f"Repository confidence: {confidence}"
        )

        print(
            f"Reason: {result.get('reason')}"
        )

        # -----------------------------------------------------
        # No relevant repository
        # -----------------------------------------------------

        if selected_index is None:
            return None

        # -----------------------------------------------------
        # Validate index
        # -----------------------------------------------------

        if not isinstance(
            selected_index,
            int
        ):
            return None

        if (
            selected_index < 0
            or selected_index >= len(repositories)
        ):
            return None

        return repositories[
            selected_index
        ]

    # =========================================================
    # Find relevant repository
    # =========================================================

    def _find_repository(
        self,
        name,
        item_type
    ):

        repositories = (
            self._search_repositories(
                name
            )
        )

        if not repositories:

            print(
                "No GitHub repositories found."
            )

            return None

        print(
            f"Found {len(repositories)} "
            "candidate repositories."
        )

        # -----------------------------------------------------
        # LLM relevance selection
        # -----------------------------------------------------

        repository = (
            self._select_relevant_repository(
                original_name=name,
                item_type=item_type,
                repositories=repositories
            )
        )

        return repository

    # =========================================================
    # Get exact repository
    # =========================================================

    def _get_repository(
        self,
        repo_name
    ):

        return self._github_get(
            f"/repos/{repo_name}"
        )

    # =========================================================
    # Get README
    # =========================================================

    def _get_readme(
        self,
        repo_name,
        default_branch
    ):

        url = (
            f"{self.github_raw_base_url}/"
            f"{repo_name}/refs/heads/"
            f"{default_branch}/README.md"
        )

        print(
            f"Fetching README from: {url}"
        )

        try:

            response = requests.get(
                url,
                timeout=self.timeout
            )

            if response.status_code == 200:

                return response.text

            # -------------------------------------------------
            # Try lowercase readme
            # -------------------------------------------------

            url = (
                f"{self.github_raw_base_url}/"
                f"{repo_name}/refs/heads/"
                f"{default_branch}/readme.md"
            )

            response = requests.get(
                url,
                timeout=self.timeout
            )

            if response.status_code == 200:

                return response.text

            print(
                "WARNING: README not found."
            )

            return ""

        except Exception as e:

            print(
                f"WARNING: README fetch failed: {e}"
            )

            return ""

    # =========================================================
    # Summarize README using OpenAI
    # =========================================================

    def _summarize_readme(
        self,
        description,
        readme
    ):

        prompt = f"""
You are writing a newsletter brief for AI engineers,
researchers, and technical product readers.

Analyze this GitHub project and write a
newsletter-ready summary. This text will be published
as-is, so it must be accurate, complete, and easy to
read.

Repository description:
{description or "Not available"}

README:
{readme or "README not available"}

WRITE A NEWSLETTER SUMMARY THAT COVERS THESE POINTS,
IN THIS ORDER:

What is it?
What the project or model actually does. Be specific.

Problem solved
The pain point or use case it addresses.

How does it work?
The key technical approach, framework, architecture,
or model. Keep important names, sizes, and methods.

Who should use it?
Developers, researchers, enterprises, AI engineers,
or another audience only if the source supports it.

Why is it useful?
The practical value or advantage.

Key capabilities
Important features, protocols, integrations, and
modalities.

Performance
Important benchmarks only if the README provides
them. If none are present, omit this section.

Maturity/status
Production-ready, experimental, research project, or
early-stage only if the README supports it. If
not stated, omit this section.

Use those labels as short section headings. Under each
heading, write 1-3 tight newsletter sentences, not a
bullet dump. Keep the voice clear and useful.

STRICT REQUIREMENTS:

1. Total length must be about 200 words. Stay close to
   200 words. Do not go under 180 or over 220.
2. Do not drop important technical information: model
   names, parameter counts, context length, architecture
   details, protocols, supported tools, and benchmark
   scores must be kept if they appear in the source.
3. Prefer concrete facts over adjectives.
4. Use clear newsletter English. Short sentences.
5. Do not invent information, numbers, audiences, or
   maturity claims.
6. If a benchmark, integration, or status is not in
   the source, omit it. Do not guess.
7. Do not use marketing language, hype, or phrases like
   "game-changing", "revolutionary", or "must-try".
8. Remove HTML, Markdown, badges, installation steps,
   setup commands, contributor lists, license text, and
   links.
9. Do not include a title above the sections.
10. Return only the newsletter summary text.

The summary must be complete enough that a reader can
understand the project without opening the repository.
"""

        # response = self.openai_client.responses.create(
        #     model=self.openai_model,
        #     input=prompt
        # )
        #
        # return (
        #     response.output_text
        #     .strip()
        # )
        return self.llm.complete(prompt)

    # =========================================================
    # Process selected repository
    # =========================================================

    def _process_repository(
        self,
        repository,
        original_type,
        original_name
    ):

        repo_name = repository.get(
            "full_name"
        )

        if not repo_name:
            return None

        print(
            f"Selected repository: {repo_name}"
        )

        # -----------------------------------------------------
        # Get complete repository metadata
        # -----------------------------------------------------

        repo = self._get_repository(
            repo_name
        )

        default_branch = repo.get(
            "default_branch",
            "main"
        )

        # -----------------------------------------------------
        # Fetch README
        # -----------------------------------------------------

        readme = self._get_readme(
            repo_name,
            default_branch
        )

        # -----------------------------------------------------
        # Summarize README
        # -----------------------------------------------------

        print(
            "Generating README summary..."
        )

        summary = self._summarize_readme(
            description=repo.get(
                "description"
            ),
            readme=readme
        )

        # -----------------------------------------------------
        # Return final structure
        # -----------------------------------------------------

        return {
            "type": original_type,

            "name": original_name,

            "source": "github",

            "data": {

                "repository": repo_name,

                "description": repo.get(
                    "description"
                ),

                "readme": summary,

                "stars": repo.get(
                    "stargazers_count",
                    0
                ),

                "forks": repo.get(
                    "forks_count",
                    0
                ),

                "topics": repo.get(
                    "topics",
                    []
                ),

                "created_at": repo.get(
                    "created_at"
                ),

                "updated_at": repo.get(
                    "updated_at"
                ),

                "url": repo.get(
                    "html_url"
                )
            }
        }

    # =========================================================
    # PUBLIC SEARCH FUNCTION
    # =========================================================

    def search(
        self,
        item
    ):

        if not isinstance(
            item,
            dict
        ):
            raise ValueError(
                "Input must be a dictionary"
            )

        item_type = item.get(
            "type"
        )

        item_name = item.get(
            "name"
        )

        if item_type not in {
            "repo",
            "model",
            "tag"
        }:

            raise ValueError(
                "type must be repo, model, or tag"
            )

        if not item_name:

            raise ValueError(
                "name is required"
            )

        print()
        print("=" * 80)
        print(
            f"Processing {item_type}: {item_name}"
        )
        print("=" * 80)

        # =====================================================
        # REPOSITORY
        # =====================================================

        if item_type == "repo":

            # -------------------------------------------------
            # Repository is already known.
            # Do NOT perform GitHub search.
            # -------------------------------------------------

            print(
                f"Using exact repository: {item_name}"
            )

            repository = {
                "full_name": item_name
            }

        # =====================================================
        # MODEL / TAG
        # =====================================================

        else:

            # -------------------------------------------------
            # Search GitHub and let LLM select
            # the most relevant repository.
            # -------------------------------------------------

            repository = (
                self._find_repository(
                    name=item_name,
                    item_type=item_type
                )
            )

            if not repository:

                print(
                    "No relevant GitHub repository found."
                )

                return {
                    "type": item_type,
                    "name": item_name,
                    "source": "github",
                    "data": None
                }

        # =====================================================
        # Research repository
        # =====================================================

        return self._process_repository(
            repository=repository,
            original_type=item_type,
            original_name=item_name
        )


# =============================================================
# MAIN
# =============================================================

def main():

    tool = GitHubSearchTool()

    # =========================================================
    # TEST 1 — REPO
    # =========================================================


    items = [
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

    results = []

    for item in items:
        results.append(tool.search(item))

    print()
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    print(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
