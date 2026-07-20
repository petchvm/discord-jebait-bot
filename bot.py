"""
Jebait Bot — entry point (slash-command edition).

The verdict is a COMMUNITY JURY VOTE. /jebait puts someone on trial: the bot posts
a message with 👍 Guilty / 👎 Innocent buttons that anyone can press for a fixed
window. The accuser's claim counts as the first guilty vote. When the window closes,
if guilty leads by VERDICT_THRESHOLD the jebait is confirmed (+1); otherwise it's
acquitted and nothing is recorded.

Why a jury (not the accused's silence + a mod):
- Being offline can never auto-confirm a jebait — only real votes do.
- No mod has to adjudicate; the people who got left hanging decide.

Timing: the vote closes at a FIXED time. We use our own asyncio timer as the
primary resolver (a View's built-in timeout resets on every click, which would let
the window drift), with the View's on_timeout as a backstop.

Slash commands are registered ("synced") with Discord. GUILD_IDS in .env lists the
servers to register them in instantly (blank = global, ~1h to appear).
"""

import asyncio
import os
import time
import traceback

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import responses
import storage

# Read config from .env so secrets never live in the code.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
# Comma-separated guild IDs to register commands in instantly (test server,
# Poogie Bois, ...). Blank = register globally (works everywhere, ~1h to appear).
GUILD_IDS = [g.strip() for g in os.getenv("GUILD_IDS", "").split(",") if g.strip()]

# The jury vote.
VOTE_WINDOW_SECONDS = 120  # how long voting stays open (a FIXED window)
VERDICT_THRESHOLD = 2      # guilty must lead innocent by this much to convict
# Anti pile-on: how long before the same person can be put on trial again.
COOLDOWN_SECONDS = 600     # 10 minutes

# Slash commands don't read message text, so NO privileged intents are needed.
intents = discord.Intents.default()

# Safety: never let echoed text (like a reason) ping @everyone/@here or roles.
allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)

# In-memory state (resets on restart, which is fine for a casual bot):
active_jebaits = set()    # user ids currently on trial (one trial at a time each)
last_accusation = {}      # user id -> epoch time of their last trial (for cooldown)
_pending_timers = set()   # strong refs so timer tasks aren't garbage-collected


class JebaitBot(commands.Bot):
    async def setup_hook(self):
        """Runs once on startup — registers the slash commands with Discord."""
        try:
            if GUILD_IDS:
                for gid in GUILD_IDS:
                    guild = discord.Object(id=int(gid))
                    self.tree.copy_global_to(guild=guild)
                    synced = await self.tree.sync(guild=guild)
                    print(f"Synced {len(synced)} slash commands to guild {gid}.", flush=True)
            else:
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} slash commands globally (~1h to appear).", flush=True)
        except Exception as e:
            print(f"WARNING: could not sync slash commands: {e!r}", flush=True)
            print("Tip: make sure the bot was invited with the 'applications.commands' scope.", flush=True)


bot = JebaitBot(command_prefix="!", intents=intents, allowed_mentions=allowed_mentions)


def _s(n):
    """Return 's' unless n is 1 — for simple pluralising."""
    return "" if n == 1 else "s"


def _fmt_duration(secs):
    """Format a number of seconds as e.g. '9m 30s'."""
    secs = max(int(secs), 0)
    m, s = divmod(secs, 60)
    if m and s:
        return f"{m}m {s}s"
    if m:
        return f"{m}m"
    return f"{s}s"


