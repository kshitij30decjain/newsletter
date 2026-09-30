"""Render selected newsletter items as an email-safe HTML and plain-text issue.

The input is the dictionary returned by ``ResearchEvaluator.evaluate_all``.
The renderer intentionally has no email-provider dependency: a delivery service
can attach the generated HTML as ``text/html`` and the text version as
``text/plain`` in a multipart/alternative email.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any


MAX_ITEMS = 8
DEFAULT_TITLE = "Dev AI Brief"
DEFAULT_INTRO = (
    "Trending AI topics, fast-growing GitHub repositories, Hugging Face models, "
    "and research papers—curated weekly for developers."
)


def _as_text(value: Any) -> str:
    """Return readable, untrusted source text without allowing HTML injection."""
    if value is None:
        return ""
    return str(value).strip()


def _strip_markdown(text: str) -> str:
    """Make LLM summaries readable in a plain-text email without parsing HTML."""
    text = re.sub(r"!?(?:\[([^\]]+)\]\([^)]*\))", r"\1", text)
    text = re.sub(r"[*_`#]", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _brief(text: str, limit: int = 250) -> str:
    """Create a compact card description from a longer research summary."""
    text = _strip_markdown(text)
    text = re.sub(r"\b(What is it\?|Problem solved|How does it work\?|Who should use it\?|Why is it useful\?|Key capabilities|Performance|Maturity/status)\s*", "", text)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{shortened}…"


def _source_for(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """Choose the most direct source and summary from the research payload."""
    research = item.get("research") or {}
    github = research.get("github") or {}
    huggingface = research.get("huggingface") or {}
    fallback: tuple[str, str, str, str, str] | None = None

    for data, label, name_key in (
        (github, "GitHub", "repository"),
        (huggingface, "Hugging Face", "model"),
    ):
        if not isinstance(data, dict):
            continue
        url = _as_text(data.get("url"))
        name = _as_text(data.get(name_key))
        summary = _as_text(data.get("readme") or data.get("description"))
        if url or summary or name:
            stars = f"{int(data['stars']):,}" if isinstance(data.get("stars"), (int, float)) else "—"
            forks = f"{int(data['forks']):,}" if isinstance(data.get("forks"), (int, float)) else "—"
            candidate = (label, url, summary, stars, forks)
            if summary:
                return candidate
            fallback = fallback or candidate

    return fallback or ("Source", "", "", "—", "—")


def _research_links(item: dict[str, Any]) -> list[tuple[str, str]]:
    """Collect every supported external source URL from an item's research data."""
    research = item.get("research") or {}
    if not isinstance(research, dict):
        return []

    links: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(label: str, value: Any) -> None:
        url = _as_text(value)
        if url.startswith(("https://", "http://")) and url not in seen:
            links.append((label, url))
            seen.add(url)

    for key, label in (("github", "GitHub"), ("huggingface", "Hugging Face")):
        data = research.get(key)
        if isinstance(data, dict):
            add(label, data.get("url"))

    for key, label in (
        ("semantic_scholar", "Semantic Scholar"),
        ("huggingface_papers", "Hugging Face Paper"),
        ("openaire", "OpenAIRE Paper"),
    ):
        data = research.get(key)
        papers = data.get("papers", []) if isinstance(data, dict) else data
        if not isinstance(papers, list):
            continue
        for index, paper in enumerate(papers, start=1):
            if not isinstance(paper, dict):
                continue
            url = paper.get("url") or paper.get("paper_url") or paper.get("link")
            if not url and isinstance(paper.get("openAccessPdf"), dict):
                url = paper["openAccessPdf"].get("url")
            title = _as_text(paper.get("title"))
            add(f"{label}: {title}" if title else f"{label} {index}", url)

    return links


def _source_icon(label: str) -> str:
    """Return a self-contained, accessible visual mark for a research source."""
    if label == "GitHub":
        return (
            '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
            '<path fill="currentColor" d="M8 0a8 8 0 0 0-2.53 15.59c.4.07.55-.17.55-.38v-1.49'
            'c-2.24.49-2.71-1.08-2.71-1.08-.36-.93-.9-1.18-.9-1.18-.73-.5.06-.49.06-.49'
            ' .81.06 1.24.83 1.24.83.72 1.23 1.89.88 2.35.67.07-.52.28-.88.51-1.08-1.79-.2'
            '-3.67-.9-3.67-3.99 0-.88.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.13 0 0 .67-.21 '
            '2.2.82A7.62 7.62 0 0 1 8 1.99c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.11'
            '.16 1.93.08 2.13.51.56.82 1.27.82 2.15 0 3.1-1.89 3.78-3.68 3.98.29.25.54.73'
            '.54 1.47v2.18c0 .21.14.46.55.38A8 8 0 0 0 8 0Z"/></svg>'
        )
    if label == "Hugging Face":
        return "<span aria-hidden=\"true\">🤗</span>"
    if label.startswith("Semantic Scholar"):
        return "<span aria-hidden=\"true\">🔎</span>"
    if label.startswith("Hugging Face Paper"):
        return "<span aria-hidden=\"true\">🤗</span>"
    return "<span aria-hidden=\"true\">📄</span>"


