from pytrends.request import TrendReq
import time
import requests
import json


# ============================================================
# CONFIGURATION
# ============================================================

TIMEFRAME = "today 3-m"
GEO = "US"

# GitHub Trending API endpoints
GITHUB_WEEKLY_URL = "https://raw.githubusercontent.com/isboyjc/github-trending-api/main/data/weekly/all.json"
GITHUB_MONTHLY_URL = "https://raw.githubusercontent.com/isboyjc/github-trending-api/main/data/monthly/all.json"

# Multiple seeds are important because searching only "AI"
# mostly returns model/company/product-related queries.
SEEDS = [
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


# ============================================================
# AI TECHNOLOGY KEYWORDS
# ============================================================

AI_TECH_KEYWORDS = [

    # --------------------------------------------------------
    # Agentic AI
    # --------------------------------------------------------
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
    "agent workflow",

    # --------------------------------------------------------
    # Agent Memory
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Agent Planning / Reasoning
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Multi-Agent Systems
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Tools / Actions
    # --------------------------------------------------------
    "tool use",
    "tool calling",
    "tool call",
    "function calling",
    "agent tools",
    "ai tools",
    "tool using agents",
    "action agent",

    # --------------------------------------------------------
    # Computer Use / Web Agents
    # --------------------------------------------------------
    "computer use",
    "computer use agent",
    "computer use agents",
    "browser agent",
    "browser agents",
    "web agent",
    "web agents",
    "web automation agent",
    "computer agent",

    # --------------------------------------------------------
    # MCP / Protocols
    # --------------------------------------------------------
    "mcp",
    "model context protocol",
    "mcp server",
    "mcp servers",
    "mcp client",
    "agent protocol",
    "agent protocols",
    "agent communication protocol",

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Context Engineering
    # --------------------------------------------------------
    "context engineering",
    "context management",
    "context window",
    "long context",
    "context compression",
    "context retrieval",
    "context aware",
    "context-aware",
    "context optimization",

    # --------------------------------------------------------
    # Knowledge
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # LLM / Models
    # --------------------------------------------------------
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
    "reasoning model",

    # --------------------------------------------------------
    # Model Infrastructure
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # AI Coding
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Safety / Reliability
    # --------------------------------------------------------
    "ai guardrails",
    "llm guardrails",
    "agent guardrails",
    "ai safety",
    "agent safety",
    "llm security",
    "agent security",
    "prompt injection",
    "agent security",
    "ai alignment",
    "model alignment",

    # --------------------------------------------------------
    # Observability
    # --------------------------------------------------------
    "llm observability",
    "ai observability",
    "agent observability",
    "agent monitoring",
    "llm tracing",
    "ai tracing",
    "agent tracing",
    "llm monitoring",

    # --------------------------------------------------------
    # Generative AI
    # --------------------------------------------------------
    "generative ai",
    "ai generation",
    "image generation",
    "video generation",
    "multimodal generation",
    "audio generation",
    "3d generation",

    # --------------------------------------------------------
    # AI Infrastructure
    # --------------------------------------------------------
    "ai infrastructure",
    "llm infrastructure",
    "ai infrastructure",
    "model serving",
    "distributed ai",
    "ai deployment",
    "llm deployment",

    # --------------------------------------------------------
    # Popular AI Models / Providers
    # --------------------------------------------------------
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


# ============================================================
# CHECK WHETHER QUERY IS AI TECHNOLOGY RELATED
# ============================================================

def is_ai_technology(query):

    query = query.lower().strip()

    return any(
        keyword in query
        for keyword in AI_TECH_KEYWORDS
    )


# ============================================================
# NORMALIZE QUERY
# ============================================================

def normalize_query(query):

    query = query.lower().strip()

    # Remove unnecessary whitespace
    query = " ".join(query.split())

    return query


# ============================================================
# GET RELATED QUERIES FOR ONE SEED
# ============================================================

def get_related_queries(pytrends, seed):

    try:

        print(f"Fetching trends for: {seed}")

        pytrends.build_payload(
            [seed],
            timeframe=TIMEFRAME,
            geo=GEO
        )

        result = pytrends.related_queries()

        if seed not in result:
            return []

        data = result[seed]

        queries = []

        # -----------------------------------------
        # Rising queries
        # -----------------------------------------

        rising = data.get("rising")

        if rising is not None:

            for _, row in rising.iterrows():

                queries.append({
                    "query": row["query"],
                    "value": row["value"],
                    "type": "rising",
                    "seed": seed
                })

        # -----------------------------------------
        # Top queries
        # -----------------------------------------

        top = data.get("top")

        if top is not None:

            for _, row in top.iterrows():

                queries.append({
                    "query": row["query"],
                    "value": row["value"],
                    "type": "top",
                    "seed": seed
                })

        return queries

    except Exception as e:

        print(
            f"WARNING: Failed for '{seed}': {e}"
        )

        return []


# ============================================================
# FILTER AI TECHNOLOGY QUERIES
# ============================================================

def filter_ai_technology(queries):

    filtered = []

    for item in queries:

        query = item["query"]

        if is_ai_technology(query):

            item["query"] = normalize_query(query)

            filtered.append(item)

    return filtered


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def deduplicate(queries):

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


# ============================================================
# FETCH GITHUB TRENDING REPOSITORIES
# ============================================================

def fetch_github_trending(url, time_period):

    try:

        print(f"Fetching GitHub trends: {time_period}")

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        repos = response.json()

        if not isinstance(repos, list):
            print(f"WARNING: Expected list from {time_period} GitHub API, got {type(repos)}")
            return []

        filtered_repos = []

        for repo in repos:

            repo_name = repo.get("repositoryName", "")
            description = repo.get("description", "") or ""
            stars = repo.get("stars", 0)

            combined_text = f"{repo_name} {description}".lower()

            if is_ai_technology(combined_text):

                filtered_repos.append({
                    "query": repo_name,
                    "value": stars,
                    "type": time_period,
                    "source": "github"
                })

        filtered_repos.sort(
            key=lambda x: x["value"],
            reverse=True
        )

        return filtered_repos

    except requests.exceptions.RequestException as e:

        print(f"WARNING: Failed to fetch GitHub {time_period} trends: {e}")
        return []

    except json.JSONDecodeError as e:

        print(f"WARNING: Failed to parse GitHub {time_period} JSON: {e}")
        return []


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print("        DYNAMIC AI TECHNOLOGY TREND DISCOVERY")
    print("=" * 75)
    print()

    pytrends = TrendReq(
        hl="en-US",
        tz=0
    )

    all_queries = []

    # --------------------------------------------------------
    # Collect trends from every seed
    # --------------------------------------------------------

    for seed in SEEDS:

        queries = get_related_queries(
            pytrends,
            seed
        )

        all_queries.extend(queries)

        # Avoid hitting Google Trends too aggressively
        time.sleep(2)


    print()
    print(
        f"Collected {len(all_queries)} raw queries."
    )


    # --------------------------------------------------------
    # Filter
    # --------------------------------------------------------

    filtered = filter_ai_technology(
        all_queries
    )


    print(
        f"Found {len(filtered)} AI technology queries."
    )


    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    trends = deduplicate(filtered)


    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    trends.sort(
        key=lambda x: x["value"],
        reverse=True
    )


    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print()
    print("=" * 75)
    print("              AI TECHNOLOGY TRENDS (GOOGLE)")
    print("=" * 75)
    print()

    for i, item in enumerate(trends, 1):

        print(
            f"{i:3}. "
            f"{item['query']:<45} "
            f"{str(item['value']):>8} "
            f"[{item['type']}]"
        )


    print()
    print("=" * 75)
    print(
        f"TOTAL GOOGLE TRENDS TOPICS: {len(trends)}"
    )
    print("=" * 75)


    # ========================================================
    # FETCH AND DISPLAY GITHUB TRENDING
    # ========================================================

    print()
    print("=" * 75)
    print("        GITHUB TRENDING AI REPOSITORIES")
    print("=" * 75)
    print()

    github_repos = []

    weekly_repos = fetch_github_trending(
        GITHUB_WEEKLY_URL,
        "weekly"
    )

    github_repos.extend(weekly_repos)

    time.sleep(2)

    # monthly_repos = fetch_github_trending(
    #     GITHUB_MONTHLY_URL,
    #     "monthly"
    # )
    #
    # github_repos.extend(monthly_repos)

    if github_repos:

        for i, repo in enumerate(github_repos, 1):

            print(
                f"{i:3}. "
                f"{repo['query']:<45} "
                f"{str(repo['value']):>8} "
                f"[{repo['type']}]"
            )

        print()
        print("=" * 75)
        print(
            f"TOTAL GITHUB REPOSITORIES: {len(github_repos)}"
        )
        print("=" * 75)

    else:

        print("No AI-related repositories found.")
        print("=" * 75)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
