"""generate.py — Sunday job.

Reads learnings.md + pillar rotation -> Anthropic drafts N concepts
-> Runway renders images -> save image+caption to content_queue/
-> emit a review digest for the Sunday manual approval gate.

Run: python -m src.generate
"""
from __future__ import annotations
import json, logging, time
from datetime import date
import requests
import anthropic as _anthropic
from .config import CFG, CONTENT_QUEUE, LEARNINGS
from .prompts.image_prompts import build_image_prompt, PILLARS
from .prompts.caption_prompts import build_caption_prompt, SYSTEM

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("generate")


def read_learnings() -> str:
    return LEARNINGS.read_text(encoding="utf-8") if LEARNINGS.exists() else ""


def rotate_pillars(n: int) -> list[str]:
    """One pillar per post, cycling through the 4 pillars."""
    return [PILLARS[i % len(PILLARS)] for i in range(n)]


def draft_concept(pillar: str, learnings: str) -> dict:
    if CFG.dry_run:
        return {
            "pillar": pillar,
            "hook": f"[DRY_RUN hook for {pillar}]",
            "caption": f"[DRY_RUN caption for {pillar}]",
            "image_prompt": build_image_prompt(pillar),
        }
    client = _anthropic.Anthropic(api_key=CFG.anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_caption_prompt(pillar, learnings)}],
    )
    return json.loads(msg.content[0].text)


def render_image(image_prompt: str, slug: str) -> str:
    if CFG.dry_run:
        log.info("[DRY_RUN] Runway render: %.60s...", image_prompt)
        return f"content_queue/{slug}.png"
    headers = {
        "Authorization": f"Bearer {CFG.runway_api_key}",
        "X-Runway-Version": "2024-11-06",
        "Content-Type": "application/json",
    }
    for attempt in range(2):
        r = requests.post(
            "https://api.dev.runwayml.com/v1/text_to_image",
            headers=headers,
            json={"promptText": image_prompt, "model": "gen3a_turbo", "ratio": "1:1"},
            timeout=30,
        )
        r.raise_for_status()
        task_id = r.json()["id"]
        for _ in range(60):
            time.sleep(5)
            poll = requests.get(
                f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                headers=headers,
                timeout=15,
            )
            poll.raise_for_status()
            task = poll.json()
            if task["status"] == "SUCCEEDED":
                img_url = task["output"][0]
                img_bytes = requests.get(img_url, timeout=30).content
                out_path = CONTENT_QUEUE / f"{slug}.png"
                out_path.write_bytes(img_bytes)
                log.info("Runway image saved: %s", out_path)
                return str(out_path)
            if task["status"] == "FAILED":
                log.warning("Runway gen failed (attempt %d): %s", attempt + 1, task.get("error"))
                break
        else:
            log.warning("Runway gen timed out (attempt %d)", attempt + 1)
    raise RuntimeError(f"Runway image generation failed after 2 attempts for slug={slug}")


def main() -> None:
    CONTENT_QUEUE.mkdir(exist_ok=True)
    learnings = read_learnings()
    week = date.today().isoformat()
    queue = []
    for i, pillar in enumerate(rotate_pillars(CFG.posts_per_week), start=1):
        slug = f"{week}_post{i}_{pillar.lower().replace(' ', '-')}"
        concept = draft_concept(pillar, learnings)
        concept["image_path"] = render_image(concept["image_prompt"], slug)
        concept["slug"] = slug
        concept["approved"] = False  # flipped at the manual gate
        (CONTENT_QUEUE / f"{slug}.json").write_text(
            json.dumps(concept, indent=2), encoding="utf-8"
        )
        queue.append(concept)
    emit_digest(queue, week)


def emit_digest(queue: list[dict], week: str) -> None:
    log.info("\n=== REVIEW DIGEST — week of %s ===", week)
    for c in queue:
        log.info("• [%s] %s", c["pillar"], c["hook"])
    log.info("Approve in content_queue/*.json by setting \"approved\": true")
    log.info("Open content_queue/*.json and set \"approved\": true for posts to schedule.")


if __name__ == "__main__":
    main()
