from pytrends.request import TrendReq
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_loader import env, env_int


def _is_rate_limited(error):
    text = str(error).lower()
    return (
        "429" in text
        or "too many requests" in text
        or type(error).__name__.lower() == "toomanyrequestserror"
    )


class GoogleTrendsDiscovery:
    """
    Discovers trending AI technology topics using Google Trends.

    Returns:
    {
        "tags": [
            {
                "query": "...",
                "value": 100,
                "type": "rising",
                "seed": "AI"
            }
        ]
    }
    """

    def __init__(
        self,
        timeframe="today 3-m",
        geo="US",
        top_n=5,
        request_delay=5
    ):
        self.timeframe = timeframe
        self.geo = geo
        self.top_n = top_n
        self.request_delay = request_delay

        self.pytrends = TrendReq(
            hl="en-US",
            tz=0
        )

        self.seeds = [
            "AI",
            "AI agents",
            "agentic AI",
            "LLM",
            "RAG",
            "MCP",
            "generative AI",
            "multimodal AI",
            "AI coding",
            "AI automation",
        ]

        self.ai_technology_keywords = [
            # Agentic AI
            "agent",
            "agents",
            "agentic",
            "agentic ai",
            "autonomous agent",
            "autonomous agents",
            "ai agent",
            "ai agents",
            "agent framework",
            "agent architecture",
            "agent workflow",
            "agent orchestration",
            "agentic workflow",

            # Memory
            "agent memory",
            "ai memory",
            "long term memory",
            "long-term memory",
            "short term memory",
            "short-term memory",
            "episodic memory",
            "semantic memory",
            "working memory",
            "persistent memory",
            "memory system",
            "memory systems",
            "memory architecture",
            "memory retrieval",
            "memory management",

            # Reasoning
            "agent planning",
            "ai planning",
            "task planning",
            "planning agent",
            "reasoning",
            "reasoning model",
            "reasoning models",
            "reasoning ai",
            "chain of thought",
            "goal oriented agent",
            "goal-oriented agent",

            # Multi-agent
            "multi agent",
            "multi-agent",
            "multi agent system",
            "multi-agent system",
            "multi agent systems",
            "multi-agent systems",
            "multi agent collaboration",
            "agent collaboration",
            "agent communication",
            "agent coordination",

            # Tools
            "tool use",
            "tool calling",
            "tool call",
            "function calling",
            "agent tools",
            "ai tools",
            "tool using agents",
            "action agent",

            # Computer / Web agents
            "computer use",
            "computer use agent",
            "computer use agents",
            "browser agent",
            "browser agents",
            "web agent",
            "web agents",
            "web automation agent",
            "computer agent",

            # MCP
            "mcp",
            "model context protocol",
            "mcp server",
            "mcp servers",
            "mcp client",
            "agent protocol",
            "agent protocols",
            "agent communication protocol",

            # RAG
            "rag",
            "retrieval augmented generation",
            "retrieval-augmented generation",
            "agentic rag",
            "agentic retrieval",
            "graph rag",
            "graph-rag",
            "multimodal rag",
            "rag agent",
            "retrieval agent",
            "adaptive rag",
            "self rag",
            "self-rag",
            "corrective rag",
            "crag",

            # Context
            "context engineering",
            "context management",
            "context window",
            "long context",
            "context compression",
            "context retrieval",
            "context aware",
            "context-aware",
            "context optimization",

            # Knowledge
            "knowledge graph",
            "knowledge graphs",
            "knowledge base",
            "knowledge bases",
            "vector database",
            "vector databases",
            "vector db",
            "embeddings",
            "embedding model",
            "embedding models",
            "semantic search",
            "hybrid search",
            "knowledge retrieval",

            # Models
            "llm",
            "large language model",
            "large language models",
            "foundation model",
            "foundation models",
            "multimodal",
            "multimodal ai",
            "vision language model",
            "vision-language model",
            "small language model",
            "small language models",

            # Inference
            "llm inference",
            "inference",
            "model serving",
            "llm serving",
            "llm optimization",
            "model optimization",
            "quantization",
            "speculative decoding",
            "inference optimization",
            "gpu inference",
            "distributed inference",

            # AI Coding
            "ai coding",
            "ai coding agent",
            "ai coding agents",
            "coding agent",
            "coding agents",
            "code agent",
            "code agents",
            "software engineering agent",
            "software engineering agents",
            "code generation",
            "ai programmer",

            # Evaluation
            "llm evaluation",
            "ai evaluation",
            "agent evaluation",
            "agent evaluations",
            "agent benchmark",
            "agent benchmarks",
            "llm benchmark",
            "llm benchmarks",
            "ai benchmark",
            "ai benchmarks",
            "agent testing",
            "llm testing",

            # Safety
            "ai guardrails",
            "llm guardrails",
            "agent guardrails",
            "ai safety",
            "agent safety",
            "llm security",
            "agent security",
            "prompt injection",
            "ai alignment",
            "model alignment",

            # Observability
            "llm observability",
            "ai observability",
            "agent observability",
            "agent monitoring",
            "llm tracing",
            "ai tracing",
            "agent tracing",
            "llm monitoring",

            # Generative AI
            "generative ai",
            "ai generation",
            "image generation",
            "video generation",
            "multimodal generation",
            "audio generation",
            "3d generation",

            # Infrastructure
            "ai infrastructure",
            "llm infrastructure",
            "distributed ai",
            "ai deployment",
            "llm deployment",

            # Popular models / providers
            "gpt",
            "gemini",
            "claude",
            "llama",
            "qwen",
            "deepseek",
            "mistral",
            "kimi",
            "openai",
            "anthropic",
        ]

        self.ai_technology_keywords = [
            keyword.lower()
            for keyword in self.ai_technology_keywords
        ]

    # --------------------------------------------------------
    # Check whether a query is AI-related
    # --------------------------------------------------------

    def is_ai_technology(self, query):
        query = query.lower().strip()

        return any(
            keyword in query
            for keyword in self.ai_technology_keywords
        )

    # --------------------------------------------------------
    # Normalize query
    # --------------------------------------------------------

    def normalize_query(self, query):
        query = query.lower().strip()
        return " ".join(query.split())

    # --------------------------------------------------------
    # Get related queries for one seed
    # --------------------------------------------------------

    def get_related_queries(self, seed):

        try:
            print(f"Fetching Google Trends for: {seed}")

            self.pytrends.build_payload(
                [seed],
                timeframe=self.timeframe,
                geo=self.geo
            )

            result = self.pytrends.related_queries()

            if seed not in result:
                return []

            data = result[seed]

            queries = []

            # Rising queries
            rising = data.get("rising")

            if rising is not None:

                for _, row in rising.iterrows():

                    queries.append({
                        "query": row["query"],
                        "value": int(row["value"]),
                        "type": "rising",
                        "seed": seed
                    })

            # Top queries
            top = data.get("top")

            if top is not None:

                for _, row in top.iterrows():

                    queries.append({
                        "query": row["query"],
                        "value": int(row["value"]),
                        "type": "top",
                        "seed": seed
                    })

            return queries

        except Exception as e:

            print(
                f"WARNING: Failed for '{seed}': {e}"
            )

            return []

    # --------------------------------------------------------
    # Filter AI technology queries
    # --------------------------------------------------------

    def filter_ai_technology(self, queries):

        filtered = []

        for item in queries:

            query = item["query"]

            if self.is_ai_technology(query):

                item = item.copy()

                item["query"] = self.normalize_query(
                    query
                )

                filtered.append(item)

        return filtered

    # --------------------------------------------------------
    # Remove duplicate queries
    # --------------------------------------------------------

    def deduplicate(self, queries):

        seen = {}

        for item in queries:

            query = item["query"]

            if query not in seen:

                seen[query] = item

            else:

                # Keep the highest trend value
                if item["value"] > seen[query]["value"]:

                    seen[query] = item

        return list(seen.values())

    # --------------------------------------------------------
    # Main discovery function
    # --------------------------------------------------------

    def run(self):

        print()
        print("=" * 70)
        print("       GOOGLE TRENDS AI DISCOVERY")
        print("=" * 70)

        all_queries = []

        # Collect trends
        for seed in self.seeds:

            queries = self.get_related_queries(seed)

            all_queries.extend(queries)

            time.sleep(self.request_delay)

        print(
            f"\nCollected {len(all_queries)} raw queries."
        )

        # Filter
        filtered = self.filter_ai_technology(
            all_queries
        )

        print(
            f"Found {len(filtered)} AI-related queries."
        )

        # Deduplicate
        trends = self.deduplicate(filtered)

        # Sort by trend value
        trends.sort(
            key=lambda x: x["value"],
            reverse=True
        )

        # Select top N
        top_trends = trends[:self.top_n]

        # Return the interface expected by
        # the rest of your agentic pipeline.
        result = {
            "tags": top_trends
        }

        print(
            f"Selected {len(top_trends)} trends."
        )

        for index, tag in enumerate(top_trends, start=1):
            print(
                f"{index}. {tag.get('query')} "
                f"(value={tag.get('value')}, type={tag.get('type')})"
            )

        return result


# Alias used by discovery.py
GoogleTrendDiscovery = GoogleTrendsDiscovery


def main():

    discovery = GoogleTrendsDiscovery(
        timeframe="today 3-m",
        geo="US",
        top_n=5
    )

    result = discovery.run()

    print(result)

    # Access the 5 tags
    tags = result["tags"]

    for tag in tags:
        print(tag["query"])


if __name__ == "__main__":
    main()

