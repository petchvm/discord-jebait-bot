"""
Jebait Bot — entry point (slash-command edition).

Milestone 4: polish. Adds a cooldown (no re-jebaiting someone too soon, and no
double-accusing while one is pending), a mod-only /unjebait to remove a tally,
randomised cheeky replies (see responses.py), and a /jebaithelp explainer.

Nothing is saved until an accusation resolves, so a bot restart mid-window just
cancels that one accusation.

Slash commands are registered ("synced") with Discord. If TEST_GUILD_ID is set in
.env, they register to just that server and appear instantly.
"""

import os
from datetime import datetime, timezone
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import responses
import storage

# Read config from .env so secrets never live in the code.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

# How long the accused has to respond before silence counts as confirmed.
DISPUTE_WINDOW_SECONDS = 60
# How long before the same person can be jebaited again (anti pile-on).
COOLDOWN_SECONDS = 600  # 10 minutes

# Slash commands don't read message text, so NO privileged intents are needed.
intents = discord.Intents.default()

# Safety: never let echoed text (like a reason) ping @everyone/@here or roles.
allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)

# User ids that currently have an accusation awaiting a response (in memory only).
active_jebaits = set()


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


def _fmt_duration(secs):
    """Format a number of seconds as e.g. '9m 30s'."""
    secs = max(int(secs), 0)
    m, s = divmod(secs, 60)
    if m and s:
        return f"{m}m {s}s"
    if m:
        return f"{m}m"
    return f"{s}s"


def _relative_ts(iso):
    """Turn a stored ISO timestamp into a Discord relative time like '5 minutes ago'."""
    try:
        return f"<t:{int(datetime.fromisoformat(iso).timestamp())}:R>"
    except Exception:
        return "recently"


class JebaitView(discord.ui.View):
    """The [Dispute ❌] [Fair cop ✅] buttons attached to a fresh accusation."""

    def __init__(self, target: discord.Member, accuser: discord.Member, reason):
        super().__init__(timeout=DISPUTE_WINDOW_SECONDS)
        self.target = target
        self.accuser = accuser
        self.reason = reason
        self.message = None  # set after sending, so on_timeout can edit it
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only the accused may press these buttons.
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(
                f"Only {self.target.mention} can respond to this jebait.", ephemeral=True
            )
            return False
        return True

    def _cleanup(self):
        active_jebaits.discard(self.target.id)

    def _disable_buttons(self):
        for child in self.children:
            child.disabled = True

    def _record(self, status):
        """Save the incident with its final status; return (incident, new_count)."""
        data = storage.load()
        incident = storage.add_jebait(
            data,
            target_id=self.target.id,
            accuser_id=self.accuser.id,
            reason=self.reason,
            status=status,
        )
        storage.save(data)
        count = storage.confirmed_count(data, self.target.id)
        return incident, count

    def _reason_line(self):
        return f"\n> {self.reason}" if self.reason else ""

    def _confirmed_suffix(self, count):
        return f"\nThat's **{count}** jebait{_s(count)} now."

    @discord.ui.button(label="Dispute", emoji="❌", style=discord.ButtonStyle.danger)
    async def dispute(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.resolved = True
        self.stop()
        self._cleanup()
        self._disable_buttons()
        incident, _ = self._record("disputed")
        text = responses.pick(responses.DISPUTED, target=self.target.mention, id=incident["id"])
        await interaction.response.edit_message(content=text + self._reason_line(), view=self)

    @discord.ui.button(label="Fair cop", emoji="✅", style=discord.ButtonStyle.success)
    async def fair_cop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.resolved = True
        self.stop()
        self._cleanup()
        self._disable_buttons()
        _, count = self._record("confirmed")
        text = responses.pick(responses.CONFIRMED_OWNED, target=self.target.mention)
        await interaction.response.edit_message(
            content=text + self._reason_line() + self._confirmed_suffix(count), view=self
        )

    async def on_timeout(self):
        if self.resolved:
            return
        self._cleanup()
        self._disable_buttons()
        _, count = self._record("confirmed")
        if self.message:
            try:
                text = responses.pick(responses.CONFIRMED_SILENCE, target=self.target.mention)
                await self.message.edit(
                    content=text + self._reason_line() + self._confirmed_suffix(count), view=self
                )
            except discord.HTTPException:
                pass


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
    if user.id in active_jebaits:
        await interaction.response.send_message(
            f"{user.mention} already has a jebait pending — let it play out first. ⏳", ephemeral=True
        )
        return

    # Cooldown: block re-accusing the same person too soon after their last incident.
    data = storage.load()
    last = storage.last_incident_time(data, user.id)
    if last is not None:
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            remaining = _fmt_duration(COOLDOWN_SECONDS - elapsed)
            await interaction.response.send_message(
                f"⏳ {user.mention} was just jebaited — give it {remaining} before the next one.",
                ephemeral=True,
            )
            return

    # Tidy the optional reason: trim, cap length, treat empty as "no reason".
    reason = (reason or "").strip()
    if len(reason) > 500:
        reason = reason[:500] + "…"
    reason = reason or None

    view = JebaitView(target=user, accuser=interaction.user, reason=reason)
    text = responses.pick(responses.ACCUSATION, accuser=interaction.user.display_name, target=user.mention)
    reason_line = f"\n> {reason}" if reason else ""
    content = (
        f"{text}{reason_line}\n"
        f"{user.mention}, you've got **{DISPUTE_WINDOW_SECONDS}s** — own up, or dispute it."
    )

    active_jebaits.add(user.id)
    try:
        await interaction.response.send_message(content=content, view=view)
    except Exception:
        active_jebaits.discard(user.id)
        raise
    try:
        view.message = await interaction.original_response()
    except discord.HTTPException:
        view.message = None


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


@bot.tree.command(name="jebaitdisputes", description="List jebaits currently frozen as disputed.")
@app_commands.guild_only()
async def jebaitdisputes(interaction: discord.Interaction):
    data = storage.load()
    disputes = storage.list_disputes(data)
    if not disputes:
        await interaction.response.send_message("No disputed jebaits right now. ✨", ephemeral=True)
        return

    lines = []
    for uid, inc in disputes[:15]:
        reason = inc["reason"] or "no reason given"
        lines.append(f"**#{inc['id']}** — <@{uid}> — \"{reason}\" — {_relative_ts(inc['timestamp'])}")
    if len(disputes) > 15:
        lines.append(f"…and {len(disputes) - 15} more.")

    embed = discord.Embed(
        title="🧊 Disputed jebaits",
        description="\n".join(lines),
        color=discord.Color.blue(),
    )
    embed.set_footer(text="Mods: resolve one with /jebaitresolve <id> confirm|dismiss")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="jebaitresolve", description="(Mod) Confirm or dismiss a disputed jebait.")
