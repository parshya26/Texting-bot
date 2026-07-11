"""
Generates the PNG images shown by /rank, /streak, and the leaderboard
commands. Original "Texting" branded design (dark background + accent
gradient) — visually similar in spirit to community rank-card bots, but
the artwork, layout and colors here are original, not copied.

Every card ends with the "Powered By @SEASON" footer.
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path(__file__).parent.parent / "fonts"
FONT_BOLD = str(FONTS_DIR / "DejaVuSans-Bold.ttf")
FONT_REGULAR = str(FONTS_DIR / "DejaVuSans.ttf")

# Dark background with a subtle accent — distinct from the reference bot's palette.
BG_COLOR = (13, 17, 23)
ACCENT = (88, 101, 242)       # indigo/blurple accent (Texting brand color)
ACCENT_SOFT = (49, 54, 84)
TEXT_WHITE = (240, 240, 245)
TEXT_MUTED = (150, 155, 170)
GOLD = (255, 200, 60)
SILVER = (200, 205, 215)
BRONZE = (205, 140, 80)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _footer(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    text = "Powered By @SEASON"
    f = _font(FONT_REGULAR, 20)
    bbox = draw.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    draw.text(((width - w) / 2, height - 40), text, font=f, fill=TEXT_MUTED)


def _load_avatar(avatar_bytes: bytes | None, size: int) -> Image.Image:
    if avatar_bytes:
        try:
            img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            img = img.resize((size, size))
        except Exception:
            img = _placeholder_avatar(size)
    else:
        img = _placeholder_avatar(size)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=size // 5, fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out


def _placeholder_avatar(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), ACCENT_SOFT)
    d = ImageDraw.Draw(img)
    d.ellipse((size * 0.2, size * 0.15, size * 0.8, size * 0.65), fill=ACCENT)
    d.ellipse((size * 0.1, size * 0.55, size * 0.9, size * 1.15), fill=ACCENT)
    return img


def render_rank_card(
    display_name: str,
    username: str,
    level: int,
    xp_into_level: int,
    xp_for_next_level: int,
    rank_position: int,
    total_ranked: int,
    total_messages: int,
    avatar_bytes: bytes | None = None,
) -> bytes:
    width, height = 1000, 360
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Accent side bar
    draw.rectangle((0, 0, 10, height), fill=ACCENT)

    # Avatar
    avatar_size = 160
    avatar = _load_avatar(avatar_bytes, avatar_size)
    img.paste(avatar, (50, 50), avatar)

    # Name + username
    draw.text((240, 55), display_name, font=_font(FONT_BOLD, 40), fill=TEXT_WHITE)
    draw.text((240, 105), f"@{username}" if username else "", font=_font(FONT_REGULAR, 26), fill=ACCENT)

    # Level label
    draw.text((240, 155), f"Current Level: {level}", font=_font(FONT_BOLD, 28), fill=TEXT_WHITE)

    # Progress bar
    bar_x, bar_y, bar_w, bar_h = 240, 200, 620, 22
    _rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=11, fill=ACCENT_SOFT)
    if xp_for_next_level > 0:
        progress = min(1.0, xp_into_level / xp_for_next_level)
    else:
        progress = 1.0
    filled_w = int(bar_w * progress)
    if filled_w > 0:
        _rounded_rect(draw, (bar_x, bar_y, bar_x + max(filled_w, bar_h), bar_y + bar_h), radius=11, fill=ACCENT)
    draw.text((bar_x + bar_w + 15, bar_y - 4), str(level + 1), font=_font(FONT_BOLD, 26), fill=TEXT_WHITE)

    # Stat pills: Rank, Chat Message Count
    _stat_pill(draw, 50, 250, "Rank", f"#{rank_position}/{total_ranked}")
    _stat_pill(draw, 380, 250, "Chat Message Count", f"{total_messages} Messages")

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _stat_pill(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, value: str) -> None:
    draw.text((x, y), label, font=_font(FONT_REGULAR, 22), fill=TEXT_MUTED)
    _rounded_rect(draw, (x, y + 30, x + 320, y + 75), radius=20, fill=ACCENT_SOFT)
    draw.text((x + 20, y + 40), value, font=_font(FONT_BOLD, 24), fill=TEXT_WHITE)


def render_streak_card(
    display_name: str,
    username: str,
    current_streak: int,
    best_streak: int,
    best_streak_range: str,
    avatar_bytes: bytes | None = None,
) -> bytes:
    width, height = 1000, 340
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 10, height), fill=ACCENT)

    avatar_size = 180
    avatar = _load_avatar(avatar_bytes, avatar_size)
    img.paste(avatar, (50, 60), avatar)
    draw.text((50, 250), f"@{username}" if username else display_name, font=_font(FONT_BOLD, 24), fill=TEXT_WHITE)

    draw.text((280, 55), "Streak Report", font=_font(FONT_BOLD, 46), fill=TEXT_WHITE)

    draw.text((280, 140), f"🔥  Current Streak: {current_streak}", font=_font(FONT_BOLD, 28), fill=(255, 140, 60))
    draw.text((280, 185), f"🏆  Best Streak: {best_streak}", font=_font(FONT_BOLD, 28), fill=GOLD)
    draw.text((280, 230), f"📅  Best Streak Range: {best_streak_range}", font=_font(FONT_REGULAR, 24), fill=TEXT_MUTED)

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_leaderboard_card(
    title: str,
    subtitle: str,
    entries: list[dict],  # [{"name": str, "username": str, "value": int, "avatar_bytes": bytes|None}]
) -> bytes:
    """Top-3 podium style card used for /daily /weekly /monthly chatter leaderboards."""
    width, height = 1100, 700
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw.text((width / 2, 40), title, font=_font(FONT_BOLD, 46), fill=TEXT_WHITE, anchor="ma")
    draw.text((width / 2, 100), subtitle, font=_font(FONT_REGULAR, 26), fill=TEXT_MUTED, anchor="ma")

    podium_colors = [GOLD, SILVER, BRONZE]
    card_w, card_h = 280, 320
    gap = 40
    total_w = card_w * 3 + gap * 2
    start_x = (width - total_w) / 2
    base_y = 620

    order = [1, 0, 2] if len(entries) >= 3 else list(range(len(entries)))  # #1 in the middle
    heights = {0: 340, 1: 280, 2: 240}

    for slot, idx in enumerate(order):
        if idx >= len(entries):
            continue
        entry = entries[idx]
        x = start_x + slot * (card_w + gap)
        card_top = base_y - heights[idx]
        color = podium_colors[idx]

        _rounded_rect(draw, (x, card_top, x + card_w, base_y), radius=18, fill=ACCENT_SOFT)
        draw.rectangle((x, card_top, x + card_w, card_top + 8), fill=color)

        rank_label = f"#{idx + 1}"
        draw.text((x + card_w / 2, card_top + 25), rank_label, font=_font(FONT_BOLD, 36), fill=color, anchor="ma")

        avatar_size = 90
        avatar = _load_avatar(entry.get("avatar_bytes"), avatar_size)
        img.paste(avatar, (int(x + (card_w - avatar_size) / 2), int(card_top + 75)), avatar)

        name = entry["name"]
        draw.text((x + card_w / 2, card_top + 180), name, font=_font(FONT_BOLD, 24), fill=TEXT_WHITE, anchor="ma")
        draw.text(
            (x + card_w / 2, card_top + 215),
            f"{entry['value']} messages",
            font=_font(FONT_REGULAR, 20), fill=TEXT_MUTED, anchor="ma",
        )

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_reputation_leaderboard_card(entries: list[dict]) -> bytes:
    """entries: [{"name": str, "username": str, "rep": int}] ordered by rep desc."""
    width = 1100
    row_h = 90
    header_h = 160
    height = header_h + row_h * max(len(entries), 1) + 60
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Logo circle
    draw.ellipse((width / 2 - 40, 20, width / 2 + 40, 100), fill=ACCENT_SOFT, outline=ACCENT, width=3)
    draw.text((width / 2, 60), "💬", font=_font(FONT_REGULAR, 36), fill=TEXT_WHITE, anchor="mm")

    # Header row
    draw.text((80, 120), "RANK", font=_font(FONT_BOLD, 24), fill=(255, 170, 60))
    draw.text((220, 120), "USER", font=_font(FONT_BOLD, 24), fill=(255, 170, 60))
    draw.text((width - 260, 120), "🎁 Reputation", font=_font(FONT_BOLD, 24), fill=(70, 210, 140))

    row_colors = {0: GOLD, 1: SILVER, 2: BRONZE}
    y = header_h
    for idx, entry in enumerate(entries):
        row_bg = ACCENT_SOFT
        rank_bg = row_colors.get(idx, (30, 33, 40))
        text_color = BG_COLOR if idx in row_colors else TEXT_WHITE

        _rounded_rect(draw, (60, y, width - 60, y + row_h - 15), radius=16, fill=row_bg)
        _rounded_rect(draw, (60, y, 200, y + row_h - 15), radius=16, fill=rank_bg)

        rank_text = f"#{idx + 1}"
        draw.text((130, y + (row_h - 15) / 2), rank_text, font=_font(FONT_BOLD, 30), fill=text_color, anchor="mm")

        name_text = entry["name"]
        if idx == 0:
            name_text += "  👑"
        draw.text((230, y + (row_h - 15) / 2), name_text, font=_font(FONT_BOLD, 28), fill=TEXT_WHITE, anchor="lm")

        draw.text(
            (width - 100, y + (row_h - 15) / 2), str(entry["rep"]),
            font=_font(FONT_BOLD, 30), fill=(70, 210, 140), anchor="rm",
        )
        y += row_h

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
