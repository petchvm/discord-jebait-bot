"""
Jebait Bot — entry point.

Milestone 1: connect to Discord and respond to a simple !ping command.
Later milestones add the jebait tally, leaderboard, and dispute flow.
"""

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Read DISCORD_TOKEN from the .env file so the secret never lives in the code.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# "Intents" declare which events Discord should send the bot.
# message_content is a *privileged* intent and is REQUIRED to read the text of
# "!" commands. It must ALSO be switched on in the Discord Developer Portal.
intents = discord.Intents.default()
intents.message_content = True

# The bot responds to messages that start with "!" (e.g. !ping).
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Runs once, right after the bot successfully logs in."""
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("Jebait Bot is online. Try '!ping' in your server.")


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    """Health check so we know the bot is alive and listening."""
    await ctx.send("pong 🏓")


def main():
    if not TOKEN:
        raise SystemExit(
            "ERROR: No DISCORD_TOKEN found.\n"
            "Copy .env.example to a new file named .env and paste your bot token into it."
        )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
