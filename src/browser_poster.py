"""browser_poster.py — Playwright-based IG + FB posting.

Runs headless on a VPS. Logs in once, saves session cookies to
.session_ig.json / .session_fb.json so re-login is rare.

Called by post.py when Meta API credentials are not configured.
"""
from __future__ import annotations
import json, logging, time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
SESSION_IG = ROOT / ".session_ig.json"
SESSION_FB = ROOT / ".session_fb.json"


# ── helpers ────────────────────────────────────────────────────────────────

def _load_context(browser, session_file: Path):
    """Return a browser context, restoring cookies if session file exists."""
    if session_file.exists():
        ctx = browser.new_context(storage_state=str(session_file))
    else:
        ctx = browser.new_context()
    return ctx


def _save_session(ctx, session_file: Path):
    ctx.storage_state(path=str(session_file))
    log.info("Session saved: %s", session_file)


def _is_logged_in_ig(page) -> bool:
    return "instagram.com" in page.url and page.locator('svg[aria-label="Home"]').count() > 0


def _is_logged_in_fb(page) -> bool:
    return "facebook.com" in page.url and page.locator('[aria-label="Facebook"]').count() > 0


# ── Instagram ───────────────────────────────────────────────────────────────

def post_instagram(image_path: str, caption: str, username: str, password: str) -> bool:
    """Post an image + caption to Instagram. Returns True on success."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = _load_context(browser, SESSION_IG)
        page = ctx.new_page()

        # 1. Login if needed
        page.goto("https://www.instagram.com/", timeout=30000)
        page.wait_for_timeout(2000)

        if not _is_logged_in_ig(page):
            log.info("IG: logging in as %s", username)
            page.goto("https://www.instagram.com/accounts/login/", timeout=30000)
            page.wait_for_timeout(2000)
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_timeout(4000)

            # Dismiss "Save login info?" if it appears
            try:
                page.click('button:has-text("Not Now")', timeout=5000)
            except PWTimeout:
                pass
            # Dismiss "Turn on notifications?" if it appears
            try:
                page.click('button:has-text("Not Now")', timeout=5000)
            except PWTimeout:
                pass

            if not _is_logged_in_ig(page):
                log.error("IG login failed — check credentials or 2FA")
                browser.close()
                return False
            _save_session(ctx, SESSION_IG)

        # 2. Click the New Post button (the + icon in nav)
        page.goto("https://www.instagram.com/", timeout=30000)
        page.wait_for_timeout(2000)
        try:
            page.click('svg[aria-label="New post"]', timeout=8000)
        except PWTimeout:
            # Fallback: click the + in the sidebar
            page.locator('[aria-label="New post"]').first.click()
        page.wait_for_timeout(1500)

        # 3. Upload the image via file chooser
        with page.expect_file_chooser() as fc_info:
            page.locator('text="Select from computer"').click(timeout=10000)
        fc = fc_info.value
        fc.set_files(image_path)
        page.wait_for_timeout(2000)

        # 4. Crop step — click Next
        page.click('button:has-text("Next")', timeout=10000)
        page.wait_for_timeout(1500)

        # 5. Filter step — click Next again
        page.click('button:has-text("Next")', timeout=10000)
        page.wait_for_timeout(1500)

        # 6. Caption step — type caption
        page.locator('textarea[aria-label="Write a caption..."], div[aria-label="Write a caption..."]').first.click()
        page.keyboard.type(caption, delay=20)
        page.wait_for_timeout(1000)

        # 7. Share
        page.click('button:has-text("Share")', timeout=10000)
        page.wait_for_timeout(5000)

        log.info("IG post shared successfully")
        _save_session(ctx, SESSION_IG)
        browser.close()
        return True


# ── Facebook ────────────────────────────────────────────────────────────────

def post_facebook(image_path: str, caption: str, username: str, password: str,
                  page_name: str = "") -> bool:
    """Post a photo + caption to a Facebook Page (or personal profile). Returns True on success."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = _load_context(browser, SESSION_FB)
        page = ctx.new_page()

        # 1. Login if needed
        page.goto("https://www.facebook.com/", timeout=30000)
        page.wait_for_timeout(2000)

        if not _is_logged_in_fb(page):
            log.info("FB: logging in as %s", username)
            page.fill('#email', username)
            page.fill('#pass', password)
            page.click('button[name="login"]')
            page.wait_for_timeout(4000)
            # Dismiss any dialogs
            try:
                page.click('div[aria-label="Close"]', timeout=4000)
            except PWTimeout:
                pass
            _save_session(ctx, SESSION_FB)

        # 2. Navigate to the Page if page_name is given, else use personal profile
        if page_name:
            page.goto(f"https://www.facebook.com/{page_name}", timeout=30000)
        else:
            page.goto("https://www.facebook.com/", timeout=30000)
        page.wait_for_timeout(2000)

        # 3. Click "Photo/video" to open composer with file upload
        try:
            page.locator('span:has-text("Photo/video"), div[aria-label="Photo/video"]').first.click(timeout=8000)
        except PWTimeout:
            page.locator('[aria-label="Create a post"]').first.click(timeout=8000)
            page.wait_for_timeout(1000)
            page.locator('span:has-text("Photo/video")').first.click(timeout=8000)
        page.wait_for_timeout(1500)

        # 4. Upload image
        with page.expect_file_chooser() as fc_info:
            page.locator('input[type="file"]').first.click()
        fc = fc_info.value
        fc.set_files(image_path)
        page.wait_for_timeout(2000)

        # 5. Add caption
        composer = page.locator('[contenteditable="true"]').first
        composer.click()
        page.keyboard.type(caption, delay=20)
        page.wait_for_timeout(1000)

        # 6. Post
        page.locator('div[aria-label="Post"], button:has-text("Post")').last.click(timeout=10000)
        page.wait_for_timeout(5000)

        log.info("FB post shared successfully")
        _save_session(ctx, SESSION_FB)
        browser.close()
        return True
