"""
Jebait Bot — entry point (slash-command edition).

Milestone 3: the dispute flow. /jebait posts a message with [Dispute ❌] and
[Fair cop ✅] buttons and a 60-second timer. Staying silent or clicking ✅ confirms
the jebait; clicking ❌ freezes it as "disputed" until a mod resolves it with
/jebaitresolve. /jebaitdisputes lists the frozen ones.

Nothing is saved until the accusation resolves, so a bot restart mid-window just
cancels that one accusation.

Slash commands are registered ("synced") with Discord. If TEST_GUILD_ID is set in
.env, they register to just that server and appear instantly.
"""

import os
from datetime import datetime
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import storage

# Read config from .env so secrets never live in the code.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

# How long the accused has to respond before silence counts as confirmed.
DISPUTE_WINDOW_SECONDS = 60

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

    @discord.ui.button(label="Dispute", emoji="❌", style=discord.ButtonStyle.danger)
    async def dispute(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.resolved = True
        self.stop()
        self._disable_buttons()
        incident, _ = self._record("disputed")
        await interaction.response.edit_message(
            content=(
                f"🧊 {self.target.mention} **disputes** this jebait!{self._reason_line()}\n"
                f"Frozen as disputed (**#{incident['id']}**). A mod can settle it with `/jebaitresolve`."
            ),
            view=self,
        )

    @discord.ui.button(label="Fair cop", emoji="✅", style=discord.ButtonStyle.success)
    async def fair_cop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.resolved = True
        self.stop()
        self._disable_buttons()
        _, count = self._record("confirmed")
        await interaction.response.edit_message(
            content=(
                f"🎣 {self.target.mention} owned up — **jebait confirmed**. 🫡{self._reason_line()}\n"
                f"That's **{count}** jebait{_s(count)} now."
            ),
            view=self,
        )

    async def on_timeout(self):
        if self.resolved:
            return
        self._disable_buttons()
        _, count = self._record("confirmed")
        if self.message:
            try:
                await self.message.edit(
                    content=(
                        f"🎣 {self.target.mention} stayed silent... **jebait confirmed**. 🤫{self._reason_line()}\n"
                        f"That's **{count}** jebait{_s(count)} now."
                    ),
                    view=self,
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

    reason = (reason or "").strip()
    if len(reason) > 500:
        reason = reason[:500] + "…"
    reason = reason or None

    view = JebaitView(target=user, accuser=interaction.user, reason=reason)
    reason_line = f"\n> {reason}" if reason else ""
    await interaction.response.send_message(
        content=(
            f"🎣 **{interaction.user.display_name}** accuses {user.mention} of a jebait!{reason_line}\n"
            f"{user.mention}, you've got **{DISPUTE_WINDOW_SECONDS}s** — own up, or dispute it."
        ),
        view=view,
    )
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
