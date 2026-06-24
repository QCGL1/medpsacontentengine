"""generate.py — Sunday job.

Reads learnings.md + pillar rotation -> Anthropic drafts N concepts
-> Runway renders images -> save image+caption to content_queue/
-> emit a review digest for the Sunday manual approval gate.

Run: python -m src.generate
"""
from __future__ import annotations
import json, logging, re, time
from datetime import date
from pathlib import Path
import requests
import anthropic
from .config import CFG, CONTENT_QUEUE, LEARNINGS
from .prompts.image_prompts import build_image_prompt, PILLARS
from .prompts.caption_prompts import build_caption_prompt, SYSTEM

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("generate")

RUNWAY_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_VERSION = "2024-11-06"


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
    client = anthropic.Anthropic(api_key=CFG.anthropic_api_key)
    prompt = build_caption_prompt(pillar, learnings)
    for attempt in range(3):
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            concept = json.loads(raw)
        except json.JSONDecodeError:
            # Extract the first {...} block as fallback
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    concept = json.loads(m.group())
                except json.JSONDecodeError:
                    if attempt < 2:
                        log.warning("JSON parse failed (attempt %d), retrying...", attempt + 1)
                        time.sleep(2)
                        continue
                    raise
            elif attempt < 2:
                log.warning("No JSON found (attempt %d), retrying...", attempt + 1)
                time.sleep(2)
                continue
            else:
                raise
        concept["pillar"] = pillar
        if "image_prompt" not in concept:
            concept["image_prompt"] = build_image_prompt(pillar)
        log.info("Drafted concept for pillar: %s | hook: %s", pillar, concept.get("hook", ""))
        return concept
    raise RuntimeError(f"Failed to draft concept for pillar: {pillar}")


def _runway_poll(task_id: str, timeout: int = 120) -> str:
    """Poll Runway task until SUCCEEDED; return image URL."""
    headers = {
        "Authorization": f"Bearer {CFG.runway_api_key}",
        "X-Runway-Version": RUNWAY_VERSION,
    }
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{RUNWAY_BASE}/tasks/{task_id}", headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "SUCCEEDED":
            return data["output"][0]
        if status == "FAILED":
            raise RuntimeError(f"Runway task {task_id} failed: {data.get('failure')}")
        time.sleep(5)
    raise TimeoutError(f"Runway task {task_id} did not complete in {timeout}s")


def render_image(image_prompt: str, slug: str) -> str:
    if CFG.dry_run:
        log.info("[DRY_RUN] Runway render: %.60s...", image_prompt)
        return f"content_queue/{slug}.png"
    headers = {
        "Authorization": f"Bearer {CFG.runway_api_key}",
        "X-Runway-Version": RUNWAY_VERSION,
        "Content-Type": "application/json",
    }
    payload = {"model": "gen4_image", "promptText": image_prompt, "ratio": "1080:1080"}
    for attempt in range(2):
        try:
            resp = requests.post(f"{RUNWAY_BASE}/text_to_image", headers=headers,
                                 json=payload, timeout=30)
            if resp.status_code == 400 and "credits" in resp.text.lower():
                log.warning("Runway: insufficient credits — skipping image, saving placeholder.")
                return f"PLACEHOLDER:{slug}.png"
            resp.raise_for_status()
            task_id = resp.json()["id"]
            log.info("Runway task %s submitted (attempt %d)", task_id, attempt + 1)
            image_url = _runway_poll(task_id)
            img_data = requests.get(image_url, timeout=60).content
            out_path = CONTENT_QUEUE / f"{slug}.png"
            out_path.write_bytes(img_data)
            log.info("Image saved: %s", out_path)
            return str(out_path)
        except Exception as exc:
            log.warning("Runway attempt %d failed: %s", attempt + 1, exc)
            if attempt == 1:
                raise
            time.sleep(3)
    raise RuntimeError("Runway image generation failed after 2 attempts")


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
    # TODO(sahil): optionally email/Slack/Gmail-label this digest for Prateek.


if __name__ == "__main__":
    main()
