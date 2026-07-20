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

# {target} = mention  (the jury voted guilty)
VERDICT_GUILTY = [
    "🔨 The jury has spoken — {target} is **guilty**.",
    "🔨 {target} is going down. **Guilty** as charged.",
    "🔨 Case closed: {target} **jebaited**, and the server saw it.",
]

# {target} = mention  (not enough votes to convict)
VERDICT_ACQUITTED = [
    "🕊️ {target} walks free — not enough to convict.",
    "🕊️ The jury isn't buying it. {target} is **acquitted**.",
    "🕊️ Case dismissed. {target} lives to bait another day.",
]


def pick(templates, **kwargs):
    """Return one random template from the list, formatted with the given values."""
    return random.choice(templates).format(**kwargs)
