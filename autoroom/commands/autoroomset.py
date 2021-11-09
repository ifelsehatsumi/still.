"""The admin room settings command."""
from abc import ABC

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import error, info

from ..abc import CompositeMetaClass, MixinMeta
from ..pcx_lib import SettingDisplay, checkmark


class AutoRoomSetCommands(MixinMeta, ABC, metaclass=CompositeMetaClass):
    """The admin room settings command."""

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def roomset(self, ctx: commands.Context):
        """Configure private rooms"""

    @roomset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        guild_section = SettingDisplay("Guild Settings")
        guild_section.add(
            "Admin private room access",
            await self.config.guild(ctx.guild).admin_access(),
        )
        guild_section.add(
            "Moderator private room access",
            await self.config.guild(ctx.guild).mod_access(),
        )

        autoroom_sections = []
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            for avc_id, avc_settings in avcs.items():
                source_channel = ctx.guild.get_channel(int(avc_id))
                if source_channel:
                    dest_category = ctx.guild.get_channel(
                        avc_settings["dest_category_id"]
                    )
                    autoroom_section = SettingDisplay(
                        f"Private Room - {source_channel.name}"
                    )
                    autoroom_section.add(
                        "Room Access",
                        avc_settings["room_type"].capitalize(),
                    )
                    autoroom_section.add(
                        "Destination category",
                        f"#{dest_category.name}"
                        if dest_category
                        else "INVALID CATEGORY",
                    )
                    if "text_channel" in avc_settings and avc_settings["text_channel"]:
                        autoroom_section.add(
                            "Text Channel",
                            "True",
                        )
                    if "member_roles" in avc_settings:
                        roles = []
                        for member_role_id in avc_settings["member_roles"]:
                            member_role = ctx.guild.get_role(member_role_id)
                            if member_role:
                                roles.append(member_role.name)
                        if roles:
                            autoroom_section.add(
                                "Member Roles" if len(roles) > 1 else "Member Role",
                                ", ".join(roles),
                            )
                    autoroom_section.add(
                        "Room name format",
                        avc_settings["channel_name_type"].capitalize()
                        if "channel_name_type" in avc_settings
                        else "Username",
                    )
                    autoroom_sections.append(autoroom_section)

        await ctx.send(guild_section.display(*autoroom_sections))

    @roomset.group()
    async def access(self, ctx: commands.Context):
        """Control access to all rooms."""

    @access.command()
    async def admin(self, ctx: commands.Context):
        """Allow Admins to join private rooms."""
        admin_access = not await self.config.guild(ctx.guild).admin_access()
        await self.config.guild(ctx.guild).admin_access.set(admin_access)
        await ctx.send(
            checkmark(
                f"Admins are {'now' if admin_access else 'no longer'} able to join private rooms."
            )
        )

    @access.command()
    async def mod(self, ctx: commands.Context):
        """Allow Moderators to join private roms."""
        mod_access = not await self.config.guild(ctx.guild).mod_access()
        await self.config.guild(ctx.guild).mod_access.set(mod_access)
        await ctx.send(
            checkmark(
                f"Moderators are {'now' if mod_access else 'no longer'} able to join private rooms."
            )
        )

    @roomset.group(aliases=["enable", "add"])
    async def create(self, ctx: commands.Context):
        """Create a Room Source.

        Anyone joining a Room Source will automatically have a new
        voice channel (Private Room) created in the destination category 
        and then be moved into it.
        """

    @create.command(name="public")
    async def create_public(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ):
        """Create a Room Source for public rooms.

        These rooms will be public by default. The room owner can
        block specific members from joining their room, or can switch the room to
        private mode to selectively allow members instead.
        """
        await self._create_new_public_private_room(
            ctx, source_voice_channel, dest_category, "public"
        )

    @create.command(name="private")
    async def create_private(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ):
        """Create an Room Source for private rooms.

        The created room will be private by default. The room owner can then allow specific members in or can switch the room to
        public to allow everyone access.
        """
        await self._create_new_public_private_room(
            ctx, source_voice_channel, dest_category, "private"
        )

    async def _create_new_public_private_room(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
        room_type: str,
    ):
        """Save the new room settings."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            vc_id = str(source_voice_channel.id)
            avcs[vc_id] = {}
            avcs[vc_id]["room_type"] = room_type
            avcs[vc_id]["dest_category_id"] = dest_category.id
        await ctx.send(
            checkmark(
                "**{}** is now a Room Source, and will create new {} voice channels in the **{}** category. "
                "Check out `[p]roomset modify` if you'd like to configure this further.".format(
                    source_voice_channel.mention,
                    room_type,
                    dest_category.mention,
                )
            )
        )

    @roomset.command(aliases=["disable", "delete", "del"])
    async def remove(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Remove a Room Source."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                del avcs[str(autoroom_source.id)]
            except KeyError:
                pass
        await ctx.send(
            checkmark(
                f"**{autoroom_source.mention}** is no longer a Room Source channel."
            )
        )

    @roomset.group(aliased=["edit"])
    async def modify(self, ctx: commands.Context):
        """Modify an existing Room Source."""

    @modify.command(name="public")
    async def modify_public(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Set a Room Source to create public Rooms."""
        await self._save_public_private(ctx, autoroom_source, "public")

    @modify.command(name="private")
    async def modify_private(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Set a Room Source to create private Rooms."""
        await self._save_public_private(ctx, autoroom_source, "private")

    async def _save_public_private(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
    ):
        """Save the public/private setting."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                avcs[str(autoroom_source.id)]["room_type"] = room_type
            except KeyError:
                await ctx.send(
                    error(
                        f"**{autoroom_source.mention}** is not a Room Source channel."
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        f"New Private Rooms created by **{autoroom_source.mention}** will be {room_type}."
                    )
                )

    @modify.group()
    async def memberrole(self, ctx: commands.Context):
        """Limit Room visibility to certain roles.

        When set, only users with the specified role(s) can see Private Rooms.
        """

    @memberrole.command(name="add")
    async def add_memberrole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        autoroom_source: discord.VoiceChannel,
    ):
        """Add a role to the list of member roles allowed to see these Private Rooms."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                if "member_roles" not in avcs[str(autoroom_source.id)]:
                    avcs[str(autoroom_source.id)]["member_roles"] = [role.id]
                elif role.id not in avcs[str(autoroom_source.id)]["member_roles"]:
                    avcs[str(autoroom_source.id)]["member_roles"].append(role.id)
            except KeyError:
                await ctx.send(
                    error(
                        f"**{autoroom_source.mention}** is not a Room Source channel."
                    )
                )
                return
        await self._send_memberrole_message(ctx, autoroom_source, "Added!")

    @memberrole.command(name="remove")
    async def remove_memberrole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        autoroom_source: discord.VoiceChannel,
    ):
        """Remove a role from the list of member roles allowed to see these Private Rooms."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                if (
                    "member_roles" in avcs[str(autoroom_source.id)]
                    and role.id in avcs[str(autoroom_source.id)]["member_roles"]
                ):
                    avcs[str(autoroom_source.id)]["member_roles"].remove(role.id)
                    if not avcs[str(autoroom_source.id)]["member_roles"]:
                        del avcs[str(autoroom_source.id)]["member_roles"]
            except KeyError:
                await ctx.send(
                    error(
                        f"**{autoroom_source.mention}** is not a Room Source channel."
                    )
                )
                return
        await self._send_memberrole_message(ctx, autoroom_source, "Removed!")

    async def _send_memberrole_message(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel, action: str
    ):
        """Send a message showing the current member roles."""
        member_roles = await self.get_member_roles_for_source(autoroom_source)
        if member_roles:
            await ctx.send(
                checkmark(
                    f"{action}\n"
                    f"New Private Rooms created by **{autoroom_source.mention}** will be visible by members "
                    "with any of the following roles:\n"
                    f"{', '.join([role.mention for role in member_roles])}"
                )
            )
        else:
            await ctx.send(
                checkmark(
                    f"{action}\n"
                    f"New Private Rooms created by **{autoroom_source.mention}** will be visible by all members."
                )
            )

    @modify.group()
    async def name(self, ctx: commands.Context):
        """Set the default name format of a Private Rooms."""

    @name.command()
    async def username(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Default format: Hatsumi's Room."""
        await self._save_room_name(ctx, autoroom_source, "username")

    @name.command()
    async def game(self, ctx: commands.Context, autoroom_source: discord.VoiceChannel):
        """The name of a game the room owner is currently playing, otherwise the username format."""
        await self._save_room_name(ctx, autoroom_source, "game")

    async def _save_room_name(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
    ):
        """Save the room name type."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                avcs[str(autoroom_source.id)]["channel_name_type"] = room_type
            except KeyError:
                await ctx.send(
                    error(
                        f"**{autoroom_source.mention}** is not a Room Source channel."
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        f"New Private Rooms created by **{autoroom_source.mention}** "
                        f"will use the **{room_type.capitalize()}** format."
                    )
                )

    @modify.command()
    async def text(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Toggle if a text channel should be created as well."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                settings = avcs[str(autoroom_source.id)]
            except KeyError:
                await ctx.send(
                    error(
                        f"**{autoroom_source.mention}** is not a Room Source channel."
                    )
                )
                return
            if "text_channel" in settings and settings["text_channel"]:
                del settings["text_channel"]
            else:
                settings["text_channel"] = True
            await ctx.send(
                checkmark(
                    f"New Private Rooms created by **{autoroom_source.mention}** will "
                    f"{'now' if 'text_channel' in settings else 'no longer'} get their own text channel."
                )
            )

    @modify.command()
    async def perms(
        self,
        ctx: commands.Context,
    ):
        """Learn how to modify default permissions."""
        await ctx.send(
            info(
                "Any permissions set for the `@everyone` role on a Room Source will be copied to the "
                "resulting Private Rooms. The only two permissions that will be overwritten are **View Channel** "
                "and **Connect**, which depend on the Room Sources public/private setting, as well as "
                "any member roles enabled for it.\n\n"
                "Do note that you don't need to set any permissions on the Room Source channel for this "
                "cog to work correctly. This functionality is for the advanced user with a complex server "
                "structure, or for users that want to selectively enable/disable certain functionality "
                "(e.g. video, voice activity/PTT, invites) in Private Rooms."
            )
        )

    @modify.command(aliases=["bitrate", "users"])
    async def other(
        self,
        ctx: commands.Context,
    ):
        """Learn how to modify default bitrate and user limits."""
        await ctx.send(
            info(
                "Default bitrate and user limit settings are now copied from the AutoRoom Source."
            )
        )
