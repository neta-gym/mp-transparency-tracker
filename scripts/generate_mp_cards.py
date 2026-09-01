#!/usr/bin/env python3
"""Generate per-MP share-card images for social posts and link previews.

Reads data/national/leaderboard/latest.json and writes one 1200x675 JPEG per
MP to dashboard/public/mp-cards/<state-slug>/<mp-slug>.jpg. The dashboard
wires each card as that MP page's og:image, and the images double as
quote-bait attachments for social posts.

Score colors match the dashboard's continuous scale in src/lib/colors.ts.

Usage: python3 scripts/generate_mp_cards.py   (requires: pillow)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
LEADERBOARD = REPO / "data/national/leaderboard/latest.json"
PHOTOS = REPO / "dashboard/public/mp-photos"
OUT_ROOT = REPO / "dashboard/public/mp-cards"
FONTS = Path("/usr/share/fonts/truetype/dejavu")

W, H = 1200, 675
CREAM = "#faf7f2"
INK = "#111111"
RED = "#dc2626"
GRAY = "#3f3f46"
BAR_BG = "#e5e0d8"

# Dashboard score color scale stops (src/lib/colors.ts)
SCALE = [
    (0, (255, 23, 68)),
    (20, (255, 61, 0)),
    (40, (255, 171, 0)),
    (60, (0, 200, 83)),
    (80, (5, 150, 105)),
    (100, (4, 120, 87)),
]


def score_rgb(score: float) -> tuple[int, int, int]:
    s = max(0.0, min(100.0, score))
    for (x0, c0), (x1, c1) in zip(SCALE, SCALE[1:]):
        if x0 <= s <= x1:
            t = (s - x0) / (x1 - x0) if x1 > x0 else 0
            return tuple(round(a + (b - a) * t) for a, b in zip(c0, c1))
    return SCALE[-1][1]


def score_label(score: float) -> str:
    for limit, label in ((80, "EXCELLENT"), (60, "GOOD"), (40, "AVERAGE"), (20, "POOR")):
        if score >= limit:
            return label
    return "CRITICAL"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def display_state(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split())


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


F_KICKER = font("DejaVuSans-Bold.ttf", 26)
F_NAME = font("DejaVuSans-Bold.ttf", 56)
F_NAME_SM = font("DejaVuSans-Bold.ttf", 44)
F_META = font("DejaVuSans.ttf", 32)
F_SCORE = font("DejaVuSans-Bold.ttf", 104)
F_OF = font("DejaVuSans.ttf", 36)
F_LABEL = font("DejaVuSans-Bold.ttf", 26)
F_BAR = font("DejaVuSans-Bold.ttf", 26)
F_VAL = font("DejaVuSans-Bold.ttf", 26)
F_BRAND = font("DejaVuSans-Bold.ttf", 24)
F_URL = font("DejaVuSans.ttf", 22)

BARS = [
    ("MPLADS FUNDS", "mplads_score"),
    ("ATTENDANCE", "attendance_score"),
    ("CRIMINAL RECORD", "criminal_score"),
]


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        trial = f"{cur} {w_}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines[:2]


def photo_circle(entry: dict, size: int = 280) -> Image.Image:
    url = entry.get("photo_url") or ""
    path = PHOTOS / Path(url).name if url else None
    base = Image.new("RGB", (size, size), "#ffd166")
    if path and path.exists():
        im = Image.open(path).convert("RGB")
        side = min(im.size)
        left = (im.width - side) // 2
        top = (im.height - side) // 2
        im = im.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
        base = im
    else:
        d = ImageDraw.Draw(base)
        initial = (entry["mp_name"] or "?")[0].upper()
        f = font("DejaVuSans-Bold.ttf", 140)
        d.text((size / 2, size / 2), initial, font=f, fill=INK, anchor="mm")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGB", (size, size), CREAM)
    out.paste(base, (0, 0), mask)
    return out


def render(entry: dict) -> Image.Image:
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, W - 9, H - 9], outline=INK, width=12)
    d.rectangle([28, 28, W - 29, H - 29], outline=INK, width=3)

    score = float(entry["composite_score"])
    col = score_rgb(score)

    # Kicker
    d.text((70, 52), "M P   R E P O R T   C A R D", font=F_KICKER, fill=RED)

    # Photo
    px, py, pr = 70, 110, 280
    img.paste(photo_circle(entry, pr), (px, py))
    d.ellipse([px - 6, py - 6, px + pr + 6, py + pr + 6], outline=INK, width=8)

    # Name / party / constituency
    tx = 410
    name_f = F_NAME if len(entry["mp_name"]) <= 22 else F_NAME_SM
    lines = wrap(d, entry["mp_name"].upper(), name_f, 540)
    ny = 115
    for ln in lines:
        d.text((tx, ny), ln, font=name_f, fill=INK)
        ny += name_f.size + 8
    ny += 6
    d.text((tx, ny), entry["party"].upper(), font=F_META, fill=GRAY)
    ny += 46
    d.text((tx, ny), f"{entry['constituency']}, {display_state(entry['state'])}", font=F_META, fill=GRAY)

    # Score block (right)
    sx = W - 90
    d.text((sx, 120), f"{score:.1f}", font=F_SCORE, fill=col, anchor="ra")
    d.text((sx, 236), "/100", font=F_OF, fill=GRAY, anchor="ra")
    d.text((sx, 290), score_label(score), font=F_LABEL, fill=col, anchor="ra")

    # Component bars
    bx0, bw = 70, 860
    by = 420
    for label, key in BARS:
        val = float(entry.get(key) or 0)
        vcol = score_rgb(val)
        d.text((bx0, by - 4), label, font=F_BAR, fill=INK)
        d.text((bx0 + bw + 60, by - 4), f"{val:.0f}", font=F_VAL, fill=vcol, anchor="ra")
        d.rectangle([bx0, by + 32, bx0 + bw, by + 56], fill=BAR_BG, outline=INK, width=2)
        fillw = max(0, int(bw * val / 100))
        if fillw:
            d.rectangle([bx0, by + 32, bx0 + fillw, by + 56], fill=vcol)
        by += 60

    # Footer
    d.text((70, H - 66), "MP TRANSPARENCY TRACKER", font=F_BRAND, fill=INK)
    d.text((W - 70, H - 64), "neta-gym.github.io/mp-transparency-tracker", font=F_URL, fill=GRAY, anchor="ra")

    return img


def main() -> None:
    # The national leaderboard ships only the top 50; state leaderboards carry
    # every scored MP. Aggregate all 36 state files (dedup by name+state).
    entries: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for state_file in sorted(REPO.glob("data/*/leaderboard/latest.json")):
        for e in json.loads(state_file.read_text())["entries"]:
            key = (slugify(e["state"]), slugify(e["mp_name"]))
            if key not in seen:
                seen.add(key)
                entries.append(e)
    assert LEADERBOARD.exists()  # sanity: data tree present
    total = 0
    for e in entries:
        state, mp = slugify(e["state"]), slugify(e["mp_name"])
        out_dir = OUT_ROOT / state
        out_dir.mkdir(parents=True, exist_ok=True)
        render(e).save(out_dir / f"{mp}.jpg", quality=85, optimize=True)
        total += 1
    size_mb = sum(f.stat().st_size for f in OUT_ROOT.rglob("*.jpg")) / 1e6
    print(f"generated {total} cards -> {OUT_ROOT} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
