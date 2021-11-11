from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from typing import Optional
import discord
import contextlib

from stillsupport.extensions.abc import MixinMeta
from stillsupport.extensions.mixin import settings


class StillSupportCloseTicketsMixin(MixinMeta):
    @settings.group()
    async def closetickets(self, ctx):
        """Select settings required to close tickets"""
        pass

    @closetickets.group()
    async def archive(self, ctx):
        """Customize ticket archive settings"""
        pass

    @archive.command(name="category")
    async def archive_category(self, ctx, category: discord.CategoryChannel):
        """Choose an archive category. Closed tickets will be moved here."""
        if not category.permissions_for(ctx.guild.me).manage_channels:
            await ctx.send(
                'I need `Manage Channels` perms in that category.'
            )
            return

        async with self.config.guild(ctx.guild).archive() as data:
            data["category"] = category.id
        await ctx.send(
            f"Archive category set to: {category.name}."
        )

    @archive.command(name="enable")
    async def archive_enable(self, ctx, yes_or_no: bool = None):
        """Enable ticket archiving. This will move closed tickets to an archive category."""
        async with self.config.guild(ctx.guild).archive() as data:
            if yes_or_no is None:
                data["enabled"] = not data["enabled"]
                yes_or_no = data["enabled"]
            else:
                data["enabled"] = yes_or_no

        if yes_or_no:
            await ctx.send("Ticket archiving enabled.")
        else:
            await ctx.send("Ticket archiving disabled.")

    @closetickets.command()
    async def reports(self, ctx, channel: discord.TextChannel = None):
        """Set a report channel to log opened and closed tickets. Leave blank to disable."""
        saving = getattr(channel, "id", 0)
        await self.config.guild(ctx.guild).report.set(saving)

        if not channel:
            await ctx.send("Reporting disabled.")
        else:
            await ctx.send(f"Report channel set to: {channel.mention}.")

    @closetickets.command()
    async def dm(self, ctx, yes_or_no: bool = None):
        """DM a member when their ticket is closed."""
        if yes_or_no is None:
            yes_or_no = not await self.config.guild(ctx.guild).dm()

        await self.config.guild(ctx.guild).dm.set(yes_or_no)
        if yes_or_no:
            await ctx.send("Ticket closed DM notifications enabled.")
        else:
            await ctx.send("Ticket closed DM notifications disabled.")

    @closetickets.command(name="closeonleave")
    async def close_ticket_on_leave(self, ctx, toggle: Optional[bool] = None):
        """Close tickets if the member who opened it leaves."""
        if toggle is None:
            toggle = not await self.config.guild(ctx.guild).closeonleave()

        await self.config.guild(ctx.guild).closeonleave.set(toggle)
        if toggle:
            await ctx.send(
                "Close on leave enabled."
            )
        else:
            await ctx.send("Tickets will remain open if the member who opened it leaves.")

    @closetickets.command(name="prune", aliases=["cleanup", "purge"])
    async def ticket_channel_prune(self, ctx, skip_confirmation: bool = False):
        """Remove all archived tickets. Must include `true` or `false` after the command."""
        category = self.bot.get_channel((await self.config.guild(ctx.guild).archive())["category"])
        if not category:
            await ctx.send("There is no archive category. Use `help archive category` for details.")
            return

        channels = category.text_channels

        if not skip_confirmation:
            message = await ctx.send(
                f"Are you sure you want to delete all {len(channels)} archived tickets?"
            )

            start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
            pred = ReactionPredicate.yes_or_no(message, ctx.author)
            await self.bot.wait_for("reaction_add", check=pred)

        if skip_confirmation or pred.result is True:
            progress = await ctx.send("Pruning archive . . .")
            for channel in channels:
                try:
                    await channel.delete()
                except discord.Forbidden:
                    await ctx.send(
                        "Oop. Make sure I have permission to view and manage channels."
                    )
                    return
                except discord.HTTPException:
                    continue

            with contextlib.suppress(discord.HTTPException):
                await progress.edit(content=f"Pruned archive of {len(channels)} tickets.")
        else:
            await ctx.send("Archive pruning cancelled.")
