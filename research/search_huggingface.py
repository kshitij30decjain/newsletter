import json
import sys
from pathlib import Path

import requests
from huggingface_hub import HfApi
# from openai import OpenAI

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_loader import env, env_int
from paper_common import LLMClient, parse_json_text


class HuggingFaceSearchTool:

    def __init__(
        self,
        openai_api_key=None,
        openai_model=None
    ):
        # openai_api_key = openai_api_key or env("OPENAI_API_KEY")
        # self.openai_model = openai_model or env("OPENAI_MODEL")
        self.base_url = env("HUGGINGFACE_BASE_URL").rstrip("/")
        self.search_limit = env_int("HUGGINGFACE_SEARCH_LIMIT")
        self.timeout = env_int("HUGGINGFACE_TIMEOUT_SECONDS")

        self.api = HfApi(
            endpoint=self.base_url
        )

        # self.openai_client = OpenAI(
        #     api_key=openai_api_key
        # )
        self.llm = LLMClient()

    # =========================================================
    # Search Hugging Face models
    # =========================================================

    def _search_models(self, query):

        print(
            f"Searching Hugging Face for: {query}"
        )

        models = self.api.list_models(
            search=query,
            limit=self.search_limit
        )

        return list(models)

    # =========================================================
    # Select most relevant model using LLM
    # =========================================================

    def _select_relevant_model(
        self,
        original_name,
        item_type,
        models
    ):

        if not models:
            return None

        candidates = []

        for index, model in enumerate(models):

            candidates.append({
                "index": index,
                "model": model.id,
                "pipeline_tag": getattr(
                    model,
                    "pipeline_tag",
                    None
                ),
                "downloads": getattr(
                    model,
                    "downloads",
                    0
                ),
                "likes": getattr(
                    model,
                    "likes",
                    0
                ),
                "trending_score": getattr(
                    model,
                    "trending_score",
                    0
                ),
                "tags": getattr(
                    model,
                    "tags",
                    []
                ),
                "created_at": str(
                    getattr(
                        model,
                        "created_at",
                        None
                    )
                ),
                "url": (
                    f"{self.base_url}/"
                    f"{model.id}"
                )
            })

        candidates_json = json.dumps(
            candidates,
            indent=2,
            ensure_ascii=False
        )

        prompt = f"""
You are a technical AI/ML research agent.

We need to find the Hugging Face model most
relevant to this discovery item.

Discovery type:
{item_type}

Discovery name:
{original_name}

Hugging Face candidates:

{candidates_json}

Select the ONE model that is most directly relevant.

Consider:

1. Model name
2. Pipeline/task
3. Model tags
4. Whether the model actually represents,
   implements, or is directly related to the
   requested technology.
5. For a model, prefer the exact model or the
   closest official model.
6. For a tag, select the model that best represents
   the technology/topic.
7. For a repository name, select a model that is
   genuinely related to that repository/project.
8. Do not select something merely because one word
   matches.
9. Do not invent a model.
10. If no candidate is genuinely relevant,
    return null.

Return ONLY valid JSON.

Format:

{{
    "selected_index": 0,
    "confidence": 0.95,
    "reason": "Short explanation"
}}

If nothing is relevant:

{{
    "selected_index": null,
    "confidence": 0.0,
    "reason": "No relevant model found"
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
                "model-selection LLM"
            )

            print(result_text)

            return None

        selected_index = result.get(
            "selected_index"
        )

        confidence = result.get(
            "confidence",
            0
        )

        print(
            f"Model confidence: {confidence}"
        )

        print(
            f"Reason: {result.get('reason')}"
        )

        if selected_index is None:
            return None

        if not isinstance(
            selected_index,
            int
        ):
            return None

        if (
            selected_index < 0
            or selected_index >= len(models)
        ):
            return None

        return models[
            selected_index
        ]

    # =========================================================
    # Find relevant model
    # =========================================================

    def _find_model(
        self,
        name,
        item_type
    ):

        models = self._search_models(
            name
        )

        if not models:

            print(
                "No Hugging Face models found."
            )

            return None

        print(
            f"Found {len(models)} "
            "candidate models."
        )

        return self._select_relevant_model(
            original_name=name,
            item_type=item_type,
            models=models
        )

    # =========================================================
    # Get model information
    # =========================================================

    def _get_model(
        self,
        model_id
    ):

        return self.api.model_info(
            model_id
        )

    # =========================================================
    # Get model card / README
    # =========================================================

    def _get_model_card(
        self,
        model_id
    ):

        url = (
            f"{self.base_url}/"
            f"{model_id}/raw/main/README.md"
        )

        print(
            f"Fetching model card: {url}"
        )

        try:

            response = requests.get(
                url,
                timeout=self.timeout
            )

            if response.status_code == 200:

                return response.text

            print(
                "WARNING: Model card not found."
            )

            return ""

        except Exception as e:

            print(
                f"WARNING: Model card fetch failed: {e}"
            )

            return ""

    # =========================================================
    # Summarize model card using OpenAI
    # =========================================================

    def _summarize_model_card(
        self,
        model_info,
        model_card
    ):

        description = getattr(
            model_info,
            "description",
            None
        )

        prompt = f"""
You are writing a newsletter brief for AI engineers,
researchers, and technical product readers.

Analyze this Hugging Face model and write a
newsletter-ready summary. This text will be published
as-is, so it must be accurate, complete, and easy to
read.

Model:
{model_info.id}

Description:
{description or "Not available"}

