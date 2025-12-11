from typing import Optional

import discord
from discord.ext import commands

from db.dkp_db import (
    init_db,
    add_dkp,
    remove_dkp,
    get_dkp,
    get_leaderboard,
)


class DKPCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db()

    @commands.command(name="dkp_add")
    @commands.has_permissions(manage_guild=True)
    async def dkp_add(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
        *reason: str,
    ):
        """Add DKP to a user."""
        if amount <= 0:
            await ctx.send("Amount must be a positive number.")
            return

        reason_text = " ".join(reason) if reason else None
        new_total = add_dkp(ctx.guild.id, member.id, amount, reason_text)

        msg = (
            f"Added **{amount} DKP** to {member.mention}. "
            f"New total: **{new_total}**."
        )
        if reason_text:
            msg += f"\nReason: {reason_text}"

        await ctx.send(msg)

    @commands.command(name="dkp_remove")
    @commands.has_permissions(manage_guild=True)
    async def dkp_remove(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
        *reason: str,
    ):
        """Remove DKP from a user."""
        if amount <= 0:
            await ctx.send("Amount must be a positive number.")
            return

        reason_text = " ".join(reason) if reason else None
        new_total = remove_dkp(ctx.guild.id, member.id, amount, reason_text)

        msg = (
            f"Removed **{amount} DKP** from {member.mention}. "
            f"New total: **{new_total}**."
        )
        if reason_text:
            msg += f"\nReason: {reason_text}"

        await ctx.send(msg)

    @commands.command(name="dkp")
    async def dkp_check(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        """Check DKP for yourself or another user."""
        target = member or ctx.author
        points = get_dkp(ctx.guild.id, target.id)
        await ctx.send(f"{target.mention} has **{points} DKP**.")

    @commands.command(name="dkp_top")
    async def dkp_top(self, ctx: commands.Context, limit: int = 10):
        """Show DKP leaderboard for this server."""
        limit = max(1, min(limit, 25))
        data = get_leaderboard(ctx.guild.id, limit)

        if not data:
            await ctx.send("No DKP data for this server yet.")
            return

        lines = []
        for rank, (user_id, points) in enumerate(data, start=1):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"<left server> ({user_id})"
            lines.append(f"**{rank}.** {name} — **{points} DKP**")

        embed = discord.Embed(
            title=f"{ctx.guild.name} DKP Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @dkp_add.error
    @dkp_remove.error
    async def dkp_perm_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "You need **Manage Server** permissions to use this command."
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(DKPCog(bot))
