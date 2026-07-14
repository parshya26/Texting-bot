"""
Generates the PNG images shown by /rank, /streak, /daily /weekly /monthly,
and /reps. Bigger, data-rich cards in a consistent "bordered dark card"
design language (original artwork — inspired by the general composition of
community rank-card bots, not a copy of any specific one's graphics).

Every card ends with the "Powered By @SEASON" footer.
"""
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONTS_DIR = Path(__file__).parent.parent / "fonts"
FONT_BOLD = str(FONTS_DIR / "DejaVuSans-Bold.ttf")
FONT_REGULAR = str(FONTS_DIR / "DejaVuSans.ttf")

BG_COLOR = (10, 10, 12)
CARD_BORDER = (235, 235, 240)
BOX_BORDER = (70, 72, 80)
TEXT_WHITE = (245, 245, 248)
TEXT_MUTED = (145, 148, 158)
TEXT_DIM = (90, 92, 100)
GOLD = (255, 203, 71)
SILVER = (206, 210, 220)
BRONZE = (206, 142, 87)
GREEN = (86, 214, 150)
FIRE = (255, 140, 66)


def _f(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _rr(draw: ImageDraw.ImageDraw, box, radius, fill=None, outline=None, width=1, corners=None):
    kwargs = {}
    if corners is not None:
        kwargs["corners"] = corners
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width, **kwargs)


