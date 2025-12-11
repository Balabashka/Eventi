import os
import json
import random
import string
from datetime import datetime
from typing import Optional, Literal

import discord
from discord.ext import commands
from discord import app_commands

from db.dkp_db import add_dkp

SERVER_IDS = [
    1443658842008195205,
]

PREFS_FILE = "server_prefs.json"
EVENTS: dict[int, dict] = {}  # event_id -> data

# code -> {guild_id, event_id, amount, creator_id, used_by: set(user_ids)}
REWARD_CODES: dict[str, dict] = {}

# Load server preferences from JSON
if os.path.exists(PREFS_FILE):
    with open(PREFS_FILE, "r", encoding="utf-8") as f:
        SERVER_PREFS = json.load(f)
else:
    SERVER_PREFS = {}


def save_prefs() -> None:
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(SERVER_PREFS, f, indent=4)


def generate_reward_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(random.choices(alphabet, k=length))
    while code in REWARD_CODES:
        code = "".join(random.choices(alphabet, k=length))
    return code


def guild_objects() -> list[discord.Object]:
    return [discord.Object(id=g_id) for g_id in SERVER_IDS]


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ----------------- helpers -----------------

    async def get_or_create_events_channel(
        self,
        guild: discord.Guild,
    ) -> Optional[discord.TextChannel]:
        channel = discord.utils.get(guild.text_channels, name="events")

        if channel is None:
            print("events channel doesn't exist")
            try:
                channel = await guild.create_text_channel("events")
                print(f"[AUTO] Created 'events' channel in {guild.name}")
            except discord.Forbidden:
                print(
                    f"[WARN] Missing permission to create 'events' channel in "
                    f"{guild.name}"
                )
                return None
            except Exception as e:
                print(
                    f"[ERROR] Failed to create 'events' channel in "
                    f"{guild.name}: {e}"
                )
                return None

        return channel

    async def broadcast_event(
        self,
        game_name: str,
        embed: discord.Embed,
        origin_guild: discord.Guild,
    ):
        """Send the event embed to all other guilds that want this game."""
        for guild in self.bot.guilds:
            if guild.id == origin_guild.id:
                continue

            prefs = SERVER_PREFS.get(str(guild.id), [])
            if prefs and game_name not in prefs:
                continue

            channel = await self.get_or_create_events_channel(guild)
            if not channel:
                print(
                    f"[BROADCAST] Skipping {guild.name}: "
                    "no events channel or missing permissions"
                )
                continue

            broadcast_embed = embed.copy()
            footer_text = broadcast_embed.footer.text or ""
            if footer_text:
                footer_text += " • "
            footer_text += f"From: {origin_guild.name}"
            broadcast_embed.set_footer(text=footer_text)

            if channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(embed=broadcast_embed)
                    print(f"[BROADCAST] Event sent to {guild.name}")
                except discord.Forbidden:
                    print(
                        f"[ERROR] Cannot send message to events channel in "
                        f"{guild.name}"
                    )
            else:
                print(
                    f"[WARN] Cannot send messages in "
                    f"{guild.name}#{channel.name}"
                )

    # ----------------- listeners -----------------

    @commands.Cog.listener()
    async def on_ready(self):
        # Create events channel + sync slash commands in each guild
        for guild in self.bot.guilds:
            await self.get_or_create_events_channel(guild)
            try:
                await self.bot.tree.sync(guild=guild)
                print(f"[SLASH] Synced commands for {guild.name} ({guild.id})")
            except Exception as e:
                print(f"[SLASH] Failed to sync for {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.get_or_create_events_channel(guild)
        try:
            await self.bot.tree.sync(guild=guild)
            print(f"[SLASH] Synced commands for new guild {guild.name}")
        except Exception as e:
            print(f"[SLASH] Failed to sync for new guild {guild.name}: {e}")

    # ----------------- prefix debug -----------------

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.send("pong")

    # ----------------- /set_games -----------------

    @app_commands.command(
        name="set_games",
        description="Set games your server wants events for.",
    )
    @app_commands.guilds(*guild_objects())
    @app_commands.describe(
        games="Comma-separated list of games (e.g. Valorant, LoL, CS2)"
    )
    async def set_games(
        self,
        interaction: discord.Interaction,
        games: str,
    ):
        game_list = [g.strip() for g in games.split(",") if g.strip()]
        if not game_list:
            await interaction.response.send_message(
                "❌ You must specify at least one game.",
                ephemeral=True,
            )
            return

        SERVER_PREFS[str(interaction.guild.id)] = game_list
        save_prefs()

        await interaction.response.send_message(
            f"✅ Event preferences updated: {', '.join(game_list)}",
            ephemeral=True,
        )

    # ----------------- /create_event -----------------

    @app_commands.command(
        name="create_event",
        description="Create a gaming event.",
    )
    @app_commands.guilds(*guild_objects())
    @app_commands.describe(
        event_name="Name of the event",
        genre="Genre of the event",
        game_name="Game for the event",
        event_type="public or private",
        description="Description of the event",
        user_limit="Max number of users",
        start_time="Start time (YYYY-MM-DD HH:MM)",
        end_time="End time (YYYY-MM-DD HH:MM)",
        dkp_reward="DKP reward for this event (0 = none)",
    )
    async def create_event(
        self,
        interaction: discord.Interaction,
        event_name: str,
        genre: str,
        game_name: str,
        event_type: Literal["public", "private"],
        description: str,
        user_limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        dkp_reward: Optional[int] = None,
    ):
        # Parse start time
        if start_time is not None:
            try:
                start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid start time. Use: `YYYY-MM-DD HH:MM`",
                    ephemeral=True,
                )
                return
        else:
            start_dt = None

        # Parse end time
        if end_time is not None:
            try:
                end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid end time. Use: `YYYY-MM-DD HH:MM`",
                    ephemeral=True,
                )
                return
        else:
            end_dt = None

        # Normalize DKP reward
        if dkp_reward is None:
            dkp_reward = 0
        if dkp_reward < 0:
            await interaction.response.send_message(
                "❌ DKP reward cannot be negative.",
                ephemeral=True,
            )
            return

        event_id = len(EVENTS) + 1

        EVENTS[event_id] = {
            "name": event_name,
            "genre": genre,
            "game": game_name,
            "start": start_dt,
            "end": end_dt,
            "limit": user_limit,
            "type": event_type,
            "creator": interaction.user.id,
            "description": description,
            "dkp_reward": dkp_reward,
            "reward_code": None,
        }

        reward_code: Optional[str] = None
        if dkp_reward > 0:
            reward_code = generate_reward_code()
            EVENTS[event_id]["reward_code"] = reward_code
            REWARD_CODES[reward_code] = {
                "guild_id": interaction.guild.id,
                "event_id": event_id,
                "amount": dkp_reward,
                "creator_id": interaction.user.id,
                "used_by": set(),
            }

        embed = discord.Embed(
            title=f"🎮 Event: {event_name}",
            description="A new event has been created.",
            color=discord.Color.blurple(),
            timestamp=start_dt,
        )

        embed.add_field(name="Genre", value=genre, inline=True)
        embed.add_field(name="Game", value=game_name, inline=True)

        if start_dt:
            embed.add_field(
                name="Start Time",
                value=start_dt.strftime("%Y-%m-%d %H:%M"),
                inline=False,
            )

        if end_dt:
            embed.add_field(
                name="End Time",
                value=end_dt.strftime("%Y-%m-%d %H:%M"),
                inline=False,
            )

        if user_limit:
            embed.add_field(
                name="Participants",
                value=str(user_limit),
                inline=True,
            )

        embed.add_field(
            name="Event Type",
            value=event_type.capitalize(),
            inline=True,
        )

        if dkp_reward > 0:
            embed.add_field(
                name="DKP Reward",
                value=f"{dkp_reward} DKP (via reward code)",
                inline=True,
            )

        embed.add_field(
            name="Description",
            value=description,
            inline=False,
        )

        embed.set_footer(
            text=f"Event ID: {event_id} • Created by {interaction.user}"
        )

        channel = await self.get_or_create_events_channel(interaction.guild)
        if channel is None:
            await interaction.response.send_message(
                "Events channel not found or cannot be created.",
                ephemeral=True,
            )
            return

        await channel.send(embed=embed)

        if event_type.lower() == "public":
            await self.broadcast_event(game_name, embed, interaction.guild)

        if reward_code:
            await interaction.response.send_message(
                "✅ Event created.\n"
                f"Your DKP reward code is: `{reward_code}`\n"
                "Share this code with participants you want to reward.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "✅ Event created.",
                ephemeral=True,
            )

    # ----------------- /redeem_dkp -----------------

    @app_commands.command(
        name="redeem_dkp",
        description="Redeem a DKP reward code from an event.",
    )
    @app_commands.guilds(*guild_objects())
    @app_commands.describe(
        code="The DKP reward code you received from an event."
    )
    async def redeem_dkp(
        self,
        interaction: discord.Interaction,
        code: str,
    ):
        code = code.strip().upper()

        if code not in REWARD_CODES:
            await interaction.response.send_message(
                "❌ Invalid or expired code.",
                ephemeral=True,
            )
            return

        info = REWARD_CODES[code]

        if info["guild_id"] != interaction.guild.id:
            await interaction.response.send_message(
                "❌ This code does not belong to this server.",
                ephemeral=True,
            )
            return

        if interaction.user.id in info["used_by"]:
            await interaction.response.send_message(
                "❌ You have already redeemed this code.",
                ephemeral=True,
            )
            return

        amount = info["amount"]
        event_id = info["event_id"]
        event_data = EVENTS.get(event_id)
        event_name = event_data["name"] if event_data else f"Event {event_id}"

        new_total = add_dkp(
            server_id=interaction.guild.id,
            user_id=interaction.user.id,
            amount=amount,
            reason=f"Event reward ({event_name})",
        )

        info["used_by"].add(interaction.user.id)

        await interaction.response.send_message(
            f"✅ You received **{amount} DKP** for `{event_name}`.\n"
            f"Your new total DKP: **{new_total}**.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
