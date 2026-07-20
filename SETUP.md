# Jebait Bot — Setup Guide

A beginner-friendly walkthrough to get Jebait Bot running from scratch and keep it online 24/7. No
prior Discord-bot experience needed. Four parts:

1. [Create the bot on Discord](#1-create-the-bot-on-discord)
2. [Get the code running](#2-get-the-code-running)
3. [Host it 24/7 on a Raspberry Pi](#3-host-it-247-on-a-raspberry-pi)
4. [Updating the bot](#4-updating-the-bot)

---

## 1. Create the bot on Discord

Do this once, in a browser, on your own Discord account.

1. Go to the **[Discord Developer Portal](https://discord.com/developers/applications)** and log in.
2. **New Application** → name it (e.g. "Jebait Bot") → **Create**.
3. Open the **Bot** tab → **Reset Token** → **Copy**. This token is your bot's password — keep it
   secret; you'll paste it into `.env` later. (You can only view it once; just reset again if lost.)
   - *No privileged intents needed* — this bot uses slash commands, which don't read message text.
4. Invite the bot: **OAuth2 → URL Generator**:
   - **Scopes:** check `bot` **and** `applications.commands`.
   - **Bot Permissions:** View Channels, Send Messages, Read Message History, Embed Links.
   - Copy the generated URL, open it, pick your server, and **Authorize**.

> **Tip:** make a private **test server** you own (Discord → the `+` button → *Create My Own*) and
> invite the bot there for testing. To add it to a server you don't own (like Poogie Bois), send that
> invite URL to the server's owner/admin — inviting a bot needs the "Manage Server" permission.

### Getting a server's ID (needed for `GUILD_IDS`)

Turn on **Settings → Advanced → Developer Mode**, then right-click a server's icon → **Copy Server ID**.

---

## 2. Get the code running

Works on any computer (your PC, or the Pi). It uses **[uv](https://docs.astral.sh/uv/)** to manage
Python and dependencies for you.

```bash
# Install uv once:
#   Windows (PowerShell):  winget install --id=astral-sh.uv -e
#   Linux / macOS:         curl -LsSf https://astral.sh/uv/install.sh | sh
# Reopen your terminal afterwards so `uv` is on your PATH (check: uv --version)

git clone https://github.com/petchvm/discord-jebait-bot.git
cd discord-jebait-bot
uv sync          # installs the pinned Python + dependencies automatically
```

Create your **`.env`** from the template:

```bash
cp .env.example .env       # Windows PowerShell: Copy-Item .env.example .env
```

Edit `.env` and fill in:

```
DISCORD_TOKEN=your-real-token-here
GUILD_IDS=your_test_server_id,poogie_bois_id
```

- `DISCORD_TOKEN` — the token you copied in Part 1.
- `GUILD_IDS` — comma-separated server IDs where commands should appear **instantly**. Leave blank to
  register globally instead (works everywhere the bot is, but takes up to ~1 hour to show up).

Run it:

```bash
uv run bot.py
```

You should see `Logged in as ...` and `Synced N slash commands ...`. In Discord, type `/` to see the
commands. Stop the bot with **Ctrl+C**.

---

## 3. Host it 24/7 on a Raspberry Pi

`uv run bot.py` only keeps the bot online while that terminal is open. To keep it running forever —
and restart automatically on boot or after a crash — set it up as a **systemd service** on a
Raspberry Pi (or any always-on Linux machine).

First do **Part 2 on the Pi** (install uv, clone, `uv sync`, create `.env`). Then, **from inside the
repo folder**, and with `uv` on your PATH (`uv --version` works):

```bash
# This auto-fills the correct paths for you (current folder, uv location, your username):
cat <<EOF | sudo tee /etc/systemd/system/jebait-bot.service
[Unit]
Description=Jebait Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=$(which uv) run bot.py
Restart=always
RestartSec=5
User=$(whoami)

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now jebait-bot
```

Check it:

```bash
systemctl status jebait-bot        # should say "active (running)"
journalctl -u jebait-bot -f        # live logs (Ctrl+C to stop watching — the bot keeps running)
```

Reboot the Pi (`sudo reboot`) and confirm the bot comes back online on its own.

---

## 4. Updating the bot

When there's new code to deploy:

```bash
cd ~/discord-jebait-bot
git pull
sudo systemctl restart jebait-bot        # on the Pi
# (running it by hand instead? just Ctrl+C and `uv run bot.py` again)
```

- If an update **adds a dependency**, run `uv sync` before restarting. Code-only changes don't need it.
- To change behaviour (vote length, threshold, cooldown), edit the constants at the top of `bot.py`,
  then pull + restart.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Commands don't appear in Discord | Check the logs say `Synced N ...` with no WARNING, then refresh Discord with **Ctrl+R**. |
| Log warns it couldn't sync / mentions `applications.commands` | The bot was invited without that scope — redo the invite (Part 1, step 4) with **both** scopes. |
| `LoginFailure` / "Improper token" | The `DISCORD_TOKEN` in `.env` is wrong — recopy it, with no quotes or spaces. |
| Service won't start | Run `journalctl -u jebait-bot -e` and read the last lines. |
| `uv sync` can't download Python (old 32-bit Pi OS) | uv's managed Python needs 64-bit. Use 64-bit Raspberry Pi OS, or install Python 3.12+ yourself. |
