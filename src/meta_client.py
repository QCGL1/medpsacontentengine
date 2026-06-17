"""Thin wrapper around the Meta Graph API for IG + FB publishing.

GOTCHAS baked in as TODOs:
  * Long-lived tokens expire ~every 60 days -> refresh_long_lived_token().
  * IG publishing is a 2-step flow: create media container, then publish.
  * Never post byte-identical content to IG and FB (vary caption slightly).
"""
from __future__ import annotations
import logging
import requests
from .config import CFG

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"


class MetaClient:
    def __init__(self, cfg=CFG):
        self.cfg = cfg

    # --- Instagram ---------------------------------------------------------
    def publish_ig(self, image_url: str, caption: str) -> str | None:
        if self.cfg.dry_run:
            log.info("[DRY_RUN] IG publish: %s | %.60s...", image_url, caption)
            return "dry-run-ig-id"
        r = requests.post(
            f"{GRAPH}/{self.cfg.meta_ig_account_id}/media",
            data={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.cfg.meta_access_token,
            },
            timeout=30,
        )
        r.raise_for_status()
        creation_id = r.json()["id"]
        r2 = requests.post(
            f"{GRAPH}/{self.cfg.meta_ig_account_id}/media_publish",
            data={
                "creation_id": creation_id,
                "access_token": self.cfg.meta_access_token,
            },
            timeout=30,
        )
        r2.raise_for_status()
        media_id = r2.json()["id"]
        log.info("IG published: %s", media_id)
        return media_id

    # --- Facebook ----------------------------------------------------------
    def publish_fb(self, image_url: str, caption: str) -> str | None:
        if self.cfg.dry_run:
            log.info("[DRY_RUN] FB publish: %s | %.60s...", image_url, caption)
            return "dry-run-fb-id"
        r = requests.post(
            f"{GRAPH}/{self.cfg.meta_page_id}/photos",
            data={
                "url": image_url,
                "caption": caption,
                "access_token": self.cfg.meta_access_token,
            },
            timeout=30,
        )
        r.raise_for_status()
        post_id = r.json()["id"]
        log.info("FB published: %s", post_id)
        return post_id

    # --- Metrics -----------------------------------------------------------
    def fetch_metrics(self, media_id: str) -> dict:
        if self.cfg.dry_run:
            return {"reach": 1000, "likes": 50, "comments": 8, "saves": 20, "shares": 12}
        r = requests.get(
            f"{GRAPH}/{media_id}/insights",
            params={
                "metric": "reach,likes,comments,saved,shares",
                "access_token": self.cfg.meta_access_token,
            },
            timeout=15,
        )
        r.raise_for_status()
        out: dict = {}
        for m in r.json().get("data", []):
            out[m["name"]] = m["values"][0]["value"] if m.get("values") else m.get("value", 0)
        out["saves"] = out.pop("saved", 0)
        return out

    # --- Token health ------------------------------------------------------
    def refresh_long_lived_token(self) -> str:
        # TODO(prateek-side): exchange before ~day 60. See SETUP_PRATEEK.md.
        raise NotImplementedError("Token refresh handled per SETUP_PRATEEK.md")
