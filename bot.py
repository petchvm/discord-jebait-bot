"""
Jebait Bot — entry point.

Milestone 2: track jebaits in a JSON file, with !jebait / !jebaitcount / !jebaitboard.
For now a !jebait is recorded immediately; the dispute flow (buttons + mod resolution)
is added in the next milestone.
"""

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import storage

# Read DISCORD_TOKEN from the .env file so the secret never lives in the code.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# message_content is a *privileged* intent, REQUIRED to read the text of "!" commands.
intents = discord.Intents.default()
intents.message_content = True

# Safety: never let echoed text (like a reason) ping @everyone/@here or roles.
# Individual user mentions (e.g. the accused) are still allowed.
allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)

bot = commands.Bot(command_prefix="!", intents=intents, allowed_mentions=allowed_mentions)


def _s(n):
    """Return 's' unless n is 1 — for simple pluralising."""
    return "" if n == 1 else "s"


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print("Jebait Bot is online.")


@bot.command(name="ping")
async def ping(ctx):
    """Health check."""
    await ctx.send("pong 🏓")


@bot.command(name="jebait")
async def jebait(ctx, member: discord.Member, *, reason: str = None):
    """Record a jebait against a user, with an optional reason."""
    if member.bot:
        await ctx.send("You can't jebait a bot. We never flake. 🤖")
        return
    if member.id == ctx.author.id:
        await ctx.send("You can't jebait yourself. Nice try. 😅")
        return

    # Tidy up the optional reason: trim, cap length, treat empty as "no reason".
    reason = (reason or "").strip()
    if len(reason) > 500:
        reason = reason[:500] + "…"
    reason = reason or None

    data = storage.load()
    storage.add_jebait(data, target_id=member.id, accuser_id=ctx.author.id, reason=reason)
    storage.save(data)
    count = storage.confirmed_count(data, member.id)

    reason_line = f"\n> {reason}" if reason else ""
    await ctx.send(
        f"🎣 {member.mention} has been **jebaited** by {ctx.author.display_name}!{reason_line}\n"
        f"They're now sitting on **{count}** jebait{_s(count)}."
    )


@bot.command(name="jebaitcount")
async def jebaitcount(ctx, member: discord.Member):
    """Show a user's current jebait count."""
    data = storage.load()
    count = storage.confirmed_count(data, member.id)
    await ctx.send(f"**{member.display_name}** has **{count}** jebait{_s(count)}.")


@bot.command(name="jebaitboard")
async def jebaitboard(ctx):
    """Show the jebait leaderboard."""
    data = storage.load()
    board = storage.leaderboard(data, limit=10)
    if not board:
        await ctx.send("No jebaits recorded yet. A spotless server... for now. 😇")
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
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    """Turn common command mistakes into friendly messages instead of tracebacks."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"You need to @mention someone. Try: `!{ctx.command.name} @user`")
    elif isinstance(error, (commands.MemberNotFound, commands.BadArgument)):
        await ctx.send("I couldn't find that user — make sure you @mention them.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # ignore unknown "!" commands
    else:
        print(f"Unhandled error in command {ctx.command}: {error!r}")
        await ctx.send("Something went wrong — check the bot's console for details.")


def main():
    if not TOKEN:
        raise SystemExit(
            "ERROR: No DISCORD_TOKEN found.\n"
            "Copy .env.example to a new file named .env and paste your bot token into it."
        )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