Model Card:
{model_card or "Model card not available"}

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
Important benchmarks only if the model card provides
them. If none are present, omit this section.

Maturity/status
Production-ready, experimental, research project, or
early-stage only if the model card supports it. If
not stated, omit this section.

Use those labels as short section headings. Under each
heading, write 1-3 tight newsletter sentences, not a
bullet dump. Keep the voice clear and useful.

STRICT REQUIREMENTS:

1. Total length must be about 200 words. Stay close to
   200 words. Do not go under 180 or over 220.
2. Do not drop important technical information: model
   names, parameter counts, context length, architecture
   details, protocols, supported tasks, modalities, and
   benchmark scores must be kept if they appear in the
   source.
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
understand the model without opening the model card.
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
    # Process model
    # =========================================================

    def _process_model(
        self,
        model,
        original_type,
        original_name
    ):

        model_id = model.id

        print(
            f"Selected model: {model_id}"
        )

        # -----------------------------------------------------
        # Get complete model information
        # -----------------------------------------------------

        model_info = self._get_model(
            model_id
        )

        # -----------------------------------------------------
        # Fetch model card
        # -----------------------------------------------------

        model_card = self._get_model_card(
            model_id
        )

        # -----------------------------------------------------
        # Summarize using LLM
        # -----------------------------------------------------

        print(
            "Generating model-card summary..."
        )

        summary = self._summarize_model_card(
            model_info=model_info,
            model_card=model_card
        )

        # -----------------------------------------------------
        # Extract metadata
        # -----------------------------------------------------

        downloads = getattr(
            model_info,
            "downloads",
            0
        )

        likes = getattr(
            model_info,
            "likes",
            0
        )

        trending_score = getattr(
            model_info,
            "trending_score",
            0
        )

        pipeline_tag = getattr(
            model_info,
            "pipeline_tag",
            None
        )

        tags = getattr(
            model_info,
            "tags",
            []
        )

        created_at = getattr(
            model_info,
            "created_at",
            None
        )

        last_modified = getattr(
            model_info,
            "last_modified",
            None
        )

        return {
            "type": original_type,

            "name": original_name,

            "source": "huggingface",

            "data": {

                "model": model_id,

                "description": getattr(
                    model_info,
                    "description",
                    None
                ),

                "readme": summary,

                "downloads": downloads,

                "likes": likes,

                "trending_score": (
                    trending_score
                ),

                "pipeline_tag": (
                    pipeline_tag
                ),

                "tags": tags,

                "created_at": str(
                    created_at
                ) if created_at else None,

                "last_modified": str(
                    last_modified
                ) if last_modified else None,

                "url": (
                    f"{self.base_url}/"
                    f"{model_id}"
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
        # MODEL
        # =====================================================

        if item_type == "model":

            # -------------------------------------------------
            # Direct model lookup
            # -------------------------------------------------

            try:

                model = self._get_model(
                    item_name
                )

            except Exception as e:

                print(
                    f"Model lookup failed: {e}"
                )

                model = None

            if model is None:

                return {
                    "type": item_type,
                    "name": item_name,
                    "source": "huggingface",
                    "data": None
                }

        # =====================================================
        # TAG / REPO
        # =====================================================

        else:

            model = self._find_model(
                name=item_name,
                item_type=item_type
            )

            if not model:

                print(
                    "No relevant Hugging Face "
                    "model found."
                )

                return {
                    "type": item_type,
                    "name": item_name,
                    "source": "huggingface",
                    "data": None
                }

        # =====================================================
        # Research model
        # =====================================================

        return self._process_model(
            model=model,
            original_type=item_type,
            original_name=item_name
        )


# =============================================================
# MAIN
# =============================================================

def main():

    tool = HuggingFaceSearchTool()

    items = [
        {
            "type": "tag",
            "name": "kimi k3"
        },
        {
            "type": "tag",
            "name": "generative ai is an engineering disaster"
        },
        {
            "type": "tag",
            "name": "jev llm"
        },
        {
            "type": "tag",
            "name": "ai agents executing unowned code"
        },
        {
            "type": "tag",
            "name": "openai ai agents wiki communication"
        },
        {
            "type": "repo",
            "name": "DietrichGebert/ponytail"
        },
        {
            "type": "repo",
            "name": "affaan-m/ECC"
        },
        {
            "type": "repo",
            "name": "alibaba/open-code-review"
        },
        {
            "type": "repo",
            "name": "cloudflare/security-audit-skill"
        },
        {
            "type": "repo",
            "name": "THU-MAIC/OpenMAIC"
        },
        {
            "type": "repo",
            "name": "obra/superpowers"
        },
        {
            "type": "repo",
            "name": "diegosouzapw/OmniRoute"
        },
        {
            "type": "repo",
            "name": "NousResearch/hermes-agent"
        },
        {
            "type": "model",
            "name": "convaiinnovations/laya"
        },
        {
            "type": "model",
            "name": "Qwen/Qwen-Image-2.1"
        },
        {
            "type": "model",
            "name": "abenzerps/Qwen-Image-2.1-Uncensored-GGUF"
        },
        {
            "type": "model",
            "name": "XingChen-AGI/Xing4.0-29B-A4B"
        },
        {
            "type": "model",
            "name": "Edge0/Audio8-ASR-Infinite"
        },
        {
            "type": "model",
            "name": "Altworld/Hemmingway-1"
        },
        {
            "type": "model",
            "name": "prism-ml/Ternary-Bonsai-2-27B-gguf"
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
