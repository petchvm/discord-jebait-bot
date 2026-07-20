"""
storage.py — tiny JSON-file data layer for the jebait bot.

All state lives in one dict saved to data.json (kept right next to this file).
Saves are ATOMIC: we write to a temporary file first, then os.replace() swaps it
in as a single operation, so a crash mid-write can never corrupt data.json.

Shape:
{
  "next_id": 7,
  "users": {
    "<discord_user_id>": {
      "incidents": [
        {"id": 1, "accuser_id": "<id>", "reason": "flaked on turbo" | null,
         "timestamp": "2026-07-20T14:03:00+00:00", "status": "confirmed"}
      ]
    }
  }
}
Only confirmed jebaits are ever stored — the jury vote happens in memory, and an
acquittal saves nothing. A user's count is how many confirmed incidents they have.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

# Keep data.json next to the code no matter where the bot is launched from.
_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(_HERE, "data.json")


def load():
    """Read the database, or return a fresh empty one if the file is missing/empty."""
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return {"next_id": 1, "users": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    """Write the database to disk atomically (temp file, then replace)."""
    fd, tmp_path = tempfile.mkstemp(dir=_HERE, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, DATA_FILE)  # atomic swap
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _user(data, user_id):
    """Get (creating if needed) the record for a user id."""
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"incidents": []}
    return data["users"][uid]


def add_jebait(data, target_id, accuser_id, reason, points=1):
    """Add a confirmed jebait incident (worth `points`) to a user and return it."""
    user = _user(data, target_id)
    incident = {
        "id": data["next_id"],
        "accuser_id": str(accuser_id),
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "confirmed",
        "points": points,
    }
    data["next_id"] += 1
    user["incidents"].append(incident)
    return incident


def confirmed_count(data, user_id):
    """A user's total jebait points (a decisive verdict is worth more than one)."""
    uid = str(user_id)
    if uid not in data["users"]:
        return 0
    return sum(i.get("points", 1) for i in data["users"][uid]["incidents"] if i["status"] == "confirmed")


def leaderboard(data, limit=10):
    """Return [(user_id, confirmed_count), ...] sorted highest-first."""
    counts = [(uid, confirmed_count(data, uid)) for uid in data["users"]]
    counts = [(uid, c) for uid, c in counts if c > 0]
    counts.sort(key=lambda pair: pair[1], reverse=True)
    return counts[:limit]


def remove_latest_confirmed(data, user_id):
    """Remove and return the user's most recent confirmed incident, or None."""
    uid = str(user_id)
    rec = data["users"].get(uid)
    if not rec:
        return None
    confirmed = [i for i in rec["incidents"] if i["status"] == "confirmed"]
    if not confirmed:
        return None
    latest = max(confirmed, key=lambda i: i["timestamp"])
    rec["incidents"].remove(latest)
    return latest
