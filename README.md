# Jebait Bot

A lighthearted Discord bot for the **Poogie Bois** Dota 2 server. It tracks "jebaits" — when
someone pings people for a game in `looking-for-game` and then flakes on them.

> ⚠️ Work in progress — being built one feature at a time.

## Commands

| Command | Who | What it does |
|---|---|---|
| `!jebait @user [reason]` | anyone | Accuse someone of a jebait. They get a chance to dispute it. |
| `!jebaitcount @user` | anyone | Show someone's jebait count. |
| `!jebaitboard` | anyone | The jebait leaderboard. |
| `!jebaitdisputes` | anyone | List disputed jebaits waiting on a mod. |
| `!jebaitresolve <id> confirm\|dismiss` | mod | Settle a disputed jebait. |
| `!unjebait @user` | mod | Remove someone's most recent jebait. |
| `!jebaithelp` | anyone | List commands. |
| `!ping` | anyone | Check the bot is alive. |

## Running it (on your PC)

1. Install Python 3.12 or 3.13.
2. Clone this repo and open a terminal in the folder.
3. Create a virtual environment and install dependencies:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1      # Windows PowerShell
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and paste your Discord bot token into it.
5. Start the bot:
   ```powershell
   python bot.py
   ```

## Notes

- **The bot token is a secret.** It goes in `.env`, which is gitignored and must never be committed.
- Bot data is stored in `data.json`, created automatically on first run. It lives only on the
  machine that runs the bot.