class JebaitJuryView(discord.ui.View):
    """A public jury vote — 👍 Guilty / 👎 Innocent, resolved when the window closes."""

    def __init__(self, origin: discord.Interaction, target: discord.Member,
                 accuser: discord.Member, reason: str):
        # Numeric timeout (NOT None). The View timeout also resets on each click, so
        # our asyncio timer (below) is the real, fixed deadline; on_timeout is a backstop
        # that runs a bit later if the timer ever fails.
        super().__init__(timeout=VOTE_WINDOW_SECONDS + 30)
        self.origin = origin          # the /jebait interaction — used to edit the message
        self.target = target
        self.accuser = accuser
        self.reason = reason
        self.resolved = False
        # The accuser's claim IS the first guilty vote.
        self.votes = {accuser.id: "guilty"}
        self.deadline = int(time.time()) + VOTE_WINDOW_SECONDS
        self.headline = responses.pick(
            responses.ACCUSATION, accuser=accuser.display_name, target=target.mention
        )

    def start(self):
        """Kick off the fixed-length voting timer (kept referenced so it isn't GC'd)."""
        print(f"[jury] trial started: {self.accuser.display_name} vs {self.target.display_name} "
              f"— closes in {VOTE_WINDOW_SECONDS}s", flush=True)
        try:
            task = asyncio.create_task(self._run())
            _pending_timers.add(task)
            task.add_done_callback(_pending_timers.discard)
        except Exception as e:
            # Don't let a timer hiccup break the command — on_timeout will still resolve it.
            print(f"[jury] could not start timer: {e!r}", flush=True)

    async def _run(self):
        try:
            await asyncio.sleep(VOTE_WINDOW_SECONDS)
            await self.resolve()
        except Exception as e:
            print(f"[jury] timer error: {e!r}", flush=True)

    async def on_timeout(self):
        # Backstop: resolve even if the asyncio timer never fired.
        await self.resolve()

    def _tally(self):
        guilty = sum(1 for v in self.votes.values() if v == "guilty")
        innocent = sum(1 for v in self.votes.values() if v == "innocent")
        return guilty, innocent

    def _reason_line(self):
        return f"\n> {self.reason}" if self.reason else ""

    def render(self):
        """The live voting message (updates as people vote)."""
        guilty, innocent = self._tally()
        return (
            f"⚖️ **The jury is out!**\n"
            f"{self.headline}{self._reason_line()}\n"
            f"Vote below — **guilty must lead by {VERDICT_THRESHOLD}** when voting closes "
            f"<t:{self.deadline}:R>.\n\n"
            f"👍 Guilty: **{guilty}**    👎 Innocent: **{innocent}**"
        )

    async def _cast(self, interaction: discord.Interaction, vote: str):
        if self.resolved:
            await interaction.response.send_message("Voting has closed on this one.", ephemeral=True)
            return
        # One vote per person; clicking again changes it.
        self.votes[interaction.user.id] = vote
        await interaction.response.edit_message(content=self.render(), view=self)

    @discord.ui.button(label="Guilty", emoji="👍", style=discord.ButtonStyle.danger)
    async def guilty(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._cast(interaction, "guilty")

    @discord.ui.button(label="Innocent", emoji="👎", style=discord.ButtonStyle.success)
    async def innocent(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._cast(interaction, "innocent")

    async def resolve(self):
        if self.resolved:
            return
        self.resolved = True
        self.stop()  # stop listening for further votes
        active_jebaits.discard(self.target.id)
        for child in self.children:
            child.disabled = True

        guilty, innocent = self._tally()
        convicted = guilty - innocent >= VERDICT_THRESHOLD
        print(f"[jury] verdict for {self.target.display_name}: {guilty}-{innocent} -> "
              f"{'GUILTY' if convicted else 'ACQUITTED'}", flush=True)

        if convicted:
            data = storage.load()
            storage.add_jebait(
                data, target_id=self.target.id, accuser_id=self.accuser.id, reason=self.reason
            )
            storage.save(data)
            count = storage.confirmed_count(data, self.target.id)
            verdict = responses.pick(responses.VERDICT_GUILTY, target=self.target.mention)
            content = (
                f"⚖️ **Verdict: GUILTY** — {guilty} to {innocent}\n"
                f"{verdict}{self._reason_line()}\n"
                f"That's **{count}** jebait{_s(count)} now."
            )
        else:
            verdict = responses.pick(responses.VERDICT_ACQUITTED, target=self.target.mention)
            content = f"⚖️ **Verdict: ACQUITTED** — {guilty} to {innocent}\n{verdict}"

        # Edit the trial message via the original interaction (token valid ~15 min).
        try:
            await self.origin.edit_original_response(content=content, view=self)
        except Exception as e:
            print(f"[jury] could not edit verdict message: {e!r}", flush=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})", flush=True)
    print("Jebait Bot is online.", flush=True)


@bot.tree.command(name="ping", description="Check the bot is alive.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong 🏓")


@bot.tree.command(name="jebait", description="Put someone on trial for a jebait (bailing after an LFG ping).")
@app_commands.describe(user="Who jebaited?", reason="What did they do? (required)")
@app_commands.guild_only()
async def jebait(interaction: discord.Interaction, user: discord.Member, reason: str):
    if user.bot:
        await interaction.response.send_message("You can't jebait a bot. We never flake. 🤖", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message("You can't jebait yourself. Nice try. 😅", ephemeral=True)
        return
    if user.id in active_jebaits:
        await interaction.response.send_message(
            f"{user.mention} is already on trial — let the jury finish first. ⚖️", ephemeral=True
        )
        return

    # Cooldown: don't let the same person be put on trial again too soon.
    elapsed = time.time() - last_accusation.get(user.id, 0.0)
    if elapsed < COOLDOWN_SECONDS:
        remaining = _fmt_duration(COOLDOWN_SECONDS - elapsed)
        await interaction.response.send_message(
            f"⏳ {user.mention} was just accused of jebaiting — give it {remaining} before the next one.",
            ephemeral=True,
        )
        return

    # Reason is required — tidy it and reject an empty/whitespace one.
    reason = reason.strip()
    if not reason:
        await interaction.response.send_message("Give a reason for the jebait.", ephemeral=True)
        return
    if len(reason) > 500:
        reason = reason[:500] + "…"

    view = JebaitJuryView(origin=interaction, target=user, accuser=interaction.user, reason=reason)
    active_jebaits.add(user.id)
    try:
        await interaction.response.send_message(content=view.render(), view=view)
    except Exception:
        active_jebaits.discard(user.id)
        raise
    last_accusation[user.id] = time.time()
    view.start()


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


@bot.tree.command(name="unjebait", description="(Mod) Remove someone's most recent jebait.")
@app_commands.describe(user="Whose most recent jebait to remove")
@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.guild_only()
async def unjebait(interaction: discord.Interaction, user: discord.Member):
    data = storage.load()
    removed = storage.remove_latest_confirmed(data, user.id)
    if removed is None:
        await interaction.response.send_message(
            f"{user.display_name} has no jebaits to remove.", ephemeral=True
        )
        return
    storage.save(data)
    count = storage.confirmed_count(data, user.id)
    await interaction.response.send_message(
        f"↩️ {interaction.user.display_name} wiped a jebait off {user.mention} "
        f"(#{removed['id']}). Back down to **{count}** jebait{_s(count)}."
    )


@bot.tree.command(name="jebaithelp", description="How the jebait system works.")
async def jebaithelp(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎣 How Jebait Bot works",
        description=(
            "A **jebait** is when someone pings for a game, gets takers, then flakes.\n\n"
            "**Call it out:** `/jebait @user <reason>`\n"
            "The whole server becomes the **jury** — everyone votes 👍 Guilty / 👎 Innocent "
            f"for {VOTE_WINDOW_SECONDS // 60} minutes. The accusation counts as the first guilty vote.\n"
            f"If guilty leads by **{VERDICT_THRESHOLD}** when time's up, the jebait sticks. "
            "Being offline can't convict you — only real votes do.\n\n"
            "**Tallies:** `/jebaitcount @user` · `/jebaitboard`\n"
            "**Mods** can undo a bad verdict with `/unjebait @user`.\n\n"
            f"You can't put the same person on trial twice within {COOLDOWN_SECONDS // 60} minutes."
        ),
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Friendly handling for slash-command errors, with a full traceback to the console."""
    if isinstance(error, app_commands.NoPrivateMessage):
        msg = "This command only works in a server, not in DMs."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "You don't have permission to use that (mods only)."
    else:
        print("[jebait] UNHANDLED COMMAND ERROR:", flush=True)
        traceback.print_exception(type(error), error, error.__traceback__)
        msg = "Something went wrong — check the bot's console."

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
