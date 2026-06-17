"""post.py — weekday 10am job.

Pulls the next APPROVED item from content_queue/, publishes to IG (+ FB
with a minor caption variation to avoid the duplicate-content penalty),
moves the record to archive/. 3x retry then alert.

Run: python -m src.post
"""
from __future__ import annotations
import json, logging
from datetime import date
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import CFG, CONTENT_QUEUE, ARCHIVE
from .meta_client import MetaClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("post")
meta = MetaClient()


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
def _publish(rec: dict) -> dict:
    image_url = rec.get("image_url") or rec.get("image_path")
    out = {}
    if CFG.target_ig:
        out["ig_id"] = meta.publish_ig(image_url, rec["caption"])
    if CFG.target_fb:
        out["fb_id"] = meta.publish_fb(image_url, fb_variant(rec["caption"]))
    return out


def _send_alert(rec: dict) -> None:
    """Log a prominent failure alert. Extend with email/Slack when credentials exist."""
    slug = rec.get("slug", "unknown")
    log.critical("=" * 60)
    log.critical("PUBLISH ALERT — post '%s' failed after all retries.", slug)
    log.critical("Action needed: check content_queue/%s.json and retry manually.", slug)
    log.critical("=" * 60)
    # Wire real email here once ALERT_EMAIL / SMTP credentials are in GitHub Secrets.
    alert_email = CFG.__dict__.get("alert_email") or ""
    if alert_email:
        import smtplib, os
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = f"[medspa-engine] Publish failed: {slug}"
        msg["From"] = alert_email
        msg["To"] = alert_email
        msg.set_content(f"Post '{slug}' failed after 3 retries. Check the Actions log.")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(alert_email, os.environ.get("GMAIL_APP_PASSWORD", ""))
            smtp.send_message(msg)


def main() -> None:
    ARCHIVE.mkdir(exist_ok=True)
    rec = next_approved()
    if not rec:
        log.info("No approved item ready to post.")
        return
    try:
        ids = _publish(rec)
    except Exception:
        log.exception("Publish failed after retries — ALERT")
        _send_alert(rec)
        raise
    rec.update(posted=True, posted_on=date.today().isoformat(), publish_ids=ids)
    (ARCHIVE / f"{rec['slug']}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    src = CONTENT_QUEUE / f"{rec['slug']}.json"
    if src.exists():
        src.unlink()
    log.info("Posted %s -> %s", rec["slug"], ids)


if __name__ == "__main__":
    main()
