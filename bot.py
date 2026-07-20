"""
Jebait Bot — entry point (slash-command edition).

Milestone 2: track jebaits in a JSON file via the slash commands /jebait,
/jebaitcount, /jebaitboard. The dispute flow (buttons + mod resolution) is
added in the next milestone.

Slash commands must be registered ("synced") with Discord. If TEST_GUILD_ID is
set in .env, they register to just that server and appear INSTANTLY — ideal for
development. Leave it blank to register globally (can take up to ~1 hour).
"""

import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import storage

# Read config from .env so secrets never live in the code.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

# Slash commands don't read message text, so NO privileged intents are needed.
intents = discord.Intents.default()

# Safety: never let echoed text (like a reason) ping @everyone/@here or roles.
allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)


class JebaitBot(commands.Bot):
    async def setup_hook(self):
        """Runs once on startup — registers the slash commands with Discord."""
        try:
            if TEST_GUILD_ID:
                guild = discord.Object(id=int(TEST_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"Synced {len(synced)} slash commands to test guild {TEST_GUILD_ID}.")
            else:
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} slash commands globally (can take ~1h to appear).")
        except Exception as e:
            print(f"WARNING: could not sync slash commands: {e!r}")
            print("Tip: make sure the bot was invited with the 'applications.commands' scope.")


bot = JebaitBot(command_prefix="!", intents=intents, allowed_mentions=allowed_mentions)


def _s(n):
    """Return 's' unless n is 1 — for simple pluralising."""
    return "" if n == 1 else "s"


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("Jebait Bot is online.")


@bot.tree.command(name="ping", description="Check the bot is alive.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong 🏓")


@bot.tree.command(name="jebait", description="Accuse someone of a jebait (bailing after an LFG ping).")
@app_commands.describe(user="Who jebaited?", reason="Optional: what did they do?")
@app_commands.guild_only()
async def jebait(interaction: discord.Interaction, user: discord.Member, reason: str = None):
    if user.bot:
        await interaction.response.send_message("You can't jebait a bot. We never flake. 🤖", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message("You can't jebait yourself. Nice try. 😅", ephemeral=True)
        return

    # Tidy the optional reason: trim, cap length, treat empty as "no reason".
    reason = (reason or "").strip()
    if len(reason) > 500:
        reason = reason[:500] + "…"
    reason = reason or None

    data = storage.load()
    storage.add_jebait(data, target_id=user.id, accuser_id=interaction.user.id, reason=reason)
    storage.save(data)
    count = storage.confirmed_count(data, user.id)

    reason_line = f"\n> {reason}" if reason else ""
    await interaction.response.send_message(
        f"🎣 {user.mention} has been **jebaited** by {interaction.user.display_name}!{reason_line}\n"
        f"They're now sitting on **{count}** jebait{_s(count)}."
    )


@bot.tree.command(name="jebaitcount", description="Show a user's jebait count.")
@app_commands.describe(user="Whose count?")
@app_commands.guild_only()
async def jebaitcount(interaction: discord.Interaction, user: discord.Member):
    data = storage.load()
    count = storage.confirmed_count(data, user.id)
    await interaction.response.send_message(f"**{user.display_name}** has **{count}** jebait{_s(count)}.")


@bot.tree.command(name="jebaitboard", description="Show the jebait leaderboard.")
@app_commands.guild_only()
async def jebaitboard(interaction: discord.Interaction):
    data = storage.load()
    board = storage.leaderboard(data, limit=10)
    if not board:
        await interaction.response.send_message("No jebaits recorded yet. A spotless server... for now. 😇")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for rank, (uid, count) in enumerate(board):
        marker = medals[rank] if rank < 3 else f"**{rank + 1}.**"
        # Mentions inside an embed show the name but never ping.
        lines.append(f"{marker} <@{uid}> — **{count}** jebait{_s(count)}")

    embed = discord.Embed(
        title="🎣 Jebait Leaderboard",
        description="\n".join(lines),
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Friendly handling for slash-command errors (e.g. permission failures)."""
    if isinstance(error, app_commands.NoPrivateMessage):
        msg = "This command only works in a server, not in DMs."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "You don't have permission to use that."
    else:
        print(f"Unhandled app command error: {error!r}")
        msg = "Something went wrong — check the bot's console."

    # Respond safely whether or not the command already replied.
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


def main():
    if not TOKEN:
        raise SystemExit(
            "ERROR: No DISCORD_TOKEN found.\n"
            "Copy .env.example to a new file named .env and paste your bot token into it."
        )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
