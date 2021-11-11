from redbot.core.utils.mod import is_admin_or_superior
from discord.ext import commands
from typing import Dict, Optional, TYPE_CHECKING
import discord
import contextlib
import asyncio


from stillsupport.extensions.abc import MixinMeta
from stillsupport.extensions.mixin import stillsupport

if discord.__version__ == "2.0.0a" or TYPE_CHECKING:
    from stillsupport.extensions.views.queue import Queue


class StillSupportBaseMixin(MixinMeta):
    async def report_close(self, ctx, ticket, author, guild_settings, reason):
        representing = author.mention if isinstance(author, discord.Member) else author
        channel = self.bot.get_channel(ticket["channel"])

        if guild_settings["report"] != 0:
            reporting_channel = self.bot.get_channel(guild_settings["report"])
            if reporting_channel:
                if await self.embed_requested(reporting_channel):
                    embed = discord.Embed(
                        title="Ticket Closed",
                        description=(
                            f"Ticket {channel.mention} opened by "
                            f"{representing} closed by "
                            f"{ctx.author.mention}."
                        ),
                        color=await ctx.embed_color(),
                    )
                    if reason:
                        embed.add_field(name="Reason", value=reason)
                    if ticket["assigned"]:
                        moderator = getattr(
                            ctx.guild.get_member(ticket["assigned"]),
                            "mention",
                            "Unknown Staff Member",
                        )
                        embed.add_field(
                            name="Staff Assigned", value=moderator,
                        )

                    await reporting_channel.send(embed=embed)
                else:
                    message = (
                        f"Ticket {channel.mention} opened by "
                        f"{representing} closed by "
                        f"{ctx.author.mention}."
                    )
                    if reason:
                        message += f"\n**Reason**: {reason}"

                    if ticket["assigned"]:
                        moderator = getattr(
                            ctx.guild.get_member(ticket["assigned"]),
                            "mention",
                            "Unknown Staff Member",
                        )
                        message += f"\nStaff Assigned: {moderator}"
                    await reporting_channel.send(
                        message, allowed_mentions=discord.AllowedMentions.none()
                    )

        if guild_settings["dm"] and isinstance(author, discord.Member):
            embed = discord.Embed(
                title="Ticket Closed",
                description=(
                    f"Your ticket no. {channel.mention} has been closed by {ctx.author.mention}."
                ),
                color=await ctx.embed_color(),
            )
            if reason:
                embed.add_field(name="Reason", value=reason)
            with contextlib.suppress(discord.HTTPException):
                await author.send(embed=embed)

    async def process_closed_ticket(
        self, ctx, guild_settings, channel, archive, author, added_users
    ):
        representing = author.mention if isinstance(author, discord.Member) else author
        if guild_settings["archive"]["enabled"] and channel and archive:
            for user in added_users:
                with contextlib.suppress(discord.HTTPException):
                    if user:
                        await channel.set_permissions(
                            user, send_messages=False, read_messages=True
                        )

            destination = channel or ctx

            await destination.send(
                f"Ticket {channel.mention} for {representing} has been closed. "
                "Archiving ticket in one minute . . .",
                allowed_mentions=discord.AllowedMentions.none(),
            )

            await asyncio.sleep(60)

            try:
                admin_roles = [
                    ctx.guild.get_role(role_id)
                    for role_id in (await self.bot._config.guild(ctx.guild).admin_role())
                    if ctx.guild.get_role(role_id)
                ]
                support_roles = [
                    ctx.guild.get_role(role_id)
                    for role_id in guild_settings["staffroles"]
                    if ctx.guild.get_role(role_id)
                ]

                all_roles = admin_roles + support_roles
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_channels=True,
                        manage_permissions=True,
                    ),
                }
                for role in all_roles:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    )
                for user in added_users:
                    if user:
                        overwrites[user] = discord.PermissionOverwrite(read_messages=False)
                await channel.edit(category=archive, overwrites=overwrites)
            except discord.HTTPException as e:
                await destination.send(f"Could not archive ticket: {str(e)}")
        else:
            destination = channel or ctx

            if channel:
                for user in added_users:
                    with contextlib.suppress(discord.HTTPException):
                        if user:
                            await channel.set_permissions(
                                user, send_messages=False, read_messages=True
                            )
            await destination.send(
                f"Ticket {channel.mention} for {representing} has been closed. "
                "Deleting ticket in one minute . . .",
                allowed_mentions=discord.AllowedMentions.none(),
            )

            await asyncio.sleep(60)

            if channel:
                try:
                    await channel.delete()
                except discord.HTTPException:
                    with contextlib.suppress(discord.HTTPException):
                        await destination.send(
                            "I no longer have permissions to manage channels, so I can't do anything with this ticket."
                        )

    @stillsupport.command()
    async def close(self, ctx, *, reason=None):
        """Close an open ticket"""
        guild_settings = await self.config.guild(ctx.guild).all()
        is_admin = await is_admin_or_superior(self.bot, ctx.author) or any(
            [ur.id in guild_settings["staffroles"] for ur in ctx.author.roles]
        )
        must_be_admin = not guild_settings["memberclose"]

        if not is_admin and must_be_admin:
            await ctx.send("Only Staff Members can close tickets.")
            return
        elif not is_admin:
            author = ctx.author  # no u
            author_id = author.id
        elif is_admin:
            # Let's try to get the current channel and get the author
            # If not, we'll default to ctx.author
            inverted = {}
            for author_id, tickets in guild_settings["created"].items():
                for ticket in tickets:
                    inverted[ticket["channel"]] = author_id
            try:
                author = ctx.guild.get_member(int(inverted[ctx.channel.id]))
                if author:
                    author_id = author.id
                else:
                    author_id = int(inverted[ctx.channel.id])
            except KeyError:
                author = ctx.author
                author_id = author.id

        if str(author_id) not in guild_settings["created"]:
            await ctx.send("They don't have an open ticket. <a:pepe_sideeye:894652027387396166>")
            return

        index = None
        if not guild_settings["created"][str(author_id)]:
            await ctx.send("You don't have any tickets open. <a:pepe_sideeye:894652027387396166> <a:pepe_sideeye:894652027387396166>")
            return
        elif len(guild_settings["created"][str(author_id)]) == 1:
            index = 0
        else:
            for i, ticket in enumerate(guild_settings["created"][str(author_id)]):
                if ticket["channel"] == ctx.channel.id:
                    index = i
                    break

            if index is None:
                await ctx.send(
                    "Hmm... You have multiple tickets open. Type this again in the ticket you want to close."
                )
                return

        ticket = guild_settings["created"][str(author_id)][index]
        channel = self.bot.get_channel(ticket["channel"])
        archive = self.bot.get_channel(guild_settings["archive"]["category"])
        added_users = [user for u in ticket["added"] if (user := ctx.guild.get_member(u))]
        added_users.append(author)

        # Again, to prevent race conditions...
        async with self.config.guild(ctx.guild).created() as created:
            del created[str(author_id)][index]

        await self.report_close(
            ctx=ctx,
            ticket=ticket,
            author=author or author_id,
            guild_settings=guild_settings,
            reason=reason,
        )

        await self.process_closed_ticket(
            ctx=ctx,
            guild_settings=guild_settings,
            channel=channel,
            archive=archive,
            author=author or author_id,
            added_users=added_users,
        )

    @stillsupport.command(name="add")
    async def ticket_add(self, ctx, user: discord.Member):
        """Add someone to an open ticket."""
        guild_settings = await self.config.guild(ctx.guild).all()
        is_admin = await is_admin_or_superior(self.bot, ctx.author) or any(
            [ur.id in guild_settings["staffroles"] for ur in ctx.author.roles]
        )
        must_be_admin = not guild_settings["memberedit"]

        if not is_admin and must_be_admin:
            await ctx.send("Only Staff can add/remove someone.")
            return
        elif not is_admin:
            author = ctx.author
            author_id = author.id
        elif is_admin:
            # Since the author isn't specified, and it's an admin, we need to guess on who
            # the author is
            inverted = {}
            for author_id, tickets in guild_settings["created"].items():
                for ticket in tickets:
                    inverted[ticket["channel"]] = author_id
            try:
                author = ctx.guild.get_member(int(inverted[ctx.channel.id]))
                if author:
                    author_id = author.id
                else:
                    author_id = int(inverted[ctx.channel.id])
            except KeyError:
                author = ctx.author
                author_id = author.id

        index = None

        if not guild_settings["created"][str(author_id)]:
            await ctx.send("You don't have any tickets open. <a:pepe_sideeye:894652027387396166> <a:pepe_sideeye:894652027387396166>")
            return
        elif len(guild_settings["created"][str(author_id)]) == 1:
            index = 0
        else:
            for i, ticket in enumerate(guild_settings["created"][str(author_id)]):
                if ticket["channel"] == ctx.channel.id:
                    index = i
                    break

            if index is None:
                await ctx.send(
                    "Hmm... You have multiple tickets open. Type this again in the ticket you want to close."
                )
                return

        channel = self.bot.get_channel(guild_settings["created"][str(author_id)][index]["channel"])

        if user.id in guild_settings["created"][str(author_id)][index]["added"]:
            await ctx.send("Member already added. <:look_phone:893502905200549890>")
            return

        adding_is_admin = await is_admin_or_superior(self.bot, user) or any(
            [ur.id in guild_settings["staffroles"] for ur in user.roles]
        )

        if adding_is_admin:
            await ctx.send("You can't assign Staff yourself. <:hm:893502960464711710>")
            return

        channel = self.bot.get_channel(guild_settings["created"][str(author_id)][index]["channel"])
        if not channel:
            await ctx.send("The ticket channel has been deleted.")
            return

        try:
            await channel.set_permissions(user, send_messages=True, read_messages=True)
        except discord.Forbidden:
            await ctx.send(
                "I no longer have permissions to manage channels, so I can't do anything with this ticket."
            )
            return

        async with self.config.guild(ctx.guild).created() as created:
            created[str(author_id)][index]["added"].append(user.id)

        await ctx.send(f"{user.mention} has been added to the ticket.")

    @stillsupport.command(name="remove")
    async def ticket_remove(self, ctx, user: discord.Member):
        """Remove someone from a ticket."""
        guild_settings = await self.config.guild(ctx.guild).all()
        is_admin = await is_admin_or_superior(self.bot, ctx.author) or any(
            [ur.id in guild_settings["staffroles"] for ur in ctx.author.roles]
        )
        must_be_admin = not guild_settings["memberedit"]

        if not is_admin and must_be_admin:
            await ctx.send("Only Staff can add/remove someone.")
            return
        elif not is_admin:
            author = ctx.author
            author_id = author.id
        elif is_admin:
            # Since the author isn't specified, and it's an admin, we need to guess on who
            # the author is
            inverted = {}
            for author_id, tickets in guild_settings["created"].items():
                for ticket in tickets:
                    inverted[ticket["channel"]] = author_id
            try:
                author = ctx.guild.get_member(int(inverted[ctx.channel.id]))
                if author:
                    author_id = author.id
                else:
                    author_id = int(inverted[ctx.channel.id])
            except KeyError:
                author = ctx.author
                author_id = author.id

        index = None

        if not guild_settings["created"][str(author_id)]:
            await ctx.send("You don't have any tickets open. <a:pepe_sideeye:894652027387396166>")
            return
        elif len(guild_settings["created"][str(author_id)]) == 1:
            index = 0
        else:
            for i, ticket in enumerate(guild_settings["created"][str(author_id)]):
                if ticket["channel"] == ctx.channel.id:
                    index = i
                    break

            if index is None:
                await ctx.send(
                    "Hmm... You have multiple tickets open. Type this again in the ticket you want to close."
                )
                return

        if user.id not in guild_settings["created"][str(author_id)][index]["added"]:
            await ctx.send("Member not added.")
            return

        removing_is_admin = await is_admin_or_superior(self.bot, user) or any(
            [ur.id in guild_settings["staffroles"] for ur in user.roles]
        )

        if removing_is_admin:
            await ctx.send("You can't remove Staff, bro.")
            return

        channel = self.bot.get_channel(guild_settings["created"][str(author_id)][index]["channel"])
        if not channel:
            await ctx.send("Ticket deleted.")

        try:
            await channel.set_permissions(user, send_messages=False, read_messages=False)
        except discord.Forbidden:
            await ctx.send(
                "I no longer have permissions to manage channels, so I can't do anything with this ticket."
            )
            return

        async with self.config.guild(ctx.guild).created() as created:
            created[str(author_id)][index]["added"].remove(user.id)

        await ctx.send(f"{user.mention} removed from ticket.")

    @stillsupport.command(name="name")
    async def ticket_name(self, ctx, *, name: str):
        """Rename a ticket"""
        guild_settings = await self.config.guild(ctx.guild).all()
        is_admin = await is_admin_or_superior(self.bot, ctx.author) or any(
            [ur.id in guild_settings["staffroles"] for ur in ctx.author.roles]
        )
        must_be_admin = not guild_settings["membername"]

        if not is_admin and must_be_admin:
            await ctx.send("Only Staff can rename tickets.")
            return
        elif not is_admin:
            author = ctx.author
            author_id = author.id
        elif is_admin:
            # Since the author isn't specified, and it's an admin, we need to guess on who
            # the author is
            inverted = {}
            for author_id, tickets in guild_settings["created"].items():
                for ticket in tickets:
                    inverted[ticket["channel"]] = author_id
            try:
                author = ctx.guild.get_member(int(inverted[ctx.channel.id]))
                if author:
                    author_id = author.id
                else:
                    author_id = int(inverted[ctx.channel.id])
            except KeyError:
                author = ctx.author
                author_id = author.id

        if str(author_id) not in guild_settings["created"]:
            await ctx.send("You don't have any tickets open. <a:pepe_sideeye:894652027387396166>")
            return

        index = None

        if not guild_settings["created"][str(author_id)]:
            await ctx.send("You don't have any tickets open. <a:pepe_sideeye:894652027387396166>")
            return
        elif len(guild_settings["created"][str(author_id)]) == 1:
            index = 0
        else:
            for i, ticket in enumerate(guild_settings["created"][str(author_id)]):
                if ticket["channel"] == ctx.channel.id:
                    index = i
                    break

            if index is None:
                await ctx.send(
                    "Hmm... You have multiple tickets open. Type this again in the ticket you want to close."
                )
                return

        channel = self.bot.get_channel(guild_settings["created"][str(author_id)][index]["channel"])
        if not channel:
            await ctx.send("Ticket deleted.")
            return

        if len(name) > 99:
            await ctx.send("Let's keep that under 100 characters.")
            return

        try:
            await channel.edit(name=name)
        except discord.Forbidden:
            await ctx.send(
                "I no longer have permissions to manage channels, so I can not do anything with this ticket."
            )
            return

        await ctx.send("Renamed ticket.")

    async def lock_ticket(self, ctx, ticket):
        channel = ctx.guild.get_channel(ticket["channel"])
        author = ctx.guild.get_member(ticket["user"])
        added_users = [user for u in ticket["added"] if (user := ctx.guild.get_member(u))]
        added_users.append(author)

        for user in added_users:
            with contextlib.suppress(discord.HTTPException):
                if user:
                    await channel.set_permissions(user, send_messages=False, read_messages=True)

        await channel.send(
            (
                f"This ticket was locked by Staff. Use `{ctx.prefix}stillsupport unlock {channel.mention}` to unlock."
            )
        )

        async with self.config.guild(ctx.guild).created() as created:
            for index, i_ticket in enumerate(created[str(author.id)]):
                if i_ticket["channel"] == ticket["channel"]:
                    created[str(author.id)][index]["locked"] = True
                    break

    async def unlock_ticket(self, ctx, ticket):
        channel = ctx.guild.get_channel(ticket["channel"])
        author = ctx.guild.get_member(ticket["user"])
        added_users = [user for u in ticket["added"] if (user := ctx.guild.get_member(u))]
        added_users.append(author)

        for user in added_users:
            with contextlib.suppress(discord.HTTPException):
                if user:
                    await channel.set_permissions(user, send_messages=True, read_messages=True)

        await channel.send("Ticket unlocked by Staff.")

        async with self.config.guild(ctx.guild).created() as created:
            for index, i_ticket in enumerate(created[str(author.id)]):
                if i_ticket["channel"] == ticket["channel"]:
                    created[str(author.id)][index]["locked"] = False
                    break

    def is_support_or_superior():
        async def predicate(ctx):
            guild_settings = await ctx.bot.get_cog("StillSupport").config.guild(ctx.guild).all()
            is_admin = await is_admin_or_superior(ctx.bot, ctx.author) or any(
                [ur.id in guild_settings["staffroles"] for ur in ctx.author.roles]
            )
            if is_admin:
                return True

            return False

        return commands.check(predicate)

    @is_support_or_superior()
    @stillsupport.command(aliases=["unlock"])
    async def lock(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Lock the current ticket. Mention a ticket to unlock a different one."""
        if channel is None:
            channel = ctx.channel

        created = await self.config.guild(ctx.guild).created()
        selected_ticket = None
        for user_id, user_tickets in created.items():
            for ticket in user_tickets:
                if ticket["channel"] == channel.id:
                    ticket["user"] = int(user_id)
                    selected_ticket = ticket
                    break
            if selected_ticket:
                break

        if not selected_ticket:
            await ctx.send(f"Uhhh I couldn't find ticket no. {channel.mention}.")
            return

        if selected_ticket["locked"]:
            await self.unlock_ticket(ctx, selected_ticket)
        else:
            await self.lock_ticket(ctx, selected_ticket)

        await ctx.tick()

    async def assign_moderator(
        self, guild: discord.Guild, ticket: Dict, moderator: discord.Member
    ):
        channel = guild.get_channel(ticket["channel"])
        author = guild.get_member(ticket["user"])
        if channel:
            await channel.send(
                f"{moderator.mention} has been assigned to this ticket."
            )

        async with self.config.guild(guild).created() as created:
            for index, i_ticket in enumerate(created[str(author.id)]):
                if i_ticket["channel"] == ticket["channel"]:
                    created[str(author.id)][index]["assigned"] = moderator.id
                    break

    @is_support_or_superior()
    @stillsupport.command(aliases=["moderator", "mod", "staff"])
    async def assign(
        self, ctx, moderator: discord.Member, ticket: Optional[discord.TextChannel] = None
    ):
        if not ticket:
            ticket = ctx.channel

        guild_settings = await self.config.guild(ctx.guild).all()

        inverted = {}
        for author_id, tickets in guild_settings["created"].items():
            for uticket in tickets:
                uticket["user"] = int(author_id)
                inverted[uticket["channel"]] = uticket

        try:
            ticket = inverted[ticket.id]
        except KeyError:
            await ctx.send(f"Uhhh I couldn't find ticket no. {ticket.mention}.")
            return

        if not (
            await is_admin_or_superior(self.bot, moderator)
            or any([ur.id in guild_settings["staffroles"] for ur in moderator.roles])
        ):
            await ctx.send(
                "Staff assigned must be an Admin or have a support role."
            )
            return

        if moderator.id == ticket["assigned"]:
            await ctx.send(
                f"{moderator.mention} is already assigned to this ticket. <:look_phone:893502905200549890>",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        if moderator.id == ticket["user"]:
            await ctx.send(
                f"You can not assign {moderator.mention} to their own ticket. They need help too, bro smh.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await self.assign_moderator(ctx.guild, ticket, moderator)
        await ctx.tick()

    def sort_tickets(self, unsorted):
        tickets = []
        for user_id, user_tickets in unsorted.items():
            for ticket in user_tickets:
                ticket["user"] = int(user_id)
                tickets.append(ticket)

        if not tickets:
            raise ValueError

        tickets.sort(key=lambda x: x["opened"], reverse=True)

        complete = []
        index = -1
        counter = 0
        for ticket in tickets:
            if counter % 5 == 0:
                index += 1
                complete.append([])

            complete[index].append(ticket)
            counter += 1

        return complete

    def on_discord_alpha():
        def predicate(ctx):
            return discord.__version__ == "2.0.0a"

        return commands.check(predicate)

    @on_discord_alpha()
    @is_support_or_superior()
    @commands.bot_has_permissions(embed_links=True)
    @stillsupport.command(aliases=["tickets"])
    async def queue(self, ctx):
        """List, modify and close tickets. Sorted by date opened"""
        unsorted_tickets = await self.config.guild(ctx.guild).created()

        try:
            complete = self.sort_tickets(unsorted_tickets)
        except ValueError:
            embed = discord.Embed(
                title="Open tickets",
                description="No open tickets. Yay!",
                color=await ctx.embed_color(),
            )
            await ctx.send(embed=embed)
            return

        queue = Queue(ctx, complete)
        await queue.build_embed()
        message = await ctx.send(embed=queue.embed, view=queue)
        queue.set_message(message)
