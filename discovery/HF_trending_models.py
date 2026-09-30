import json
import requests

URL = "https://huggingface.co/api/models"
PARAMS = {"sort": "trendingScore", "direction": -1, "limit": 50}

FIELDS = [
    "_id", "id", "modelId", "trendingScore", "likes", "downloads",
    "private", "pipeline_tag", "library_name", "createdAt", "tags",
]

# If you're behind a corporate proxy, set it here, e.g.
# PROXIES = {"https": "http://your-proxy:port"}
PROXIES = None


def fetch_trending_models(limit=50):
    print(f"Fetching Hugging Face trending models (limit={limit})")
    params = dict(PARAMS)
    params["limit"] = limit
    resp = requests.get(URL, params=params, proxies=PROXIES, timeout=30)
    resp.raise_for_status()

    models = [{field: m.get(field) for field in FIELDS} for m in resp.json()]
    print(f"Hugging Face API returned {len(models)} models.")
    return models


class HuggingFaceModelDiscovery:
    """Discovers trending Hugging Face models."""

    def __init__(self, top_n=7):
        self.top_n = top_n

    def run(self):
        print()
        print("=" * 80)
        print("        HUGGING FACE TRENDING MODELS")
        print("=" * 80)

        models = fetch_trending_models(limit=self.top_n)
        top_models = models[:self.top_n]

        print()
        print("=" * 80)
        print("        TOP TRENDING HUGGING FACE MODELS")
        print("=" * 80)

        for index, model in enumerate(top_models, start=1):
            model_id = model.get("id") or model.get("modelId") or "unknown"
            print()
            print(f"{index}. {model_id}")
            print(f"   Trending score: {model.get('trendingScore')}")
            print(f"   Downloads: {model.get('downloads')}")
            print(f"   Likes: {model.get('likes')}")
            print(f"   Pipeline: {model.get('pipeline_tag')}")
            print(f"   Created: {model.get('createdAt')}")

        print()
        print(f"Selected {len(top_models)} Hugging Face models.")

        return {
            "tags": top_models
        }


if __name__ == "__main__":
    models = fetch_trending_models()

    with open("trending_models.json", "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2, ensure_ascii=False)

    print(json.dumps(models, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(models)} models to trending_models.json")
