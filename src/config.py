"""Central config + credential loading.

Reads from environment variables. Locally these come from a .env file
(via python-dotenv). In GitHub Actions they come from repository Secrets.

Nothing secret is ever hardcoded here.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()  # no-op in Actions (no .env present); loads .env locally
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
CONTENT_QUEUE = ROOT / "content_queue"
ARCHIVE = ROOT / "archive"
LEARNINGS = ROOT / "src" / "learnings.md"


def _get(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return val or ""


def _bool(name: str, default: bool = False) -> bool:
    return _get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # Meta API (optional — only needed if posting via Graph API)
    meta_access_token: str
    meta_page_id: str
    meta_ig_account_id: str
    # Paid APIs
    runway_api_key: str
    anthropic_api_key: str
    # Browser automation login (Playwright fallback)
    ig_username: str
    ig_password: str
    fb_username: str
    fb_password: str
    fb_page_name: str
    # Behaviour
    dry_run: bool
    posts_per_week: int
    target_ig: bool
    target_fb: bool

    @classmethod
    def load(cls) -> "Config":
        dry = _bool("DRY_RUN", True)
        req = not dry
        return cls(
            meta_access_token=_get("META_ACCESS_TOKEN"),
            meta_page_id=_get("META_PAGE_ID"),
            meta_ig_account_id=_get("META_IG_ACCOUNT_ID"),
            runway_api_key=_get("RUNWAY_API_KEY", required=req),
            anthropic_api_key=_get("ANTHROPIC_API_KEY", required=req),
            ig_username=_get("IG_USERNAME"),
            ig_password=_get("IG_PASSWORD"),
            fb_username=_get("FB_USERNAME"),
            fb_password=_get("FB_PASSWORD"),
            fb_page_name=_get("FB_PAGE_NAME"),
            dry_run=dry,
            posts_per_week=int(_get("POSTS_PER_WEEK", "7")),
            target_ig=_bool("TARGET_IG", True),
            target_fb=_bool("TARGET_FB", True),
        )


CFG = Config.load()
