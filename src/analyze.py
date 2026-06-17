"""analyze.py — Friday 6pm job.

Pulls metrics for the last 7 posts -> scores each -> Anthropic identifies
patterns -> appends to learnings.md -> emits a Friday digest with suggested
themes for next week.

Engagement score = (saves*3 + shares*3 + comments*2 + likes*1) / reach

Run: python -m src.analyze
"""
from __future__ import annotations
import json, logging
from datetime import date
import anthropic as _anthropic
from .config import CFG, ARCHIVE, LEARNINGS
from .meta_client import MetaClient
from .prompts.caption_prompts import SYSTEM

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("analyze")
meta = MetaClient()


def score(m: dict) -> float:
    reach = max(m.get("reach", 0), 1)
    return (m.get("saves", 0) * 3 + m.get("shares", 0) * 3
            + m.get("comments", 0) * 2 + m.get("likes", 0) * 1) / reach


def recent_posts(n: int = 7) -> list[dict]:
    files = sorted(ARCHIVE.glob("*.json"))[-n:]
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def analyze_patterns(scored: list[dict]) -> str:
    if CFG.dry_run:
        return "[DRY_RUN] Pattern analysis + next-week themes go here."
    client = _anthropic.Anthropic(api_key=CFG.anthropic_api_key)
    summary = json.dumps(
        [{"pillar": p.get("pillar"), "score": p.get("score"), "hook": p.get("hook")} for p in scored],
        indent=2,
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                "These are last week's posts ranked by engagement score (saves×3 + shares×3 "
                "+ comments×2 + likes×1) / reach. Higher = better.\n\n"
                f"{summary}\n\n"
                "In 3-5 bullet points: what patterns made the top posts work? "
                "Then suggest 3 specific themes for next week. Return plain markdown."
            ),
        }],
    )
    return msg.content[0].text


def append_learnings(text: str) -> None:
    stamp = f"\n\n## {date.today().isoformat()}\n{text}\n"
    with LEARNINGS.open("a", encoding="utf-8") as fh:
        fh.write(stamp)


def main() -> None:
    posts = recent_posts()
    for p in posts:
        m = meta.fetch_metrics(p.get("publish_ids", {}).get("ig_id", ""))
        p["metrics"] = m
        p["score"] = round(score(m), 3)
    posts.sort(key=lambda x: x["score"], reverse=True)
    insight = analyze_patterns(posts)
    append_learnings(insight)
    log.info("=== FRIDAY DIGEST ===")
    for p in posts:
        log.info("  %.3f  [%s] %s", p["score"], p.get("pillar", "?"), p.get("slug", ""))
    log.info("Top pillar this week: %s", posts[0].get("pillar") if posts else "n/a")


if __name__ == "__main__":
    main()
