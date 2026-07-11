# Texting Support Bot

Full aiogram-3 Telegram bot for the @Texting community: support-portal forms
(Report/Appeal/Suggest/Feedback/Apply-for-Mod/Host-a-Giveaway), a moderator
directory with reviews, a live join-gated giveaway engine, a Beem-style
rank/streak/leaderboard system, and a reputation (/rep) system — all with an
admin approval workflow.

## 1. Project structure

```
texting_bot/
├── bot.py                        # Entry point
├── config.py                     # Env-based settings
├── requirements.txt
├── .env.example
├── assets/
│   └── banner.jpg                 # <-- put your "Support Portal" banner image here
├── fonts/
│   ├── DejaVuSans.ttf              # bundled fonts for image cards (portable)
│   └── DejaVuSans-Bold.ttf
├── database/
│   ├── schema.sql                   # full SQL schema (19 tables)
│   └── db.py                        # async data-access layer
├── callbacks/
│   └── factories.py                  # all structured CallbackData classes
├── states/
│   └── forms.py                       # FSM state groups for every form
├── keyboards/
│   ├── main_menu.py                    # home menu + confirm/cancel/anon
│   ├── appeal.py                        # Mute/Warning/Ban buttons
│   ├── moderators.py                     # directory/profile/review keyboards
│   ├── admin.py                           # approve/reject keyboards
│   └── giveaway_engine.py                  # Participate!/Join/Done keyboards
├── handlers/
│   ├── start.py               # /start, /cancel, home + owners
│   ├── report.py               # Report form (exact reference flow)
│   ├── appeal.py                # Appeal form
│   ├── suggest.py                # Suggestion form
│   ├── feedback.py                # Feedback form
│   ├── apply_mod.py                # Apply-for-Mod (open/closed toggle)
│   ├── giveaway.py                  # "Host a Giveaway" static contact message
│   ├── giveaway_engine.py            # live giveaway creation + entries
│   ├── moderators.py                  # directory/profile/services/reviews
│   ├── rank.py                         # /rank /streak /daily /weekly /monthly
│   ├── reputation.py                    # /rep /reps
│   ├── admin.py                          # full admin panel
│   └── message_tracker.py                 # passive group message counter
├── utils/
│   ├── session.py              # banner-message-edit + one-active-request lock
│   ├── admin_notify.py          # DMs admins on new submissions
│   ├── texts.py                  # moderator screen copy
│   ├── giveaway_format.py         # giveaway post caption + winner text
│   ├── giveaway_scheduler.py       # background task that ends giveaways
│   ├── rank_cards.py                # Pillow image generation (rank/streak/leaderboards)
│   └── telegram_helpers.py           # avatar-fetching helper
└── data/
    └── seed_data.py            # sample moderators for local testing
```

## 2. Core mechanics (matches the reference bot exactly)

- **Single edited message**: every form sends ONE banner photo, then only
  edits its caption/keyboard as the user answers — never sends new bubbles.
- **`/cancel`**: cancels whatever's active, appends
  "❌ Cancelled. Send /start to begin again." to the same message.
- **One active request at a time**: any other button while a form is open
  replies "You're already in the middle of a support request. Send /cancel
  to discard it and start over."
- **Confirm/Cancel/Submit-anonymously** on Report/Suggest/Feedback; Appeal
  and Apply-for-Mod have no anonymous option.
- **Admin reject flow**: admin taps ❌ Reject → bot asks for a reason → that
  reason is sent to the submitter: "❌ Your report has been reviewed and was
  not approved.\n\n<reason>"

## 3. Setup

```bash
cd texting_bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env:
#   BOT_TOKEN         - from @BotFather
#   ADMIN_IDS         - your Telegram user id(s), comma-separated
#   MAIN_CHAT_ID       - your group's chat id (negative number) — required
#                        for /rank /streak /rep and giveaways
#   BANNER_IMAGE_PATH  - defaults to ./assets/banner.jpg — put your image there
#   GIVEAWAY_HOST_CONTACT - username to DM for "Host a Giveaway" (no @)

python -m data.seed_data     # optional: adds 2 sample moderators
python bot.py
```

**Getting MAIN_CHAT_ID**: add the bot to your group, send any message, then
use a helper bot like @RawDataBot in the group — it shows the chat id
(a negative number for groups/supergroups).

**Bot permissions needed in the main group**:
- Turn off Privacy Mode via @BotFather (`/setprivacy`) so the bot can see
  every group message for rank/streak tracking.
- **Admin** in the group itself, and **admin in any channel/group you use as
  a giveaway join-requirement** — Telegram only lets a bot check membership
  reliably when it's an admin there.

## 4. Admin commands

| Command | Purpose |
|---|---|
| `/admin` | Menu of everything below |
| `/pending_reports` `/pending_appeals` `/pending_suggestions` `/pending_feedback` `/pending_applications` | Approve/reject queues |
| `/pending_reviews` | Approve/reject moderator reviews |
| `/mods` | Verify/unverify, activate/deactivate moderators |
| `/applications` | View/toggle whether Apply-for-Mod is open |
| `/creategiveaway` | Start the live giveaway creation flow (prize → conditions → required channels → duration → confirm) |

## 5. Adding a real moderator

```python
from database.db import db

mod_id = await db.create_moderator(
    username="simo_helper",
    display_name="Simo's Helper",
    role="Moderator",
    bio="Handles dispute resolution.",
    contact_username="simo_helper",
    verification_status="verified",
)
await db.add_service(mod_id, "Dispute help", "Mediates trade disagreements.")
```

Or extend `data/seed_data.py` and re-run `python -m data.seed_data`.

## 6. Notes on the rank/streak/reputation system

- All counters are scoped to `MAIN_CHAT_ID` only — no cross-group/global data.
- XP: 15–25 random XP per message, 60-second cooldown to prevent spam farming
  (tune in `config.py`: `xp_per_message_min/max`, `xp_cooldown_seconds`).
- Level formula: `level = floor(sqrt(xp / 50))` — tune via `xp_curve_divisor`.
- `/rep` is reply-based, 1 per giver per 24 hours, no self-rep, no rep-to-bots.
- Card art (`utils/rank_cards.py`) is an original dark/indigo design generated
  with Pillow — not a copy of any third-party bot's artwork — and every card
  ends with the "Powered By @SEASON" footer as requested.

## 7. Extending further

- New simple one-field form → follow the pattern in `handlers/feedback.py`.
- New moderator field → add the column to `schema.sql`, pass it as a kwarg to
  `create_moderator(...)`, surface it in `utils/texts.py`.
- Move to PostgreSQL later → only `database/db.py` needs rewriting; every
  handler already treats it as a black box returning plain dicts.
