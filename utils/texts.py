"""Message copy for the moderator system screens."""

STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}

VERIFICATION_BADGE = {
    "trusted": "🛡️ Trusted",
    "verified": "✅ Verified",
    "unverified": "⚪ New",
}


def moderators_list_text(count: int) -> str:
    if count == 0:
        return "There are no moderators listed yet. Please check back later."
    return f"📋 Moderator Directory\n\n{count} moderator(s) available. Tap a name to view their profile."


def moderator_profile_text(mod: dict, community: dict | None, services: list[dict], review_count: int) -> str:
    badge = VERIFICATION_BADGE.get(mod["verification_status"], "")
    status = "🟢 Active" if mod["active_status"] else "🔴 Inactive"
    rating = mod["reputation_score"] or 0
    rating_str = f"{rating:.1f}/5" if review_count else "No ratings yet"

    lines = [
        f"{mod['display_name']}  {badge}",
        f"@{mod['username']} · {mod['role']} · {status}",
        "",
        mod["bio"] or "No bio provided.",
        "",
        f"⭐ Rating: {rating_str} ({review_count} review(s))",
    ]
    if community:
        lines.append(f"🏘️ Community: {community['name']}")
    if services:
        names = ", ".join(s["name"] for s in services)
        lines.append(f"🛠️ Services: {names}")
    if mod.get("notes"):
        lines.append(f"📝 Notes: {mod['notes']}")
    return "\n".join(lines)


def service_list_text(mod: dict, services: list[dict]) -> str:
    if not services:
        return f"{mod['display_name']} hasn't listed any services yet."
    lines = [f"🛠️ Services — {mod['display_name']}\n"]
    for s in services:
        desc = f" — {s['description']}" if s.get("description") else ""
        lines.append(f"• {s['name']}{desc}")
    return "\n".join(lines)


def reviews_list_text(mod: dict, reviews: list[dict]) -> str:
    if not reviews:
        return f"No approved reviews yet for {mod['display_name']}. Be the first to leave one!"
    lines = [f"💬 Reviews — {mod['display_name']}\n"]
    for r in reviews:
        stars = STARS.get(r["rating"], "")
        who = f"@{r['reviewer_username']}" if r["reviewer_username"] else "Anonymous"
        cat = f" ({r['service_category']})" if r.get("service_category") else ""
        lines.append(f"{stars}{cat} — {who}\n{r['review_text']}\n")
    return "\n".join(lines)
