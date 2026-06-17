"""Image style templates per content pillar.

Keep prompts brand-consistent: warm, clean, professional med-spa aesthetic.
Rotate 3-5 visual styles to avoid a samey feed. Tune freely.
"""

# 4 content pillars (locked in Phase 0 decisions)
PILLARS = [
    "Get Booked",            # marketing & lead gen
    "Keep Them Coming Back", # retention & experience
    "Mind the Margin",       # pricing & profit
    "Run the Room",          # ops, team & compliance
]

# Shared look-and-feel (edit to match the locked visual identity).
BASE_STYLE = (
    "clean modern medical-spa aesthetic, soft natural light, warm neutral "
    "palette (creams, soft beige, muted sage), professional, uncluttered, "
    "editorial photography style, high quality, no text overlay"
)

PILLAR_STYLE = {
    "Get Booked": "bright welcoming clinic reception or phone-in-hand booking moment",
    "Keep Them Coming Back": "warm client-experience moment, relaxed returning client",
    "Mind the Margin": "tasteful flat-lay of treatment tools / subtle finance motif",
    "Run the Room": "calm organized treatment room, confident small team",
}


def build_image_prompt(pillar: str) -> str:
    scene = PILLAR_STYLE.get(pillar, "")
    return f"{scene}, {BASE_STYLE}".strip(", ")