def _item_view(item: dict[str, Any], position: int) -> dict[str, Any]:
    original = item.get("item") or {}
    name = _as_text(item.get("name") or original.get("name") or "Untitled item")
    kind = _as_text(item.get("type") or original.get("type") or "technology").title()
    source_label, source_url, summary, stars, forks = _source_for(item)
    score = item.get("final_score")
    score_text = f"{float(score):.1f}/100" if isinstance(score, (int, float)) else "Unscored"
    reason = _as_text(item.get("reason"))
    return {
        "position": str(position),
        "name": name,
        "kind": kind,
        "source_label": source_label,
        "source_url": source_url,
        "source_links": _research_links(item),
        "stars": stars,
        "forks": forks,
        "summary": _brief(summary),
        "reason": reason,
        "score": score_text,
    }


def _evaluation_payload(evaluation_output: dict[str, Any]) -> dict[str, Any]:
    """Accept evaluate_all output or a saved stage file that wraps it in ``result``."""
    if not isinstance(evaluation_output, dict):
        raise ValueError("evaluation_output must be a dictionary")
    if isinstance(evaluation_output.get("items"), list):
        return evaluation_output
    result = evaluation_output.get("result")
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return result
    raise ValueError("evaluation_output must contain an 'items' list")


def _selected_items(evaluation_output: dict[str, Any]) -> list[dict[str, Any]]:
    items = _evaluation_payload(evaluation_output)["items"]
    return [item for item in items if isinstance(item, dict)][:MAX_ITEMS]


