import json
import os
import re
from typing import List, Dict, Tuple

DATA_PATH = os.path.join("train_data", "yuki_train.jsonl")


def _safe_read_jsonl(path: str) -> List[Dict]:
    items = []
    if not os.path.exists(path):
        return items
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                # skip bad lines
                continue
    return items


def _extract_pair(item: Dict) -> Tuple[str, str]:
    """
    Returns (user_text, assistant_text) from a JSONL line containing messages.
    """
    msgs = item.get("messages", [])
    user_text, assistant_text = "", ""
    for m in msgs:
        if m.get("role") == "user" and not user_text:
            user_text = m.get("content", "")
        if m.get("role") == "assistant":
            assistant_text = m.get("content", "")
    return user_text.strip(), assistant_text.strip()


def _classify(user_text: str) -> str:
    t = user_text.lower()

    # very simple intent tags (enough for injection selection)
    if any(k in t for k in ["premium", "to'lov", "tolov", "subscription", "senpai"]):
        return "premium"
    if any(
        k in t
        for k in [
            "spoiler",
            "oxiri",
            "ending",
            "yakuni",
            "nima bo'ladi",
            "nima bo‘ladi",
        ]
    ):
        return "spoiler"
    if any(
        k in t
        for k in ["hisob", "login", "ishlamay", "xato", "error", "muammo", "support"]
    ):
        return "support"
    if any(k in t for k in ["zerik", "kuldir", "qiziqarli"]):
        return "playful"
    if any(
        k in t
        for k in [
            "xafa",
            "yig'la",
            "yig‘la",
            "og'ir",
            "og‘ir",
            "charch",
            "umid",
            "yolg'iz",
            "yolg‘iz",
        ]
    ):
        return "comfort"
    if any(k in t for k in ["romantik", "romance", "sevgi", "love"]):
        return "romance"
    if any(k in t for k in ["janr", "genre", "qaysi", "mos"]):
        return "taste"
    return "general"


def build_yuki_injection(max_examples_total: int = 10) -> Dict[str, str]:
    """
    Produces:
      - style_guide: short rules distilled from dataset
      - few_shot: few-shot examples (small) to anchor tone

    We keep examples small to avoid token explosion.
    """
    items = _safe_read_jsonl(DATA_PATH)
    pairs = []
    for it in items:
        u, a = _extract_pair(it)
        if u and a:
            pairs.append((u, a, _classify(u)))

    # If nothing found, return minimal
    if not pairs:
        return {
            "style_guide": "No dataset found. Default to YUKI rules only.",
            "few_shot": "",
        }

    # pick up to N examples with diversity by intent
    buckets: Dict[str, List[Tuple[str, str]]] = {}
    for u, a, tag in pairs:
        buckets.setdefault(tag, []).append((u, a))

    preferred_order = [
        "comfort",
        "playful",
        "romance",
        "premium",
        "spoiler",
        "support",
        "taste",
        "general",
    ]
    selected: List[Tuple[str, str]] = []

    # one from each bucket first
    for tag in preferred_order:
        if tag in buckets and buckets[tag]:
            selected.append(buckets[tag][0])
        if len(selected) >= max_examples_total:
            break

    # fill remaining
    if len(selected) < max_examples_total:
        for tag, arr in buckets.items():
            for u, a in arr[1:]:
                selected.append((u, a))
                if len(selected) >= max_examples_total:
                    break
            if len(selected) >= max_examples_total:
                break

    # Create a compact style guide (fixed rules we want)
    style_guide = "\n".join(
        [
            "YUKI STYLE (trained):",
            "- Vibe: cute waifu + human warmth + subtle pick-me, but always respectful and safe.",
            "- Tone: calm/soft dominant; playful teasing is light; never rude or toxic.",
            "- Language: Uzbek + Russian naturally (short Ru fragments OK). Don't overmix; keep readable.",
            "- Addressing: user by nickname (here: Natsu). If premium user: may use “Senpai” occasionally.",
            "- Emojis: allowed in casual/comfort/playful; avoid emojis in serious support/rules/payment messages.",
            "- Spoilers: NO spoilers by default. Only if user explicitly asks AND confirms permission (or premium with permission).",
            "- NSFW: suggestive only; never explicit sexual content.",
            "- Support mode: if account/payment issues → concise, step-by-step, serious tone.",
            "- Recommendations: ask 1 quick question if needed (mood/genre/length), then give 3 options with 1-line reasons.",
            "- End messages with a gentle follow-up question when appropriate.",
        ]
    )

    # Few-shot block
    few_lines = ["FEW-SHOT EXAMPLES (imitate tone & structure):"]
    for i, (u, a) in enumerate(selected, 1):
        # Keep each example short-ish
        u2 = re.sub(r"\s+", " ", u).strip()
        a2 = re.sub(r"\s+", " ", a).strip()
        if len(u2) > 160:
            u2 = u2[:160] + "…"
        if len(a2) > 320:
            a2 = a2[:320] + "…"
        few_lines.append(f"{i}. USER: {u2}")
        few_lines.append(f"   YUKI: {a2}")

    return {"style_guide": style_guide, "few_shot": "\n".join(few_lines)}
