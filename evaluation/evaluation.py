import json
import sys
from pathlib import Path

# from openai import OpenAI

EVALUATION_DIR = Path(__file__).resolve().parent
ROOT = EVALUATION_DIR.parent
RESEARCH_DIR = ROOT / "research"

for path in (str(ROOT), str(RESEARCH_DIR), str(ROOT / "discovery")):
    if path not in sys.path:
        sys.path.insert(0, path)

from env_loader import env
from paper_common import LLMClient, parse_json_text
from pipeline_io import capture_stage, save_stage_result


# Always keep the 8 highest final_score items, regardless of
# how high or low those scores are.
MAX_INCLUDED = 8


class ResearchEvaluator:

    def __init__(
        self,
        openai_api_key=None,
        openai_model=None
    ):
        # openai_api_key = openai_api_key or env("OPENAI_API_KEY")
        #
        # self.client = OpenAI(
        #     api_key=openai_api_key
        # )
        #
        # self.model = openai_model or env("OPENAI_MODEL")
        self.llm = LLMClient()

    # =========================================================
    # Evaluate one researched item
    # =========================================================

    def evaluate(self, research_item):
        """
        Score one researched discovery item.

        research_item must be one element of payload["items"]
        from run_research(). Pass the Python dict, not JSON.

        Expected input:
        {
            "item": {"type": "...", "name": "..."},
            "research": {
                "github": {...} | None,
                "huggingface": {...} | None,
                "semantic_scholar": {"papers": []},
                "huggingface_papers": {"papers": []},
                "openaire": {"papers": []}
            }
        }
        """

        if not isinstance(research_item, dict):
            raise ValueError(
                "research_item must be a dictionary"
            )

        item = research_item.get("item")

        research = research_item.get(
            "research",
            {}
        )

        if not item:
            raise ValueError(
                "Missing 'item'"
            )

        item_type = item.get("type")
        item_name = item.get("name")

        if not item_type or not item_name:
            raise ValueError(
                "item must contain type and name"
            )

        # -----------------------------------------------------
        # Convert research to JSON
        # -----------------------------------------------------

        research_json = json.dumps(
            research,
            indent=2,
            ensure_ascii=False
        )

        # -----------------------------------------------------
        # Evaluation prompt
        # -----------------------------------------------------

        prompt = f"""
You are the evaluation agent for a technical AI newsletter.

Your task is to evaluate ONE researched discovery item and
assign a score from 0 to 100.

The goal is NOT to determine whether the item is merely popular.

The goal is to determine whether this item deserves to be
included in a high-quality AI/technology newsletter.

DISCOVERY ITEM:

Type:
{item_type}

Name:
{item_name}

RESEARCH DATA:

{research_json}


============================================================
EVALUATION CRITERIA
============================================================

Evaluate the item using these six dimensions.

1. MOMENTUM — 20%

Determine whether the technology is gaining attention NOW.

Consider evidence such as:
- Google Trends information if available
- GitHub growth/activity
- Hugging Face trending score
- recent downloads
- recent likes
- recent research activity
- recent publication/activity dates

Do NOT confuse total popularity with recent momentum.


2. TECHNICAL SIGNIFICANCE — 20%

How technically important is this?

Consider:
- new architecture
- meaningful model capability
- important engineering innovation
- inference improvements
- agent capabilities
- reasoning
- multimodal capabilities
- infrastructure improvements
- important developer tooling
- meaningful performance improvements

A simple wrapper around an existing technology should score
lower than a genuinely significant technical development.


3. NOVELTY — 15%

How different or innovative is this compared with existing
technology?

Look for:
- new approaches
- new architectures
- new techniques
- unusual capabilities
- meaningful improvements over existing approaches

Do not give a high novelty score simply because something is
newly released.


4. COMMUNITY ADOPTION — 15%

Evaluate evidence of real-world interest.

Consider:
- GitHub stars
- GitHub forks
- GitHub activity
- Hugging Face downloads
- Hugging Face likes
- trending score
- community engagement

Do not blindly reward large absolute numbers because older
projects naturally have larger totals.


5. RESEARCH SIGNIFICANCE — 15%

Evaluate the research importance.

Consider:
- relevant research papers
- citations
- benchmark results
- research activity
- academic interest
- quality of supporting research

Recent research momentum should matter more than old citation
counts.


6. NEWSLETTER VALUE — 15%

This is extremely important.

Ask:

"If I publish this in an AI/technology newsletter, would a
technical reader find it useful or genuinely interesting?"

Consider:
- practical usefulness
- engineering relevance
- learning value
- story potential
- importance to AI developers/researchers
- breadth of impact
- ability to explain the technology clearly

Avoid selecting something merely because it is popular.


============================================================
IMPORTANT RULES
============================================================

1. Base your evaluation ONLY on the supplied research data.

2. Do NOT invent facts, metrics, papers, benchmarks, stars,
   downloads, or other information.

3. Missing information should reduce confidence, not be
   replaced with assumptions.

4. Separate popularity from technical importance.

5. A highly downloaded model is NOT automatically important.

6. A highly cited paper is NOT automatically currently
   relevant.

7. Recent momentum is especially important for this newsletter.

8. Consider the quality and credibility of the evidence.

9. If multiple sources support the same conclusion, this
   increases confidence.

10. If sources contradict each other, acknowledge the
    uncertainty.

11. The final score must be calculated using:

    momentum * 0.20
    + technical_significance * 0.20
    + novelty * 0.15
    + community_adoption * 0.15
    + research_significance * 0.15
    + newsletter_value * 0.15


============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "name": "{item_name}",
    "type": "{item_type}",

    "scores": {{
        "momentum": 0,
        "technical_significance": 0,
        "novelty": 0,
        "community_adoption": 0,
        "research_significance": 0,
        "newsletter_value": 0
    }},

    "final_score": 0,

    "confidence": 0,

    "decision": "include",

    "reason": "Short explanation of why this item is or is not valuable for the newsletter."
}}

Rules for output:

- Every score must be between 0 and 100.
- final_score must be calculated using the specified weights.
- confidence must be between 0 and 1.
- decision must be either "include" or "exclude".
- reason should be concise.
- Do not return Markdown.
- Do not return additional fields.
"""

        # -----------------------------------------------------
        # Call LLM
        # -----------------------------------------------------

        # response = self.client.responses.create(
        #     model=self.model,
        #     input=prompt
        # )
        #
        # result_text = response.output_text.strip()
        result_text = self.llm.complete(prompt)

        # -----------------------------------------------------
        # Parse JSON
        # -----------------------------------------------------

        try:
            # result = json.loads(
            #     result_text
            # )
            result = parse_json_text(
                result_text
            )

        except json.JSONDecodeError as e:

            raise ValueError(
                f"Invalid JSON returned by evaluator: {e}\n"
                f"Response: {result_text}"
            )

        # -----------------------------------------------------
        # Validate scores
        # -----------------------------------------------------

        scores = result.get(
            "scores",
            {}
        )

        required_scores = [
            "momentum",
            "technical_significance",
            "novelty",
            "community_adoption",
            "research_significance",
            "newsletter_value"
        ]

        for key in required_scores:

            if key not in scores:
                raise ValueError(
                    f"Missing score: {key}"
                )

            score = scores[key]

            if not isinstance(score, (int, float)):
                raise ValueError(
                    f"Invalid score for {key}"
                )

            if score < 0 or score > 100:
                raise ValueError(
                    f"Score for {key} must be between 0 and 100"
                )

        # -----------------------------------------------------
        # Calculate final score ourselves
        #
        # Do NOT trust the LLM to calculate this.
        # -----------------------------------------------------

        final_score = (
            scores["momentum"] * 0.20
            + scores["technical_significance"] * 0.20
            + scores["novelty"] * 0.15
            + scores["community_adoption"] * 0.15
            + scores["research_significance"] * 0.15
            + scores["newsletter_value"] * 0.15
        )

        result["final_score"] = round(
            final_score,
            2
        )

        return result

    def apply_cutoff(
        self,
        results,
        max_included=MAX_INCLUDED,
    ):
        """
        Include the top max_included items by final_score.
        Score value does not matter — rank does.
        """
        ranked = sorted(
            results,
            key=lambda item: item.get("final_score", 0),
            reverse=True,
        )

        for index, item in enumerate(ranked):
            if index < max_included:
                item["decision"] = "include"
            else:
                item["decision"] = "exclude"

        return ranked

    def evaluate_all(self, payload):
        """
        Evaluate every researched item, then return the top 8
        with scores plus the original research data (repo URL,
        stars, downloads, tags, readme, papers, etc.).
        """
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("items", [])
        else:
            raise ValueError(
                "payload must be {\"items\": [...]} or a list"
            )

        results = []

        with capture_stage(EVALUATION_DIR, "evaluation") as stage:
            print(f"Evaluating {len(items)} researched items.")

            for index, research_item in enumerate(items, start=1):
                item = research_item.get("item", {}) if isinstance(research_item, dict) else {}
                print()
                print("=" * 80)
                print(
                    f"[{index}/{len(items)}] Evaluating "
                    f"{item.get('type')}: {item.get('name')}"
                )
                print("=" * 80)

                scored = self.evaluate(research_item)

                if isinstance(research_item, dict):
                    scored["item"] = research_item.get("item")
                    scored["research"] = research_item.get("research")

                scores = scored.get("scores") or {}
                print(
                    f"Scores for {item.get('name')}: "
                    f"momentum={scores.get('momentum')}, "
                    f"technical={scores.get('technical_significance')}, "
                    f"novelty={scores.get('novelty')}, "
                    f"adoption={scores.get('community_adoption')}, "
                    f"research={scores.get('research_significance')}, "
                    f"newsletter={scores.get('newsletter_value')}, "
                    f"final={scored.get('final_score')}, "
                    f"decision={scored.get('decision')}"
                )
                print(f"Reason: {scored.get('reason')}")

                results.append(scored)

            ranked = self.apply_cutoff(results)
            selected = [
                item
                for item in ranked
                if item.get("decision") == "include"
            ]
            output = {
                "evaluated_count": len(results),
                "selected_count": len(selected),
                "items": selected,
            }

            print()
            print("=" * 80)
            print(
                f"EVALUATION COMPLETE: scored {output['evaluated_count']}, "
                f"selected top {output['selected_count']}"
            )
            print("=" * 80)
            for index, item in enumerate(selected, start=1):
                print(
                    f"{index}. [{item.get('type')}] {item.get('name')} "
                    f"(final_score={item.get('final_score')})"
                )

            save_stage_result(stage, output)
            return output


# =============================================================
# MAIN
# =============================================================

def main():
    from research import run_research

    evaluator = ResearchEvaluator()

    payload = run_research()
    output = evaluator.evaluate_all(payload)

    print()
    print("=" * 80)
    print(
        f"EVALUATION RESULT: "
        f"scored {output['evaluated_count']}, "
        f"selected top {output['selected_count']}"
    )
    print("=" * 80)

    print(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    return output


if __name__ == "__main__":
    main()