def _number(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _stats(items: list[dict[str, Any]]) -> dict[str, str]:
    """Build the limited, source-backed side-panel statistics for this issue."""
    github = [item.get("research", {}).get("github") or {} for item in items]
    huggingface = [item.get("research", {}).get("huggingface") or {} for item in items]
    github = [data for data in github if isinstance(data, dict) and data.get("repository")]
    huggingface = [data for data in huggingface if isinstance(data, dict) and data.get("model")]
    scores = [item.get("final_score") for item in items if isinstance(item.get("final_score"), (int, float))]
    return {
        "repositories": str(len(github)),
        "stars": f"{sum(_number(data.get('stars')) for data in github):,}",
        "models": str(len(huggingface)),
        "downloads": f"{sum(_number(data.get('downloads')) for data in huggingface):,}",
        "signals": str(len(items)),
        "average_score": f"{sum(scores) / len(scores):.1f}" if scores else "—",
    }


def _model_downloads(items: list[dict[str, Any]]) -> list[tuple[str, int, int]]:
    """Return selected Hugging Face models and their current downloads and likes."""
    models: dict[str, tuple[int, int]] = {}
    for item in items:
        data = (item.get("research") or {}).get("huggingface") or {}
        if not isinstance(data, dict) or not data.get("model"):
            continue
        model = _as_text(data["model"])
        downloads = _number(data.get("downloads"))
        likes = _number(data.get("likes"))
        old_downloads, old_likes = models.get(model, (0, 0))
        models[model] = (max(old_downloads, downloads), max(old_likes, likes))
    return sorted(
        ((model, downloads, likes) for model, (downloads, likes) in models.items()),
        key=lambda model: model[1],
        reverse=True,
    )


def _tldr(views: list[dict[str, str]]) -> str:
    """Use the evaluator's supplied reasons rather than inventing a weekly thesis."""
    summaries = [view["reason"] or view["name"] for view in views[:4]]
    return " · ".join(summaries)


def render_newsletter(
    evaluation_output: dict[str, Any],
    *,
    issue_date: date | None = None,
    title: str = DEFAULT_TITLE,
    intro: str = DEFAULT_INTRO,
) -> tuple[str, str]:
    """Return ``(html_body, plain_text_body)`` for up to eight selected items."""
    issue_date = issue_date or date.today()
    views = [_item_view(item, index) for index, item in enumerate(_selected_items(evaluation_output), 1)]
    if not views:
        raise ValueError("Cannot render an issue without selected items")

    stats = _stats(_selected_items(evaluation_output))
    model_downloads = _model_downloads(_selected_items(evaluation_output))
    html_cards: list[str] = []
    text_cards: list[str] = []
    for view in views:
        source_links = "".join(
            f'<a class="source-link" href="{html.escape(url, quote=True)}" '
            f'title="{html.escape(label, quote=True)}" aria-label="{html.escape(label, quote=True)}">'
            f'{_source_icon(label)}</a>'
            for label, url in view["source_links"]
        )
        summary = html.escape(view["summary"])
        reason = html.escape(view["reason"])
        html_cards.append(
            f'''<article class="signal-card">
  <div class="signal-number">{view["position"]}</div>
  <div class="signal-content">
    <div class="eyebrow">{html.escape(view["kind"])} <span>•</span> Top signal #{view["position"]}</div>
    <h2>{html.escape(view["name"])}</h2>
    <p class="summary">{summary or "A selected development with source details available below."}</p>
    {f'<p class="why"><strong>Why it matters:</strong> {reason}</p>' if reason else ''}
    {f'<div class="source-links"><span class="source-label">Sources:</span>{source_links}</div>' if source_links else ''}
  </div>
  <div class="momentum"><span>Momentum</span><strong>{view["score"]}</strong></div>
</article>'''
        )

        text_card = f"{view['position']}. {view['name']} ({view['kind']}; score {view['score']})"
        if view["summary"]:
            text_card += f"\n{view['summary']}"
        if view["reason"]:
            text_card += f"\nWhy it matters: {view['reason']}"
        for label, url in view["source_links"]:
            text_card += f"\n{label}: {url}"
        text_cards.append(text_card)

    safe_title = html.escape(_as_text(title) or DEFAULT_TITLE)
    safe_intro = html.escape(_as_text(intro) or DEFAULT_INTRO)
    hero_title = safe_title.replace("AI", "<span>AI</span>", 1)
    issue_label = f"Week of {issue_date.strftime('%B')} {issue_date.day}, {issue_date.year}"
    html_body = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  @page {{ size:A3 landscape; margin:8mm; }} :root {{ color-scheme: light; }} * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#f5f9ff; color:#102044; font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  .page {{ max-width:1440px; margin:0 auto; padding:16px; }}
  .hero {{ overflow:hidden; position:relative; min-height:210px; padding:28px 34px; border-radius:18px; color:#fff; background:radial-gradient(circle at 88% 15%,#18b9a4 0,transparent 24%),linear-gradient(116deg,#032a32 4%,#075866 54%,#063340 100%); }}
  .hero:after {{ content:""; position:absolute; pointer-events:none; inset:auto -4% 0 39%; height:68%; opacity:.45; background:linear-gradient(145deg,transparent 29%,#0b4550 30% 45%,transparent 46%) 0 0/320px 100%,linear-gradient(35deg,transparent 35%,#0f796f 36% 48%,transparent 49%) 180px 0/360px 100%; clip-path:polygon(0 100%,13% 37%,27% 67%,43% 7%,59% 58%,70% 30%,86% 75%,100% 45%,100% 100%); }}
  .issue-meta {{ position:absolute; z-index:1; top:27px; right:34px; font-size:13px; color:#e7e9ff; }}
  .hero-content {{ position:relative; z-index:1; max-width:790px; }} .hero h1 {{ margin:0; font-size:clamp(38px,6vw,66px); line-height:.95; letter-spacing:-.055em; }}
  .hero h1 span {{ color:#66f2d2; }} .tagline {{ margin:15px 0 8px; font-size:20px; }} .hero-copy {{ max-width:680px; margin:0; color:#d9fffa; line-height:1.5; }}
  .tldr {{ display:flex; align-items:flex-start; gap:16px; margin:14px 0 20px; padding:18px 22px; border:1px solid #cbece8; border-radius:15px; background:linear-gradient(100deg,#e9fbf8,#f7fffd); }}
  .tldr-icon {{ font-size:25px; }} .tldr h2 {{ margin:0 0 4px; font-size:18px; }} .tldr p {{ margin:0; font-size:14px; line-height:1.45; color:#294060; }}
  .layout {{ display:flex; flex-wrap:nowrap; gap:20px; align-items:flex-start; }} .main-column {{ flex:1 1 0; min-width:0; }} .layout aside {{ flex:0 0 340px; width:340px; }}
  .section-title {{ margin:0 0 13px; font-size:25px; letter-spacing:-.04em; }}
  .signal-card {{ position:relative; display:grid; grid-template-columns:42px minmax(0,1fr) auto; gap:13px; margin-bottom:12px; padding:18px; border:1px solid #d5ece9; border-radius:15px; background:linear-gradient(110deg,#fff,#f1fbf9); box-shadow:0 5px 16px rgba(18,103,98,.07); break-inside:avoid; page-break-inside:avoid; }}
  .signal-number {{ display:grid; place-items:center; width:34px; height:34px; border-radius:8px; background:linear-gradient(135deg,#008d88,#12b89f); color:#fff; font-weight:800; font-size:18px; }}
  .eyebrow {{ color:#547092; font-size:11px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }} .eyebrow span {{ color:#b8c9dd; }}
  .signal-card h2 {{ margin:4px 0 8px; font-size:18px; letter-spacing:-.025em; line-height:1.2; }} .summary,.why {{ margin:0; color:#334967; font-size:14px; line-height:1.55; }} .why {{ margin-top:8px; color:#17375f; }}
  .source-links {{ display:flex; flex-wrap:wrap; align-items:center; gap:7px 9px; margin-top:12px; }} .source-label {{ color:#61758f; font-size:12px; font-weight:750; }} .source-link {{ display:grid; place-items:center; width:25px; height:25px; border:1px solid #cbe7e1; border-radius:7px; color:#007b72; font-size:15px; text-decoration:none; }} .source-link:hover {{ background:#e4f7f3; }} .source-link svg {{ width:15px; height:15px; }}
  .momentum {{ align-self:start; min-width:95px; padding:7px 10px; border-radius:999px; background:#dff8ee; color:#087b57; text-align:center; white-space:nowrap; }} .momentum span {{ display:block; font-size:10px; font-weight:700; }} .momentum strong {{ font-size:13px; }}
  .rail-card {{ margin-bottom:13px; padding:18px; border:1px solid #d5ece9; border-radius:15px; background:#fff; box-shadow:0 5px 16px rgba(18,103,98,.07); }} .rail-card h3 {{ margin:0 0 13px; font-size:17px; letter-spacing:-.025em; }}
  .metric {{ display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid #e9eff7; color:#40536d; font-size:13px; }} .metric:last-child {{ border:0; }} .metric strong {{ color:#089563; }}
  .mini-list {{ list-style:none; padding:0; margin:0; }} .mini-list li {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding:10px 0; border-bottom:1px solid #e9eff7; }} .mini-list li:last-child {{ border:0; }} .project-details {{ min-width:0; }} .mini-list a,.model-name {{ color:#19345a; text-decoration:none; font-size:13px; font-weight:700; }} .mini-list span {{ display:block; margin-top:3px; color:#61758f; font-size:12px; }} .star-count,.download-count {{ flex:0 0 auto; color:#089563; font-size:12px; white-space:nowrap; }} .rail-note {{ margin:9px 0 0; color:#61758f; font-size:11px; line-height:1.4; }}
  footer {{ padding:22px 4px 10px; color:#74839a; font-size:12px; text-align:center; }} footer a {{ color:#506b8e; }}
  @media print {{ .page {{ max-width:1440px; padding:0; }} .layout {{ display:flex !important; flex-wrap:nowrap !important; }} .main-column {{ flex:1 1 0 !important; min-width:0 !important; }} .layout aside {{ display:block !important; flex:0 0 340px !important; width:340px !important; }} .hero,.tldr,.rail-card {{ break-inside:avoid; page-break-inside:avoid; }} }}
  @media (max-width:800px) {{ .page {{ padding:10px; }} .hero {{ min-height:185px; padding:25px 21px; }} .issue-meta {{ position:static; margin-bottom:20px; }} .layout {{ display:block; }} .layout aside {{ width:auto; }} .signal-card {{ grid-template-columns:38px minmax(0,1fr); }} .momentum {{ grid-column:2; justify-self:start; }} }}
  @media (max-width:480px) {{ .hero h1 {{ font-size:43px; }} .tagline {{ font-size:17px; }} .signal-card {{ padding:15px; }} .section-title {{ font-size:22px; }} }}
</style></head>
<body><main class="page">
  <header class="hero"><div class="issue-meta">{issue_label} &nbsp;|&nbsp; Issue #{issue_date.isocalendar().week}</div><div class="hero-content"><h1>{hero_title}</h1><p class="tagline">{safe_intro}</p><p class="hero-copy">The eight most relevant AI developments selected from recent GitHub, Hugging Face, trend, research, and developer-community signals.</p></div></header>
  <section class="tldr"><div class="tldr-icon">⚡</div><div><h2>TL;DR — This Week in AI</h2><p>{html.escape(_tldr(views))}</p></div></section>
  <div class="layout"><section class="main-column"><h2 class="section-title">🔥 This Week’s Top {len(views)} AI Developments</h2>{''.join(html_cards)}</section>
  <aside><section class="rail-card"><h3>📊 The Numbers Behind This Week</h3><div class="metric"><span>Signals selected</span><strong>{stats['signals']}</strong></div><div class="metric"><span>Average momentum</span><strong>{stats['average_score']}/100</strong></div><div class="metric"><span>Repositories linked</span><strong>{stats['repositories']}</strong></div><div class="metric"><span>Models linked</span><strong>{stats['models']}</strong></div></section>
  <section class="rail-card"><h3>⌘ GitHub Projects in This Issue</h3><ul class="mini-list">{''.join(f'<li><div class="project-details"><a href="{html.escape(v["source_url"], quote=True)}">{html.escape(v["name"])}</a><span>Repo · Score {v["score"]}</span></div><strong class="star-count">⭐ {v["stars"]} · 🍴 {v["forks"]}</strong></li>' for v in views if v['kind'] == 'Repo' and v['source_label'] == 'GitHub' and v['source_url']) or '<li><span>No GitHub repository was selected this week.</span></li>'}</ul></section>
  <section class="rail-card"><h3>🤗 Model Signals</h3><div class="metric"><span>Hugging Face downloads</span><strong>{stats['downloads']}</strong></div><div class="metric"><span>Models represented</span><strong>{stats['models']}</strong></div><ul class="mini-list">{''.join(f'<li><div class="project-details"><span class="model-name">{html.escape(model)}</span></div><strong class="download-count">↓ {downloads:,} · ♥ {likes:,}</strong></li>' for model, downloads, likes in model_downloads) or '<li><span>No linked Hugging Face models this week.</span></li>'}</ul><p class="rail-note">Current download counters reported by Hugging Face and summed above; they are not weekly download totals.</p></section></aside></div>
  <footer>You received this email because you subscribed to AI Signal. <a href="{{unsubscribe_url}}">Unsubscribe</a></footer>
</main></body></html>'''

    text_body = "\n\n".join(
        [f"{title}\n{issue_label}", intro, *text_cards, "Unsubscribe: {unsubscribe_url}"]
    )
    return html_body, text_body


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Print an existing HTML page to PDF using an installed Chromium browser."""
    browser = next(
        (shutil.which(name) for name in ("google-chrome", "chromium", "chromium-browser") if shutil.which(name)),
        None,
    )
    if not browser:
        raise RuntimeError(
            "A Chromium-based browser is required to export PDF. "
            "Install Google Chrome or Chromium, then run the renderer again."
        )

    with tempfile.TemporaryDirectory(prefix="newsletter-chrome-") as profile_dir:
        command = [
            browser,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-crash-reporter",
            "--disable-breakpad",
            f"--user-data-dir={profile_dir}",
            f"--print-to-pdf={pdf_path.resolve()}",
            "--print-to-pdf-no-header",
            html_path.resolve().as_uri(),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)

    if result.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Could not export newsletter PDF. {details}")


def write_newsletter(
    evaluation_output: dict[str, Any], output_dir: Path, **kwargs: Any
) -> tuple[Path, Path]:
    """Render an issue, then export that exact HTML page as ``newsletter.pdf``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    html_body, text_body = render_newsletter(evaluation_output, **kwargs)
    html_path = output_dir / "newsletter.html"
    pdf_path = output_dir / "newsletter.pdf"
    html_path.write_text(html_body, encoding="utf-8")
    html_to_pdf(html_path, pdf_path)
    return html_path, pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an evaluated newsletter issue")
    parser.add_argument(
        "input",
        type=Path,
        help="JSON from ResearchEvaluator.evaluate_all, or a saved evaluation/outputs stage file",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("publishing/output"))
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--intro", default=DEFAULT_INTRO)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    html_path, pdf_path = write_newsletter(payload, args.output_dir, title=args.title, intro=args.intro)
    print(f"Wrote {html_path} and {pdf_path}")


if __name__ == "__main__":
    main()
