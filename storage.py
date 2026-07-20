"""
storage.py — tiny JSON-file data layer for the jebait bot.

All state lives in one dict saved to data.json (kept right next to this file).
Saves are ATOMIC: we write to a temporary file first, then os.replace() swaps it
in as a single operation. That way a crash mid-write can never leave a
half-written, corrupt data.json.

The shape of the data:
{
  "next_id": 7,                 # counter for unique incident ids
  "users": {
    "<discord_user_id>": {
      "incidents": [
        {
          "id": 1,
          "accuser_id": "<id>",
          "reason": "flaked on turbo" | null,
          "timestamp": "2026-07-20T14:03:00+00:00",
          "status": "confirmed"   # "confirmed" or "disputed"
        }
      ]
    }
  }
}
A user's "count" is simply how many of their incidents are "confirmed".
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


def add_jebait(data, target_id, accuser_id, reason, status="confirmed"):
    """Add a jebait incident to a user and return the created incident dict."""
    user = _user(data, target_id)
    incident = {
        "id": data["next_id"],
        "accuser_id": str(accuser_id),
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
    }
    data["next_id"] += 1
    user["incidents"].append(incident)
    return incident


def confirmed_count(data, user_id):
    """Number of CONFIRMED jebaits for a user."""
    uid = str(user_id)
    if uid not in data["users"]:
        return 0
    return sum(1 for i in data["users"][uid]["incidents"] if i["status"] == "confirmed")


def leaderboard(data, limit=10):
    """Return [(user_id, confirmed_count), ...] sorted highest-first."""
    counts = [(uid, confirmed_count(data, uid)) for uid in data["users"]]
    counts = [(uid, c) for uid, c in counts if c > 0]
    counts.sort(key=lambda pair: pair[1], reverse=True)
    return counts[:limit]


def find_incident(data, incident_id):
    """Return (user_id, incident_dict) for the given id, or (None, None)."""
    for uid, rec in data["users"].items():
        for inc in rec["incidents"]:
            if inc["id"] == incident_id:
                return uid, inc
    return None, None


def remove_incident(data, incident_id):
    """Delete an incident by id. Returns True if something was removed."""
    for rec in data["users"].values():
        for i, inc in enumerate(rec["incidents"]):
            if inc["id"] == incident_id:
                del rec["incidents"][i]
                return True
    return False


def list_disputes(data):
    """Return [(user_id, incident), ...] for all disputed incidents, oldest id first."""
    out = []
    for uid, rec in data["users"].items():
        for inc in rec["incidents"]:
            if inc["status"] == "disputed":
                out.append((uid, inc))
    out.sort(key=lambda pair: pair[1]["id"])
    return out