def _watermark(img: Image.Image, rows: int = 3, cols: int = 6) -> None:
    """Faint repeating chat-bubble glyph pattern in the background, like the reference cards."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    w, h = img.size
    icon_font = _f(FONT_BOLD, 46)
    for r in range(rows):
        for c in range(cols):
            x = int(w * (c + 0.5) / cols)
            y = int(h * (r + 0.5) / rows)
            d.text((x, y), "💬", font=icon_font, fill=(255, 255, 255, 12), anchor="mm")
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0))


def _load_avatar(avatar_bytes: bytes | None, size: int) -> Image.Image:
    if avatar_bytes:
        try:
            img = Image.open(io.BytesIO(avatar_bytes)).convert("RGB")
            img = ImageOps.fit(img, (size, size))
        except Exception:
            img = _placeholder_avatar(size)
    else:
        img = _placeholder_avatar(size)

    out = Image.new("RGBA", (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=size // 5, fill=255)
    out.paste(img.convert("RGBA"), (0, 0), mask)
    return out


def _placeholder_avatar(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), (35, 37, 45))
    d = ImageDraw.Draw(img)
    d.ellipse((size * 0.22, size * 0.16, size * 0.78, size * 0.62), fill=(70, 74, 90))
    d.ellipse((size * 0.08, size * 0.58, size * 0.92, size * 1.18), fill=(70, 74, 90))
    return img


def _base_card(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (width, height), BG_COLOR)
    _watermark(img)
    draw = ImageDraw.Draw(img)
    _rr(draw, (6, 6, width - 6, height - 6), radius=28, outline=CARD_BORDER, width=3)
    return img, draw


def _footer(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    text = "Powered By @SEASON"
    f = _f(FONT_REGULAR, 22)
    draw.text((width / 2, height - 34), text, font=f, fill=TEXT_DIM, anchor="mm")


def _stat_box(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, label: str, value: str) -> None:
    _rr(draw, (x, y, x + w, y + h), radius=16, outline=BOX_BORDER, width=2)
    draw.text((x + 24, y + 18), label.upper(), font=_f(FONT_REGULAR, 20), fill=TEXT_MUTED)
    draw.text((x + 24, y + 48), value, font=_f(FONT_BOLD, 40), fill=TEXT_WHITE)


def _rank_pill(draw: ImageDraw.ImageDraw, right_x: int, y: int, text: str) -> None:
    f = _f(FONT_BOLD, 28)
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    pad_x, pad_y = 30, 16
    box_w, box_h = tw + pad_x * 2, 44 + pad_y
    x0 = right_x - box_w
    _rr(draw, (x0, y, right_x, y + box_h), radius=box_h // 2, fill=CARD_BORDER)
    draw.text((x0 + box_w / 2, y + box_h / 2), text, font=f, fill=(15, 15, 18), anchor="mm")


def render_rank_card(
    display_name: str,
    username: str,
    level: int,
    xp_into_level: int,
    xp_for_next_level: int,
    rank_position: int,
    total_ranked: int,
    total_messages: int,
    reputation: int = 0,
    avatar_bytes: bytes | None = None,
) -> bytes:
    width, height = 1474, 620
    img, draw = _base_card(width, height)

    avatar_size = 230
    avatar = _load_avatar(avatar_bytes, avatar_size)
    img.paste(avatar, (70, 70), avatar)

    draw.text((340, 90), display_name.upper(), font=_f(FONT_BOLD, 56), fill=TEXT_WHITE)
    draw.text((340, 160), f"@{username}" if username else "", font=_f(FONT_REGULAR, 34), fill=TEXT_MUTED)

    _rank_pill(draw, width - 70, 70, f"RANK #{rank_position}")

    box_y = 340
    box_h = 130
    gap = 40
    box_w = (width - 140 - gap) // 2
    _stat_box(draw, 70, box_y, box_w, box_h, "Chat Messages", str(total_messages))
    _stat_box(draw, 70 + box_w + gap, box_y, box_w, box_h, "Reputation", str(reputation))

    # XP progress bar
    bar_x, bar_y, bar_w, bar_h = 70, 520, width - 140, 26
    _rr(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=13, outline=BOX_BORDER, width=2)
    progress = min(1.0, xp_into_level / xp_for_next_level) if xp_for_next_level > 0 else 1.0
    filled = int((bar_w - 8) * progress)
    if filled > 0:
        fill_right = bar_x + 4 + filled
        # Round the left cap to match the track's rounded start; keep the
        # right edge square so a partial fill reads as "cut off here", not
        # as a floating rounded pill in the middle of the bar.
        is_full = filled >= bar_w - 8
        _rr(
            draw,
            (bar_x + 4, bar_y + 4, fill_right, bar_y + bar_h - 4),
            radius=8,
            fill=TEXT_WHITE,
            corners=(True, is_full, is_full, True),
        )

    draw.text((bar_x, bar_y - 40), f"{xp_into_level}/{xp_for_next_level} XP", font=_f(FONT_REGULAR, 26), fill=TEXT_MUTED)
    draw.text((bar_x + bar_w, bar_y - 40), f"LEVEL {level}", font=_f(FONT_BOLD, 30), fill=TEXT_WHITE, anchor="ra")

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_streak_card(
    display_name: str,
    username: str,
    current_streak: int,
    best_streak: int,
    best_streak_range: str,
    total_messages: int,
    avatar_bytes: bytes | None = None,
) -> bytes:
    width, height = 1474, 560
    img, draw = _base_card(width, height)

    avatar_size = 230
    avatar = _load_avatar(avatar_bytes, avatar_size)
    img.paste(avatar, (70, 70), avatar)

    draw.text((340, 90), display_name.upper(), font=_f(FONT_BOLD, 56), fill=TEXT_WHITE)
    draw.text((340, 160), f"@{username}" if username else "", font=_f(FONT_REGULAR, 34), fill=TEXT_MUTED)
    draw.text((340, 220), "STREAK REPORT", font=_f(FONT_BOLD, 24), fill=FIRE)

    box_y = 340
    box_h = 130
    gap = 30
    box_w = (width - 140 - gap * 2) // 3
    _stat_box(draw, 70, box_y, box_w, box_h, "🔥 Current Streak", str(current_streak))
    _stat_box(draw, 70 + box_w + gap, box_y, box_w, box_h, "🏆 Best Streak", str(best_streak))
    _stat_box(draw, 70 + (box_w + gap) * 2, box_y, box_w, box_h, "Chat Messages", str(total_messages))

    draw.text((70, 500), f"📅 Best Streak Range: {best_streak_range}", font=_f(FONT_REGULAR, 28), fill=TEXT_MUTED)

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_leaderboard_card(title: str, subtitle: str, entries: list[dict]) -> bytes:
    """entries: [{"name","username","value","avatar_bytes"}] — Top 3 Chatters podium."""
    width, height = 1474, 900
    img, draw = _base_card(width, height)

    draw.text((width / 2, 60), title.upper(), font=_f(FONT_BOLD, 54), fill=TEXT_WHITE, anchor="ma")
    draw.text((width / 2, 125), subtitle, font=_f(FONT_REGULAR, 28), fill=TEXT_MUTED, anchor="ma")

    podium_colors = [GOLD, SILVER, BRONZE]
    card_w, card_h = 380, 430
    gap = 50
    total_w = card_w * 3 + gap * 2
    start_x = (width - total_w) / 2
    base_y = 820

    order = [1, 0, 2] if len(entries) >= 3 else list(range(len(entries)))
    heights = {0: 460, 1: 380, 2: 330}

    for slot, idx in enumerate(order):
        if idx >= len(entries):
            continue
        entry = entries[idx]
        x = start_x + slot * (card_w + gap)
        card_top = base_y - heights[idx]
        color = podium_colors[idx]

        _rr(draw, (x, card_top, x + card_w, base_y), radius=20, outline=BOX_BORDER, width=2)
        _rr(draw, (x, card_top, x + card_w, card_top + 10), radius=5, fill=color)

        draw.text((x + card_w / 2, card_top + 35), f"#{idx + 1}", font=_f(FONT_BOLD, 46), fill=color, anchor="ma")

        avatar_size = 120
        avatar = _load_avatar(entry.get("avatar_bytes"), avatar_size)
        img.paste(avatar, (int(x + (card_w - avatar_size) / 2), int(card_top + 95)), avatar)

        draw.text((x + card_w / 2, card_top + 235), entry["name"], font=_f(FONT_BOLD, 30), fill=TEXT_WHITE, anchor="ma")
        draw.text(
            (x + card_w / 2, card_top + 280), f"{entry['value']} messages",
            font=_f(FONT_REGULAR, 24), fill=TEXT_MUTED, anchor="ma",
        )

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_reputation_leaderboard_card(entries: list[dict]) -> bytes:
    """entries: [{"name","username","rep"}] ordered by rep desc."""
    width = 1474
    row_h = 110
    header_h = 220
    height = header_h + row_h * max(len(entries), 1) + 80
    img, draw = _base_card(width, height)

    draw.ellipse((width / 2 - 55, 40, width / 2 + 55, 150), outline=CARD_BORDER, width=3)
    draw.text((width / 2, 95), "💬", font=_f(FONT_REGULAR, 46), fill=TEXT_WHITE, anchor="mm")
    draw.text((width / 2, 185), "REPUTATION LEADERBOARD", font=_f(FONT_BOLD, 34), fill=TEXT_WHITE, anchor="mm")

    draw.text((110, header_h - 20), "RANK", font=_f(FONT_BOLD, 24), fill=(255, 175, 70))
    draw.text((290, header_h - 20), "USER", font=_f(FONT_BOLD, 24), fill=(255, 175, 70))
    draw.text((width - 320, header_h - 20), "🎁 REPUTATION", font=_f(FONT_BOLD, 24), fill=GREEN)

    row_colors = {0: GOLD, 1: SILVER, 2: BRONZE}
    y = header_h + 20
    for idx, entry in enumerate(entries):
        rank_bg = row_colors.get(idx, (32, 34, 42))
        text_color = (15, 15, 18) if idx in row_colors else TEXT_WHITE

        _rr(draw, (80, y, width - 80, y + row_h - 20), radius=18, outline=BOX_BORDER, width=2)
        _rr(draw, (80, y, 260, y + row_h - 20), radius=18, fill=rank_bg)

        draw.text((170, y + (row_h - 20) / 2), f"#{idx + 1}", font=_f(FONT_BOLD, 34), fill=text_color, anchor="mm")

        name_text = entry["name"] + ("  👑" if idx == 0 else "")
        draw.text((290, y + (row_h - 20) / 2), name_text, font=_f(FONT_BOLD, 32), fill=TEXT_WHITE, anchor="lm")

        draw.text((width - 130, y + (row_h - 20) / 2), str(entry["rep"]), font=_f(FONT_BOLD, 34), fill=GREEN, anchor="rm")
        y += row_h

    _footer(draw, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
