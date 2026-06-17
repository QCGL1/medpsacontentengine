# Setup — Sahil's Build Runbook

Hey Sahil. This gets the engine fully built and tested **without any API keys,
any paid accounts, or any of Prateek's credentials**. You'll run everything in
**DRY_RUN mode** — it logs exactly what it *would* do instead of making real
calls or posting anything live. Prateek drops in the real keys afterward and
flips one switch.

You do **not** need:
- ❌ A credit card
- ❌ A Runway / Anthropic / Meta account
- ❌ Any real API key (placeholders only)
- ❌ Claude

---

## 1. Get the code
```bash
git clone <repo-url> medspa-content-engine   # Prateek will share the repo
cd medspa-content-engine
```
(If he hands you a zip instead, just unzip and `cd` in.)

## 2. Python env (Windows/WSL or any Linux/Mac)
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Create your local .env (placeholders only)
```bash
cp .env.example .env
```
Leave the dummy values exactly as they are. Confirm `DRY_RUN=true` is set.
**Never put a real key in this file.** When Prateek has real keys, they go into
GitHub Secrets (his job), not into your `.env`.

## 4. Run each job in dry-run
```bash
python -m src.generate    # drafts 7 placeholder concepts into content_queue/
python -m src.post        # "publishes" the first approved item (logs only)
python -m src.analyze     # scores + appends a dry-run block to learnings.md
```
Expected: lots of `[DRY_RUN] ...` log lines, JSON files appearing in
`content_queue/`, and no errors. That's a fully working pipeline.

## 5. Test the manual approval gate
Open any file in `content_queue/*.json`, change `"approved": false` to `true`,
save, then re-run `python -m src.post`. It should "post" that item and move the
record into `archive/`.

## 6. Your build tasks (the `TODO(sahil)` markers)
Search the repo for `TODO(sahil)` — those are the spots to wire real logic.
Everything compiles and runs in dry-run today; you're filling in the live calls:

| File | What to implement |
|------|-------------------|
| `src/generate.py` | Anthropic concept call + Runway image render |
| `src/meta_client.py` | IG 2-step publish, FB photo publish, insights fetch |
| `src/analyze.py` | Anthropic pattern analysis from scored posts |
| `src/post.py` | (mostly done) confirm retry/alert path |

Each `TODO` has a one-line spec next to it. Build against dry-run, then Prateek
tests live with real keys.

## 7. GitHub Actions
The three workflows in `.github/workflows/` are ready. They default to DRY_RUN
via a repo variable, so they run green even before keys exist. You can trigger
them manually from the Actions tab ("Run workflow") to confirm they pass.

## Gotchas to respect while building
- **Don't** post byte-identical content to IG and FB — `post.py` already varies
  the FB caption via `fb_variant()`; keep that.
- IG must be a **Professional** account linked to an FB Page (Prateek sets up).
- Failed image gens happen ~10–15% of the time — keep the retry-once logic.
- Don't commit `.env` or anything secret (`.gitignore` already blocks it).

## Handoff back to Prateek
When your `TODO(sahil)` items work in dry-run, tell Prateek. He'll:
1. Add the real keys to GitHub Secrets,
2. Set the repo variable `DRY_RUN=false`,
3. Run a live test post.
No code change needed for go-live.
