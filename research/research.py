"""
Research pipeline.

run_research() collects every discovery item into one Python
payload and returns that data structure. evaluation.py receives
the payload in memory. Each stage also writes a timestamped JSON
snapshot and log file under its own directory.

    payload = run_research()
    evaluator.evaluate_all(payload)


Payload:

{
  "items": [
    {
      "item": {"type": "...", "name": "..."},
      "research": {
        "github": { ... } | None,
        "huggingface": { ... } | None,
        "semantic_scholar": { "papers": [] },
        "huggingface_papers": { "papers": [] },
        "openaire": { "papers": [] }
      }
    }
  ]
}
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = Path(__file__).resolve().parent
DISCOVERY_DIR = ROOT / "discovery"

for path in (str(ROOT), str(DISCOVERY_DIR), str(RESEARCH_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from discovery import get_discovery_data
from pipeline_io import capture_stage, save_stage_result
from search_github import GitHubSearchTool
from search_huggingface import HuggingFaceSearchTool
from search_huggingface_papers import HuggingFacePapersSearchTool
from search_openaire import OpenAireSearchTool
from search_semantic_scholar import SemanticScholarSearchTool


def _tool_data(result):
    if not isinstance(result, dict):
        return None
    return result.get("data")


def _call_tool(name, tool, item):
    if tool is None:
        return None

    try:
        return _tool_data(tool.search(item))
    except Exception as e:
        print(f"WARNING: {name} research failed for {item}: {e}")
        return None


def _paper_result(name, tool, item):
    if tool is None:
        return {"papers": []}

    try:
        result = tool.search(item)
    except Exception as e:
        print(f"WARNING: {name} research failed for {item}: {e}")
        return {"papers": []}

    if isinstance(result, dict):
        if "papers" in result:
            return {"papers": result.get("papers") or []}
        data = result.get("data")
        if isinstance(data, dict) and "papers" in data:
            return {"papers": data.get("papers") or []}
        if isinstance(data, list):
            return {"papers": data}

    if isinstance(result, list):
        return {"papers": result}

    return {"papers": []}


def run_research(discovery_data=None):
    """
    Collect all research into one Python payload.

    Returns:
        dict: {"items": [research_item, ...]}
    """
    with capture_stage(RESEARCH_DIR, "research") as stage:
        if discovery_data is None:
            discovery_data = get_discovery_data()

        items = discovery_data.get("items", []) if isinstance(discovery_data, dict) else []
        print(f"Researching {len(items)} discovery items.")

        print("Initializing research tools...")
        github_tool = GitHubSearchTool()
        huggingface_tool = HuggingFaceSearchTool()
        semantic_scholar_tool = SemanticScholarSearchTool()
        huggingface_papers_tool = HuggingFacePapersSearchTool()
        openaire_tool = OpenAireSearchTool()
        print("Research tools ready.")

        researched = []

        for index, item in enumerate(items, start=1):
            print()
            print("=" * 80)
            print(f"[{index}/{len(items)}] Researching {item.get('type')}: {item.get('name')}")
            print("=" * 80)

            research = {
                "github": _call_tool("github", github_tool, item),
                "huggingface": _call_tool("huggingface", huggingface_tool, item),
                "semantic_scholar": _paper_result(
                    "semantic_scholar",
                    semantic_scholar_tool,
                    item,
                ),
                "huggingface_papers": _paper_result(
                    "huggingface_papers",
                    huggingface_papers_tool,
                    item,
                ),
                "openaire": _paper_result(
                    "openaire",
                    openaire_tool,
                    item,
                ),
            }

            github_name = (research["github"] or {}).get("repository") if research["github"] else None
            hf_name = (research["huggingface"] or {}).get("model") if research["huggingface"] else None
            paper_counts = {
                source: len((research[source] or {}).get("papers") or [])
                for source in ("semantic_scholar", "huggingface_papers", "openaire")
            }

            print()
            print(
                f"Summary for {item.get('name')}: "
                f"github={github_name or 'none'}, "
                f"huggingface={hf_name or 'none'}, "
                f"papers={paper_counts}"
            )

            researched.append({
                "item": item,
                "research": research,
            })

        payload = {
            "items": researched
        }

        print()
        print("=" * 80)
        print(f"RESEARCH COMPLETE: {len(researched)} items")
        print("=" * 80)

        save_stage_result(stage, payload)
        return payload


def main():
    payload = run_research()
    return payload


if __name__ == "__main__":
    main()
