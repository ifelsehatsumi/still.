from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from typing import Union, Optional
import discord
import asyncio
import copy

from stillsupport.extensions.abc import MixinMeta
from stillsupport.extensions.mixin import settings


class StillSupportBaseSettingsMixin(MixinMeta):
    @settings.group(name="opentickets", aliases=["otk"])
    async def pre_creation_settings(self, ctx):
        """Select settings required to open tickets"""
        pass

    @pre_creation_settings.command()
    async def setmsg(self, ctx, message: discord.Message):
        """Set the message that opens tickets upon react"""
        if not message.channel.permissions_for(ctx.guild.me).manage_messages:
            await ctx.send(
                'I must have "Manage Messages" permissions in that channel.'
            )
            return

        msg = f"{message.channel.id}-{message.id}"
        await self.config.guild(ctx.guild).msg.set(msg)
        await ctx.send("Ticket message set.")

    @pre_creation_settings.command()
    async def reaction(self, ctx, emoji: Union[discord.Emoji, str]):
        """Set the reaction emote that opens tickets"""
        if isinstance(emoji, discord.Emoji):
            if emoji.guild_id != ctx.guild.id:
                await ctx.send(
                    "Emote must be from the current server."
                )
                return
            test_emoji = emoji
            emoji = str(emoji.id)
        else:
            emoji = str(emoji).replace("\N{VARIATION SELECTOR-16}", "")
            test_emoji = emoji

        test_message = None
        channel_id, message_id = list(
            map(int, (await self.config.guild(ctx.guild).msg()).split("-"))
        )

        if channel_id == message_id == 0:
            test_message = ctx.message
        else:
            try:
                test_message = await self.bot.get_channel(channel_id).fetch_message(message_id)
            except (AttributeError, discord.NotFound, discord.Forbidden):
                # Channel/message no longer exists or we cannot access it
                await self.config.guild(ctx.guild).msg.set("0-0")
                test_message = ctx.message

        try:
            await test_message.add_reaction(test_emoji)
        except discord.HTTPException:
            await ctx.send("Uhh what emote is that??")
            return
        else:
            await test_message.remove_reaction(test_emoji, member=ctx.guild.me)

        await self.config.guild(ctx.guild).reaction.set(emoji)
        await ctx.send(f"Ticket emote set to {test_emoji}")

    @pre_creation_settings.command()
    async def block(self, ctx, *, user: discord.Member = None):
        """Block or unblock someone from creating tickets."""
        if user:
            async with self.config.guild(ctx.guild).block() as block:
                if user.id in block:
                    block.remove(user.id)
                    await ctx.send(
                        f"{user.display_name} unblocked from support."
                    )
                else:
                    block.append(user.id)
                    await ctx.send(
                        f"{user.display_name} blocked from support."
                    )
        else:
            block = await self.config.guild(ctx.guild).block()
            if not block:
                await ctx.send("No one's been blocked so far.")
                return
            e = discord.Embed(
                title="Members Blocked from Support",
                description="",
                color=await ctx.embed_color(),
            )
            for u in block:
                e.description += f"<@{u}> "
            await ctx.send(embed=e)

    @pre_creation_settings.command()
    async def maxtickets(self, ctx, number: int, send_dm: Optional[bool] = None):
        """Set the maximum number of tickets someone can have open at once. Must be greater than 0.
        Use `true` or `false` after the command to set if a DM letting the member know they have too many tickets."""
        if number < 1:
            await ctx.send("Max must be greater than 0.")
            return

        await self.config.guild(ctx.guild).maxtickets.set(number)
        if send_dm is None:
            await ctx.send("Max number of tickets updated.")
        else:
            await self.config.guild(ctx.guild).maxticketsenddm.set(send_dm)
            await ctx.send(
                "Max number of tickets DM setting updated."
            )

    @settings.group(name="managetickets", aliases=["mngtkt"])
    async def post_creation_settings(self, ctx):
        """Select settings required to manage open tickets"""
        pass

    @post_creation_settings.command(name="greeting", aliases=["openmessage"])
    async def ticket_creation_message(self, ctx, *, message):
        """Set a support greeting sent when a ticket is opened.
        You can use the following member variables:
            {mention}
            {username}
            {id}
        Enter "{default}" to reset."""
        await self.config.guild(ctx.guild).openmessage.set(message)
        if message == "{default}":
            await ctx.send("Greeting reset to default.")
        else:
            await ctx.send("Greeting set.")

    @post_creation_settings.command()
    async def category(self, ctx, category: discord.CategoryChannel):
        """Choose which category to put new tickets"""
        if not category.permissions_for(ctx.guild.me).manage_channels:
            await ctx.send(
                'Oop. I need the "Manage Channels" perm in that category first.'
            )
            return

        await self.config.guild(ctx.guild).category.set(category.id)
        await ctx.send(f"New tickets will be opened under {category.name}.")

    @post_creation_settings.command()
    async def roles(self, ctx, *, role: discord.Role = None):
        """Set the support roles which'll have access to tickets - including archives.
        These roles will have access to tickets automatically."""
        if role:
            async with self.config.guild(ctx.guild).staffroles() as roles:
                if role.id in roles:
                    roles.remove(role.id)
                    await ctx.send(
                        f"{role.name} removed from support."
                    )
                else:
                    roles.append(role.id)
                    await ctx.send(
                        f"{role.name} added to support."
                    )
        else:
            roles = await self.config.guild(ctx.guild).staffroles()
            new = copy.deepcopy(roles)
            if not roles:
                await ctx.send("There are no support roles.")
                return
            e = discord.Embed(
                title="Support Roles",
                description="The Admin is support by default.\n",
                color=await ctx.embed_color(),
            )
            for r in roles:
                ro = ctx.guild.get_role(r)
                if ro:
                    e.description += ro.mention + "\n"
                else:
                    new.remove(r)

            if new != roles:
                await self.config.guild(ctx.guild).staffroles.set(new)
            await ctx.send(embed=e)

    @post_creation_settings.group(name="ticketname")
    async def ticket_names(self, ctx):
        """Set the naming convention for new tickets"""
        pass

    @ticket_names.command(name="list")
    async def ticket_names_list(self, ctx):
        """Show ticket name presets"""
        embed = discord.Embed(
            title="Ticket Name Presets", description="", color=await ctx.embed_color()
        )
        data = await self.config.guild(ctx.guild).presetname()
        presets = data["presets"]
        for index, preset in enumerate(presets):
            embed.description += (
                f"**{index+1} {'(selected)' if index == data['chosen'] else ''}**: `{preset}`\n"
            )

        embed.set_footer(
            text=f"Use {ctx.prefix}stillsupport settings managetickets "
            "ticketname select to change to one of these presets."
        )
        await ctx.send(embed=embed)

    @ticket_names.command(name="add")
    async def ticket_names_add(self, ctx, *, name: str):
        """Add a new ticket name preset.  Availale variables:

        {user} - User name
        {userid} - User ID

        {minute} - Minute integer
        {hour} - Hour integer
        {day_name} - Day name (ex. Monday, Tuesday)
        {day} - Day integer
        {month_name} - Month name (ex. January)
        {month} - Month integer
        {year} - Year integer
        {random} - Random integer between 1 and 10000

        All dates are in UTC time."""
        async with self.config.guild(ctx.guild).presetname() as data:
            data["presets"].append(name)

        msg = await ctx.send("Preset added.  Would you like to use it now?")
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        try:
            await self.bot.wait_for("reaction_add", check=pred, timeout=30.0)
        except asyncio.TimeoutError:
            pred.result = False

        if pred.result is True:
            async with self.config.guild(ctx.guild).presetname() as data:
                data["chosen"] = len(data["presets"]) - 1
            await ctx.send("New name preset enabled.")
        else:
            await ctx.send(
                "No name preset enabled. Use "
                f"`{ctx.prefix}stillsupport settings managetickets "
                f"ticketname select {len(data['presets'])}`."
            )

    @ticket_names.command(name="remove", aliases=["delete"])
    async def ticket_names_remove(self, ctx, index: int):
        """Delete a ticket name preset. You can't delete the currently enabled preset."""
        real_index = index
        settings = await self.config.guild(ctx.guild).presetname()
        if settings["chosen"] == real_index:
            await ctx.send("You can't delete this . . .")
            return

        # I coded this in a shitty way... so we need to check if the one we are
        # removing it before the currently selected
        if real_index < settings["chosen"]:
            settings["chosen"] -= 1

        del settings["presets"][real_index]
        await self.config.guild(ctx.guild).presetname.set(settings)
        await ctx.send("Preset deleted.")

    @ticket_names.command(name="select", alises=["choose"])
    async def ticket_names_select(self, ctx, index: int):
        """Select a ticket name preset to use.

        Use `[p]stillsupport settings managetickets ticketnames list` to view available presets."""
        real_index = index - 1
        settings = await self.config.guild(ctx.guild).presetname()
        if settings["chosen"] == real_index:
            await ctx.send("Umm... you're already using that preset.")
            return

        if index > len(settings["presets"]):
            await ctx.send(
                f"I- *sigh* ...use `{ctx.prefix}stillsupport settings managetickets ticketnames list` to view available presets."
            )
            return

        settings["chosen"] = real_index
        await self.config.guild(ctx.guild).presetname.set(settings)
        await ctx.send("New preset enabled.")

    @settings.command()
    async def enable(self, ctx, yes_or_no: Optional[bool] = None):
        """Enable still.support tickets."""
        # We'll run through a test of all the settings to ensure everything is set properly

        # Before we get started to it, we'll check if the bot has Administrator permissions
        # NOTE for anyone reading: Do not make your cogs require Admin!  The only reason this is
        # happening is because Discord decided to lock MANAGE_PERMISSIONS behind Admin
        # (which is bullshit), therefore, I have to require it.  I would really rather not.
        if not ctx.channel.permissions_for(ctx.guild.me).administrator:
            await ctx.send(
                "I must have the Administrator permission to enable still.support. "
                "this would not be required, however Discord has "
                "changed channel overwrites, and MANAGE_PERMISSIONS access requires Administrator."
            )
            return

        # 1 - Ticket message is accessible and we can do what is needed with it
        channel_id, message_id = list(
            map(int, (await self.config.guild(ctx.guild).msg()).split("-"))
        )
        if channel_id == message_id == 0:
            await ctx.send(
                "No ticket greeting set. Set it with "
                f"`{ctx.prefix}stillsupport settings opentickets setmsg`."
            )
            return

        try:
            message = await self.bot.get_channel(channel_id).fetch_message(message_id)
        except AttributeError:
            # Channel no longer exists
            await self.config.guild(ctx.guild).msg.set("0-0")
            await ctx.send(
                "No ticket message set for opening tickets. Set it with "
                f"`{ctx.prefix}stillsupport settings opentickets setmsg`."
                "\nReason: Previously set channel deleted"
            )
            return
        except discord.NotFound:
            # Message no longer exists
            await self.config.guild(ctx.guild).msg.set("0-0")
            await ctx.send(
                "No ticket message set for opening tickets. Set it with "
                f"`{ctx.prefix}stillsupport settings opentickets setmsg`."
                "\nReason: Previously set message deleted"
            )
            return
        except discord.Forbidden:
            # We don't have permission to read that message
            await ctx.send(
                "Ticket channel permissions incorrect. Allow the following: "
                "`Read Messages`, `Add Reactions`, `Manage Messages`."
            )
            return

        # 2 - Check reaction is set properly
        emoji = await self.config.guild(ctx.guild).reaction()
        if emoji.isdigit():
            emoji = self.bot.get_emoji(int(emoji))
            if not emoji:
                await self.config.guild(ctx.guild).reaction.set("\N{ADMISSION TICKETS}")
                await ctx.send(
                    "Open ticket emote missing. Set a new one or "
                    "rerun this command to go with the default."
                )
                return

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await ctx.send(
                "Couldn't set the open ticket emote.  "
                "Make sure the emote exists, and I have the `Add Reactions` perm?"
            )
            return

        # 3 - Category check
        category_id = await self.config.guild(ctx.guild).category()
        if not category_id:
            await ctx.send(
                "No ticket category set to place open tickets. Set it with "
                f"`{ctx.prefix}stillsupport settings managetickets category`."
            )
            return

        category = self.bot.get_channel(category_id)
        if not category:
            await ctx.send(
                "No ticket category set to place open tickets. Set it with "
                f"`{ctx.prefix}stillsupport settings managetickets category`.\n"
                "Reason: Previous category deleted."
            )
            return

        # 4 - Archive check (if enabled)
        archive = await self.config.guild(ctx.guild).archive()
        if archive["enabled"]:
            if not archive["category"]:
                await ctx.send(
                    "Archive enabled, but no archive category is set. Set one with "
                    f"`{ctx.prefix}stillsupport settings closesettings archive category`."
                )
                return

            archive_category = self.bot.get_channel(archive["category"])
            if not archive_category:
                await ctx.send(
                    "Archive enabled, but archive category was deleted. Set a new one with "
                    f"`{ctx.prefix}stillsupport settings closesettings archive category`."
                )
                return

        # 5 - Reporting channel (also if enabled)
        report = await self.config.guild(ctx.guild).report()
        if report != 0:
            report_channel = self.bot.get_channel(report)
            if not report_channel:
                await ctx.send(
                    "Reporting enabled, but report channel has been deleted. Please reset it with "
                    f"`{ctx.prefix}stillsupport settings closesettings reports`."
                )

            if not report_channel.permissions_for(ctx.guild.me).send_messages:
                await ctx.send(
                    "Reporting is enabled but I can't post in the report channel.  "
                    "Make sure I have `View Channels`, `Read Message History` and `Send Messages` perms."
                )
                return

        # Checks passed, let's cleanup a little bit and then enable
        await message.clear_reactions()
        await message.add_reaction(emoji)
        await self.config.guild(ctx.guild).enabled.set(True)

        await ctx.send("All checks passed.  still.support is now enabled.")

    @settings.command()
    async def disable(self, ctx):
        """Disable ticketing system"""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("still.support disabled.")
