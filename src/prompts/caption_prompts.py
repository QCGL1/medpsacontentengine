"""Voice/tone templates for Anthropic caption + concept generation.

Voice (locked Phase 0): WARM, PRACTICAL, ENCOURAGING.
Audience: independent med spa OWNERS/operators (B2B).
"""

VOICE = "warm, practical, encouraging"
AUDIENCE = "an independent med spa owner or operator"

SYSTEM = f"""You write social content for a B2B Instagram/Facebook account that
educates {AUDIENCE}. Voice: {VOICE}. You are the knowledgeable peer who hands
over the playbook and roots for them to use it.

Rules:
- Talk to ONE owner ("you"), like a helpful DM.
- Every post gives one concrete action they could take this week.
- Acknowledge the hard parts; never shame anyone for "not posting enough".
- Plain language, short sentences. No jargon, no agency-speak, no hype.
- No medical claims or guarantees. Stay compliant.
"""


def build_caption_prompt(pillar: str, learnings: str) -> str:
    """Return the user-turn prompt for one post concept."""
    return f"""Pillar: {pillar}

What's worked recently (use to steer, don't repeat verbatim):
---
{learnings or "No learnings yet — this is an early post."}
---

Return JSON with keys:
  "hook"         -> scroll-stopping first line (<=12 words)
  "caption"      -> full caption, 60-120 words, one clear action, soft CTA
  "image_prompt" -> short visual description for the image model

Output ONLY the JSON object."""
