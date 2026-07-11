"""
Sample data for development/demo. Run with:  python -m data.seed_data
Safe to re-run — skips moderators that already exist by username.
"""
import asyncio

from database.db import db, init_db


SAMPLE_COMMUNITIES = [
    {
        "name": "Insta Recovery Hub",
        "link": "https://t.me/instarecoveryhub_demo",
        "description": "Community focused on Instagram account recovery and unbans.",
        "owner_name": "alex_mod",
    },
    {
        "name": "MM Trade Zone",
        "link": "https://t.me/mmtradezone_demo",
        "description": "Middleman services for safe trading.",
        "owner_name": "riley_mod",
    },
]

SAMPLE_MODERATORS = [
    {
        "username": "alex_mod",
        "display_name": "Alex",
        "role": "Senior Moderator",
        "bio": "Helping with Instagram unbans and account recovery for 2+ years.",
        "contact_username": "alex_mod",
        "verification_status": "trusted",
        "notes": "Fastest average response time in the team.",
        "community_index": 0,
        "services": [
            ("Instagram unban", "Full appeal process handled end-to-end."),
            ("Account recovery help", "Recovering hacked or locked accounts."),
        ],
    },
    {
        "username": "riley_mod",
        "display_name": "Riley",
        "role": "Moderator",
        "bio": "Trusted middleman for trades and deals within the community.",
        "contact_username": "riley_mod",
        "verification_status": "verified",
        "notes": "",
        "community_index": 1,
        "services": [
            ("Middleman", "Secure escrow-style trade facilitation."),
            ("Dispute help", "Mediating disagreements between traders."),
        ],
    },
]


async def seed() -> None:
    await init_db()

    community_ids = []
    for c in SAMPLE_COMMUNITIES:
        cid = await db.create_community(c["name"], c["link"], c["description"], c["owner_name"])
        community_ids.append(cid)

    for m in SAMPLE_MODERATORS:
        existing = await db.get_moderator_by_username(m["username"])
        if existing:
            print(f"Skipping {m['username']} (already exists)")
            continue
        mod_id = await db.create_moderator(
            username=m["username"],
            display_name=m["display_name"],
            role=m["role"],
            bio=m["bio"],
            community_id=community_ids[m["community_index"]],
            contact_username=m["contact_username"],
            verification_status=m["verification_status"],
            notes=m["notes"],
        )
        for name, desc in m["services"]:
            await db.add_service(mod_id, name, desc)
        print(f"Created moderator {m['display_name']} (id={mod_id})")

    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
