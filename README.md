# Jebait Bot

A lighthearted Discord bot for the **Poogie Bois** Dota 2 server. It tracks "jebaits" — when
someone pings people for a game in `looking-for-game` and then flakes on them.

> ⚠️ Work in progress — being built one feature at a time.

## Commands

| Command | Who | What it does |
|---|---|---|
| `/jebait user [reason]` | anyone | Put someone on trial — the server votes guilty/innocent. |
| `/jebaitcount user` | anyone | Show someone's jebait count. |
| `/jebaitboard` | anyone | The jebait leaderboard. |
| `/unjebait user` | mod | Remove someone's most recent jebait. |
| `/jebaithelp` | anyone | Explains how the jebait system works. |
| `/ping` | anyone | Check the bot is alive. |

Commands are Discord **slash commands** — type `/` in the server to see them all.

## Running it (on your PC)

This project uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies.
The Python version is pinned in `.python-version` and the dependencies live in `pyproject.toml`.

1. Install uv once: `winget install --id=astral-sh.uv -e` (or see the uv docs).
2. Clone this repo and open a terminal in the folder.
3. Install everything — uv creates the environment and installs dependencies for you:
   ```powershell
   uv sync
   ```
4. Copy `.env.example` to `.env` and paste your Discord bot token into it.
5. Start the bot:
   ```powershell
   uv run bot.py
   ```

## Notes

- **The bot token is a secret.** It goes in `.env`, which is gitignored and must never be committed.
- Bot data is stored in `data.json`, created automatically on first run. It lives only on the
  machine that runs the bot.
