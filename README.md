# Jebait Bot

A lighthearted Discord bot for the **Poogie Bois** Dota 2 server. It tracks "jebaits" — when someone
pings for a game in `looking-for-game`, gets takers, then flakes on them.

## How it works: the jury

Instead of a mod judging every case, the **server is the jury**:

1. Someone runs `/jebait @user [reason]` — this puts the user on trial.
2. The bot posts a message with **👍 Guilty** / **👎 Innocent** buttons that anyone can press. The
   accuser's claim counts as the first guilty vote.
3. Voting stays open for ~2 minutes with a live tally.
4. When it closes, if **guilty leads by 2**, the jebait is confirmed (+1). Otherwise it's acquitted
   and nothing is recorded.

Why a jury? The people who actually got left hanging are the fairest judges — and being **offline can
never auto-confirm** a jebait (silence proves nothing). No mod has to adjudicate.

## Commands

| Command | Who | What it does |
|---|---|---|
| `/jebait user reason` | anyone | Put someone on trial (reason required) — the server votes guilty/innocent. |
| `/jebaitcount user` | anyone | Show someone's jebait count. |
| `/jebaitboard` | anyone | The jebait leaderboard. |
| `/unjebait user` | mod | Remove someone's most recent jebait. |
| `/jebaithelp` | anyone | Explains how the jebait system works. |
| `/ping` | anyone | Check the bot is alive. |

"mod" = anyone with the **Manage Messages** permission. Everything is a Discord **slash command** —
type `/` in the server to see them all.

## Setup

New here? Follow the step-by-step **[beginner setup guide → SETUP.md](SETUP.md)**. It covers creating
the Discord bot, running it, and hosting it 24/7 on a Raspberry Pi.

## Configuration

**`.env`** (secrets + per-machine config — never committed):

| Key | What |
|---|---|
| `DISCORD_TOKEN` | Your bot token (required). |
| `GUILD_IDS` | Comma-separated server IDs to register commands in instantly. Blank = global (~1h). |

**Constants at the top of `bot.py`** (tune the vibe, then restart):

| Constant | Default | What |
|---|---|---|
| `VOTE_WINDOW_SECONDS` | `120` | How long the jury vote stays open. |
| `VERDICT_THRESHOLD` | `2` | How far guilty must lead innocent to convict. |
| `COOLDOWN_SECONDS` | `600` | How long before the same person can be tried again. |

## Notes

- **The bot token is a secret.** It lives in `.env`, which is gitignored and must never be committed.
- Data is stored in `data.json`, created on first run. It lives only on the machine running the bot.
- Built with Python + [discord.py](https://discordpy.readthedocs.io/), managed with
  [uv](https://docs.astral.sh/uv/).
