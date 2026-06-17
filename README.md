# medspa-content-engine

AI-assisted Instagram + Facebook content engine for a B2B med spa education
account. Generates weekly image+caption concepts, posts approved ones daily,
and learns from engagement — all on ~$13/mo infra and <30 min/week of human time.

## How it runs
| Day | Workflow | Does |
|-----|----------|------|
| Sun 9am | `weekly_generate` | Draft 7 concepts + images → `content_queue/` → review digest |
| Sun (manual) | you/owner | Approve items (set `"approved": true` in the JSON) |
| M–F 10am | `daily_post` | Publish one approved item to IG + FB |
| Fri 6pm | `weekly_analyze` | Score posts, append to `learnings.md`, suggest themes |

Engagement score: `(saves*3 + shares*3 + comments*2 + likes*1) / reach`

## Layout
```
src/            generate.py · post.py · analyze.py · config.py · meta_client.py
src/prompts/    image_prompts.py · caption_prompts.py
src/learnings.md  append-only memory the engine reads + writes
brand/          pillars.md · voice.md  (locked Phase 0 decisions)
content_queue/  generated, not-yet-posted items
archive/        posted items + metrics
.github/workflows/  the three cron jobs
```

## Build it
**Sahil:** follow `SETUP_SAHIL.md`. You can build and test the entire thing in
**DRY_RUN mode with zero API keys** — nothing costs money, nothing posts live.

**Real keys / paid accounts** are owned by Prateek and added later via GitHub
Secrets (see his private runbook). The code is written so the live switch is
literally flipping `DRY_RUN` to `false` once Secrets exist — no code changes.

## Dry-run vs live
- `DRY_RUN=true` (default) → every external call is logged, not executed.
- `DRY_RUN=false` → requires all keys present (enforced in `config.py`).
