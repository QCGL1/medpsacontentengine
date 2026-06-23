"""post.py — weekday 10am job.

Pulls the next APPROVED item from content_queue/ and either:
  - Posts via Meta API if META credentials are configured, OR
  - Packages the post into ready_to_post/<slug>/ with image + captions
    so it can be manually posted in ~30 seconds.

Run: python -m src.post
"""
from __future__ import annotations
import json, logging, shutil, subprocess, sys
from datetime import date
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import CFG, CONTENT_QUEUE, ARCHIVE, ROOT
from .meta_client import MetaClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("post")
meta = MetaClient()

READY_TO_POST = ROOT / "ready_to_post"

_META_CONFIGURED = (
    CFG.meta_access_token not in ("", "dummy-long-lived-token")
    and CFG.meta_page_id not in ("", "000000000000000")
    and CFG.meta_ig_account_id not in ("", "000000000000000")
)


def next_approved() -> dict | None:
    items = sorted(CONTENT_QUEUE.glob("*.json"))
    for path in items:
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("approved") and not rec.get("posted"):
            rec["_path"] = str(path)
            return rec
    return None


def fb_variant(caption: str) -> str:
    """Tiny variation so IG and FB are not byte-identical."""
    return caption.rstrip() + "\n\n—\nFollow along for more."


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def _publish_meta(rec: dict) -> dict:
    image_url = rec.get("image_url") or rec.get("image_path")
    out = {}
    if CFG.target_ig:
        out["ig_id"] = meta.publish_ig(image_url, rec["caption"])
    if CFG.target_fb:
        out["fb_id"] = meta.publish_fb(image_url, fb_variant(rec["caption"]))
    return out


def _package_for_manual_post(rec: dict) -> Path:
    """Save image + caption files into ready_to_post/<slug>/ and open in Finder."""
    READY_TO_POST.mkdir(exist_ok=True)
    out_dir = READY_TO_POST / rec["slug"]
    out_dir.mkdir(exist_ok=True)

    # Copy image if it exists on disk
    image_path = rec.get("image_path", "")
    if image_path and not image_path.startswith("PLACEHOLDER") and Path(image_path).exists():
        ext = Path(image_path).suffix or ".png"
        shutil.copy(image_path, out_dir / f"image{ext}")
        log.info("Image copied: %s", out_dir / f"image{ext}")
    else:
        # Write a note if image is a placeholder (Runway credits needed)
        (out_dir / "IMAGE_MISSING.txt").write_text(
            "Image not generated yet — add Runway credits and re-run src.generate.\n"
            f"Suggested prompt:\n{rec.get('image_prompt', '')}\n",
            encoding="utf-8",
        )
        log.warning("No image available — wrote prompt to IMAGE_MISSING.txt")

    # Instagram caption
    ig_caption = rec.get("caption", "")
    (out_dir / "caption_instagram.txt").write_text(ig_caption, encoding="utf-8")

    # Facebook caption (slight variation)
    fb_caption = fb_variant(ig_caption)
    (out_dir / "caption_facebook.txt").write_text(fb_caption, encoding="utf-8")

    # Summary card
    summary = (
        f"Pillar:  {rec.get('pillar', '')}\n"
        f"Hook:    {rec.get('hook', '')}\n"
        f"Slug:    {rec['slug']}\n"
        f"Date:    {date.today().isoformat()}\n\n"
        f"HOW TO POST:\n"
        f"1. Open caption_instagram.txt — copy the text\n"
        f"2. Open Instagram, create new post, paste caption, attach image\n"
        f"3. Repeat for Facebook using caption_facebook.txt\n"
    )
    (out_dir / "HOW_TO_POST.txt").write_text(summary, encoding="utf-8")

    log.info("Ready-to-post package: %s", out_dir)

    # Open the folder in Finder (Mac) so it's right there
    if sys.platform == "darwin":
        subprocess.run(["open", str(out_dir)], check=False)

    return out_dir


_BROWSER_CONFIGURED = bool(CFG.ig_username and CFG.ig_password)


def _publish_browser(rec: dict) -> dict:
    """Post via Playwright browser automation. Falls back to manual package if no login."""
    image_path = rec.get("image_path", "")
    has_image = image_path and not image_path.startswith("PLACEHOLDER") and Path(image_path).exists()

    if not _BROWSER_CONFIGURED:
        log.warning("No IG_USERNAME/IG_PASSWORD set — falling back to manual package.")
        _package_for_manual_post(rec)
        return {"manual": True}

    if not has_image:
        log.warning("No real image available (Runway credits needed) — falling back to manual package.")
        _package_for_manual_post(rec)
        return {"manual": True}

    from .browser_poster import post_instagram, post_facebook
    ids: dict = {}

    if CFG.target_ig:
        log.info("Posting to Instagram via browser...")
        ok = post_instagram(image_path, rec["caption"], CFG.ig_username, CFG.ig_password)
        ids["ig_browser"] = "posted" if ok else "failed"

    if CFG.target_fb and CFG.fb_username:
        log.info("Posting to Facebook via browser...")
        ok = post_facebook(image_path, fb_variant(rec["caption"]),
                           CFG.fb_username, CFG.fb_password, CFG.fb_page_name)
        ids["fb_browser"] = "posted" if ok else "failed"

    return ids


def main() -> None:
    ARCHIVE.mkdir(exist_ok=True)
    rec = next_approved()
    if not rec:
        log.info("No approved item ready to post.")
        return

    if CFG.dry_run:
        log.info("[DRY_RUN] Would post: %s", rec["slug"])
        log.info("[DRY_RUN] Hook: %s", rec.get("hook", ""))
        log.info("[DRY_RUN] Caption: %.80s...", rec.get("caption", ""))
        return

    if _META_CONFIGURED:
        log.info("Meta credentials found — posting via API...")
        try:
            ids = _publish_meta(rec)
        except Exception:
            log.exception("Meta publish failed — falling back to browser automation")
            ids = _publish_browser(rec)
    else:
        log.info("No Meta API credentials — using browser automation.")
        ids = _publish_browser(rec)

    rec.update(posted=True, posted_on=date.today().isoformat(), publish_ids=ids)
    (ARCHIVE / f"{rec['slug']}.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    src = CONTENT_QUEUE / f"{rec['slug']}.json"
    if src.exists():
        src.unlink()
    log.info("Done: %s", rec["slug"])


if __name__ == "__main__":
    main()