@app_commands.describe(
    incident_id="The disputed jebait's # (see /jebaitdisputes)",
    action="Confirm it, or throw it out",
)
@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.guild_only()
async def jebaitresolve(
    interaction: discord.Interaction, incident_id: int, action: Literal["confirm", "dismiss"]
):
    data = storage.load()
    uid, inc = storage.find_incident(data, incident_id)
    if inc is None:
        await interaction.response.send_message(f"No jebait with id #{incident_id}.", ephemeral=True)
        return
    if inc["status"] != "disputed":
        await interaction.response.send_message(
            f"#{incident_id} isn't disputed (it's already {inc['status']}).", ephemeral=True
        )
        return

    if action == "confirm":
        inc["status"] = "confirmed"
        storage.save(data)
        count = storage.confirmed_count(data, uid)
        await interaction.response.send_message(
            f"✅ Dispute **#{incident_id}** overruled by {interaction.user.display_name}. "
            f"<@{uid}> is now on **{count}** jebait{_s(count)}."
        )
    else:  # dismiss
        storage.remove_incident(data, incident_id)
        storage.save(data)
        await interaction.response.send_message(
            f"🗑️ Dispute **#{incident_id}** dismissed by {interaction.user.display_name}. That jebait is gone."
        )


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
            "**Call it out:** `/jebait @user [reason]`\n"
            "The accused gets **60 seconds** and two buttons:\n"
            "• **✅ Fair cop** — admits it, jebait confirmed\n"
            "• **❌ Dispute** — freezes it for a mod to judge\n"
            "Ignoring it counts as confirmed (silence = guilt 🤫).\n\n"
            "**Tallies:** `/jebaitcount @user` · `/jebaitboard`\n"
            "**Disputes:** `/jebaitdisputes` — mods settle with `/jebaitresolve`\n\n"
            f"You can't jebait the same person twice within {int(COOLDOWN_SECONDS // 60)} minutes."
        ),
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Friendly handling for slash-command errors (e.g. permission failures)."""
    if isinstance(error, app_commands.NoPrivateMessage):
        msg = "This command only works in a server, not in DMs."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "You don't have permission to use that (mods only)."
    else:
        print(f"Unhandled app command error: {error!r}")
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
