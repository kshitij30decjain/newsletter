import json
from huggingface_hub import HfApi


class HuggingFaceModelDiscovery:

    def __init__(
        self,
        top_n=7,
        search_limit=100
    ):
        self.top_n = top_n
        self.search_limit = search_limit

        self.api = HfApi()

        # AI topics for discovery
        self.search_terms = [

            # Agentic AI
            "AI agent",
            "agentic AI",
            "autonomous agent",
            "agent framework",
            "agent orchestration",

            # Memory
            "AI memory",
            "agent memory",
            "long term memory",

            # Reasoning
            "reasoning model",
            "reasoning AI",
            "AI planning",

            # Multi-agent
            "multi agent",
            "multi agent system",

            # Tools
            "tool calling",
            "function calling",
            "agent tools",

            # Computer / Web agents
            "computer use",
            "browser agent",
            "web agent",

            # MCP
            "MCP",
            "Model Context Protocol",

            # RAG
            "RAG",
            "agentic RAG",
            "graph RAG",

            # Context
            "context engineering",
            "context management",
            "long context",

            # Knowledge
            "knowledge graph",
            "embeddings",
            "embedding model",
            "reranker",
            "semantic search",

            # Models
            "LLM",
            "large language model",
            "foundation model",
            "multimodal AI",
            "small language model",

            # Inference
            "LLM inference",
            "model serving",
            "quantization",
            "inference optimization",

            # AI Coding
            "AI coding",
            "coding agent",
            "code agent",
            "software engineering agent",

            # Evaluation
            "LLM evaluation",
            "AI evaluation",
            "agent evaluation",
            "LLM benchmark",

            # Safety
            "AI safety",
            "LLM security",
            "AI guardrails",
            "prompt injection",

            # Observability
            "LLM observability",
            "AI observability",
            "LLM tracing",

            # Generative AI
            "generative AI",
            "image generation",
            "video generation",
            "audio generation",

            # Vision
            "computer vision",
            "vision language model",
            "visual reasoning",

            # Speech
            "speech AI",
            "voice AI",
            "text to speech",
            "speech recognition",

            # Robotics
            "embodied AI",
            "robotics AI",
            "vision language action",

            # Training
            "fine tuning",
            "LoRA",
            "QLoRA",
            "RLHF",
            "DPO",

            # Infrastructure
            "AI infrastructure",
            "LLM infrastructure",
            "AI deployment",

            # Popular models/providers
            "GPT",
            "Gemini",
            "Claude",
            "Llama",
            "Qwen",
            "DeepSeek",
            "Mistral",
            "Kimi",
        ]

    # ---------------------------------------------------------
    # Discover models
    # ---------------------------------------------------------

    def _discover_models(self):

        models = {}

        for search_term in self.search_terms:

            print(
                f"Searching Hugging Face: {search_term}"
            )

            try:

                results = self.api.list_models(
                    search=search_term,
                    limit=self.search_limit
                )

                results = list(results)

                # Sort by trending score
                results.sort(
                    key=lambda model:
                        getattr(
                            model,
                            "trending_score",
                            0
                        ) or 0,
                    reverse=True
                )

                # Deduplicate models
                for model in results:
                    models[model.id] = model

            except Exception as e:

                print(
                    f"Failed for {search_term}: {e}"
                )

        return list(models.values())

    # ---------------------------------------------------------
    # Run discovery
    # ---------------------------------------------------------

    def run(self):

        print()
        print("=" * 80)
        print("       HUGGING FACE TRENDING AI MODELS")
        print("=" * 80)

        # Discover models
        models = self._discover_models()

        print()
        print(
            f"Unique models discovered: {len(models)}"
        )

        # Sort all discovered models by trending score
        models.sort(
            key=lambda model:
                getattr(
                    model,
                    "trending_score",
                    0
                ) or 0,
            reverse=True
        )

        # Select top N
        top_models = models[:self.top_n]

        # -----------------------------------------------------
        # Return ONLY model names
        # -----------------------------------------------------

        tags = [
            model.id
            for model in top_models
        ]

        print()
        print("=" * 80)
        print("        TOP TRENDING HUGGING FACE MODELS")
        print("=" * 80)

        for index, model in enumerate(top_models, start=1):
            print()
            print(f"{index}. {model.id}")
            print(f"   Trending score: {getattr(model, 'trending_score', 0)}")
            print(f"   Downloads: {getattr(model, 'downloads', 0)}")
            print(f"   Likes: {getattr(model, 'likes', 0)}")
            print(f"   Pipeline: {getattr(model, 'pipeline_tag', None)}")

        print()
        print(f"Selected {len(tags)} Hugging Face models.")

        return {
            "tags": tags
        }


# =============================================================
# MAIN
# =============================================================

def main():

    discovery = HuggingFaceModelDiscovery(
        top_n=7,
        search_limit=100
    )

    result = discovery.run()

    print()
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    print(
        json.dumps(
            result,
            indent=4
        )
    )


if __name__ == "__main__":
    main()
