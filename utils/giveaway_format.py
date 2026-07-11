"""
Builds the caption text shown on a live giveaway post in the group.
"""
import datetime as dt


def _countdown_string(ends_at_iso: str) -> str:
    ends_at = dt.datetime.fromisoformat(ends_at_iso)
    now = dt.datetime.utcnow()
    remaining = ends_at - now
    if remaining.total_seconds() <= 0:
        return "Ended"
    days = remaining.days
    hours, rem = divmod(remaining.seconds, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ", ".join(parts)


def format_giveaway_caption(giveaway: dict, entry_count: int, ended: bool = False) -> str:
    lines = [
        f"🎉 <b>{giveaway['prize']} GIVEAWAY</b>",
        f"Hosted By: @{giveaway['host_username']}",
        "",
    ]
    if giveaway.get("conditions"):
        lines.append("<b>Giveaway Conditions:</b>")
        for cond in giveaway["conditions"].splitlines():
            cond = cond.strip()
            if cond:
                lines.append(f"• {cond}")
        lines.append("")

    lines.append(f"<b>Entries:</b> {entry_count}")
    lines.append("")

    if ended:
        lines.append("🏁 <b>This giveaway has ended.</b>")
    else:
        lines.append(f"<b>Giveaway Ends In:</b> {_countdown_string(giveaway['ends_at'])}")
        lines.append("")
        lines.append("To participate in the giveaway, press the button below")

    return "\n".join(lines)


def format_requirements_message(channels: list[str]) -> str:
    lines = ["You don't meet the requirements to enter this giveaway:"]
    for ch in channels:
        lines.append(f"☐ Join @{ch}")
    return "\n".join(lines)


def format_winner_announcement(giveaway: dict, winner: dict | None) -> str:
    if winner is None:
        return f"🏁 The <b>{giveaway['prize']}</b> giveaway has ended — no valid entries were received."
    name = f"@{winner['username']}" if winner.get("username") else winner.get("first_name", "the winner")
    return (
        f"🎉 <b>Giveaway Ended!</b>\n\n"
        f"Congratulations {name} — you won the <b>{giveaway['prize']}</b> giveaway! 🏆"
    )
