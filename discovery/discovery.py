import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DISCOVERY_DIR = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_io import capture_stage, save_stage_result


def _item_name(item, *keys):
    if isinstance(item, str):
        return item

    if isinstance(item, dict):
        for key in keys:
            value = item.get(key)
            if value:
                return value

    return item


def get_discovery_data():

    with capture_stage(DISCOVERY_DIR, "discovery") as stage:
        items = []

        # -----------------------------
        # Google Trends
        # -----------------------------

        print()
        print("-" * 80)
        print("SOURCE: Google Trends")
        print("-" * 80)

        try:
            from google_trend_discovery import GoogleTrendsDiscovery

            google_result = GoogleTrendsDiscovery(top_n=5).run()
            google_tags = google_result.get("tags", [])

            for tag in google_tags:
                items.append({
                    "type": "tag",
                    "name": _item_name(tag, "query")
                })

            print(f"Google Trends added {len(google_tags)} tags.")
        except Exception as e:
            print(f"WARNING: Google Trends discovery failed: {e}")

        # -----------------------------
        # GitHub
        # -----------------------------

        print()
        print("-" * 80)
        print("SOURCE: GitHub")
        print("-" * 80)

        try:
            from github_discovery import GitHubTrendingAI

            github_result = GitHubTrendingAI(top_n=8).run()
            github_repos = github_result.get("tags", [])

            for repo in github_repos:
                items.append({
                    "type": "repo",
                    "name": _item_name(repo, "repo")
                })

            print(f"GitHub added {len(github_repos)} repositories.")
        except Exception as e:
            print(f"WARNING: GitHub discovery failed: {e}")

        # -----------------------------
        # Hugging Face
        # -----------------------------

        print()
        print("-" * 80)
        print("SOURCE: Hugging Face")
        print("-" * 80)

        try:
            from HF_trending_models import HuggingFaceModelDiscovery

            huggingface_result = HuggingFaceModelDiscovery(top_n=7).run()
            huggingface_models = huggingface_result.get("tags", [])

            for model in huggingface_models:
                items.append({
                    "type": "model",
                    "name": _item_name(model, "id", "modelId")
                })

            print(f"Hugging Face added {len(huggingface_models)} models.")
        except Exception as e:
            print(f"WARNING: Hugging Face discovery failed: {e}")

        payload = {
            "items": items
        }

        print()
        print("=" * 80)
        print(f"DISCOVERY COMPLETE: {len(items)} items")
        print("=" * 80)
        for index, item in enumerate(items, start=1):
            print(f"{index}. [{item.get('type')}] {item.get('name')}")

        save_stage_result(stage, payload)
        return payload


if __name__ == "__main__":
    print(json.dumps(get_discovery_data(), indent=2))
