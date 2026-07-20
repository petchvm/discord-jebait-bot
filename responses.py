"""
responses.py — varied, cheeky message templates so the bot doesn't feel robotic.

Each list holds interchangeable lines with {placeholders}. Call pick() to get one
at random, already formatted. Add your own lines freely — just keep the same
{placeholders} the caller fills in.
"""

import random

# {accuser} = display name, {target} = mention
ACCUSATION = [
    "🎣 **{accuser}** says {target} pulled a jebait!",
    "🎣 {target} stands accused of a jebait by **{accuser}**!",
    "🎣 **{accuser}** is calling out {target} for a classic bait-and-bail!",
    "🎣 Uh oh — **{accuser}** reckons {target} baited and ghosted!",
]

# {target} = mention  (accused clicked "Fair cop")
CONFIRMED_OWNED = [
    "🫡 {target} owned up — **jebait confirmed**.",
    "🫡 Respect the honesty — {target} admits it. **Confirmed**.",
    "🫡 {target} takes the L like a champ. **Jebait confirmed**.",
]

# {target} = mention  (accused stayed silent for the full window)
CONFIRMED_SILENCE = [
    "🤫 {target} went quiet... **jebait confirmed**. Silence speaks.",
    "🤫 Not a peep from {target} — **confirmed**. The guilty say nothing.",
    "🤫 {target} left it on read. **Jebait confirmed**.",
]

# {target} = mention, {id} = incident id  (accused clicked "Dispute")
DISPUTED = [
    "🧊 {target} **disputes** it! Frozen as **#{id}** for a mod to judge.",
    "🧊 Not so fast — {target} contests this. Frozen as **#{id}**.",
    "🧊 {target} pleads innocent! Frozen as **#{id}** until a mod rules.",
]


def pick(templates, **kwargs):
    """Return one random template from the list, formatted with the given values."""
    return random.choice(templates).format(**kwargs)
