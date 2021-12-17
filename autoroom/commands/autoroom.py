"""The Private Room command."""
import datetime
from abc import ABC
from typing import Union

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import error, humanize_timedelta

from ..abc import CompositeMetaClass, MixinMeta
from ..pcx_lib import SettingDisplay, delete


class AutoRoomCommands(MixinMeta, ABC, metaclass=CompositeMetaClass):
    """The Private Room Command"""

    @commands.group()
    @commands.guild_only()
    async def room(self, ctx: commands.Context):
        """Organize Your Room."""

    @room.command(name="settings", aliases=["info"])
    async def room_settings(self, ctx: commands.Context):
        """Display current settings."""
        member_channel = self._get_current_voice_channel(ctx.message.author)
        autoroom_info = await self._get_autoroom_info(member_channel)
        if not autoroom_info:
            hint = await ctx.send(
                error(f"{ctx.message.author.mention}, you are not in a room.")
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return

        room_settings = SettingDisplay("Room Settings")
        room_settings.add(
            "Owner",
            autoroom_info["owner"].display_name if autoroom_info["owner"] else "???",
        )

        mode = "???"
        for member_role in autoroom_info["member_roles"]:
            if member_role in member_channel.overwrites:
                mode = (
                    "Public"
                    if member_channel.overwrites[member_role].connect
                    else "Private"
                )
                break
        room_settings.add("Mode", mode)

        room_settings.add("Bitrate", f"{member_channel.bitrate // 1000}kbps")
        room_settings.add(
            "Channel Age",
            humanize_timedelta(
                timedelta=datetime.datetime.utcnow() - member_channel.created_at
            ),
        )

        await ctx.send(room_settings)

    @room.command()
    async def unlock(self, ctx: commands.Context):
        """The more the merrier! Unlock your room so others can enter!"""
        await self._process_allow_deny(ctx, True)

    @room.command()
    async def lock(self, ctx: commands.Context):
        """Lock your door, dude. No one can get in that's not already."""
        await self._process_allow_deny(ctx, False)

    @room.command(aliases=["add"])
    async def openfor(
        self, ctx: commands.Context, member_or_role: Union[discord.Role, discord.Member]
    ):
        """Open the door for a specific friend to allow them in!"""
        await self._process_allow_deny(ctx, True, member_or_role=member_or_role)

    @room.command(aliases=["ban"])
    async def lockout(
        self, ctx: commands.Context, member_or_role: Union[discord.Role, discord.Member]
    ):
        """Lock only a specific person out of your room. Sucks to suck.

        If someone can no longer enter your room due to locking out a role,
        they will be disconnected. Keep in mind that if the guild is using
        member roles, denying roles will probably not work as expected.
        """
        if await self._process_allow_deny(ctx, False, member_or_role=member_or_role):
            channel = self._get_current_voice_channel(ctx.message.author)
            if not channel or not ctx.guild.me.permissions_in(channel).move_members:
                return
            for member in channel.members:
                if not member.permissions_in(channel).connect:
                    await member.move_to(None, reason="AutoRoom: Deny user")

    async def _process_allow_deny(
        self,
        ctx: commands.Context,
        allow: bool,
        *,
        member_or_role: Union[discord.Role, discord.Member] = None,
    ) -> bool:
        """Unlock or lock your room."""
        channel = self._get_current_voice_channel(ctx.message.author)
        autoroom_info = await self._get_autoroom_info(channel)
        if not autoroom_info:
            hint = await ctx.send(
                error(f"{ctx.message.author.mention}, you are not in a room.")
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return False
        if ctx.message.author != autoroom_info["owner"]:
            hint = await ctx.send(
                error(
                    f"{ctx.message.author.mention}, this isn't your room lol wtf."
                )
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return False

        denied_message = ""
        if not member_or_role:
            # public/private command
            member_or_role = autoroom_info["member_roles"]
        elif (
            allow
            and member_or_role == ctx.guild.default_role
            and [member_or_role] != autoroom_info["member_roles"]
        ):
            denied_message = "this room is using roles, so the default role must remain denied."
        elif member_or_role in autoroom_info["member_roles"]:
            # allow/deny a member role -> modify all member roles
            member_or_role = autoroom_info["member_roles"]
        elif not allow:
            if member_or_role == ctx.guild.me:
                denied_message = "lol nice try. I can enter anytime I want jerk."
            elif member_or_role == ctx.message.author:
                denied_message = "bruh. imagine trying to lock yourself out of your room."
            elif member_or_role == ctx.guild.owner:
                denied_message = (
                    "I don't know if you know this, but that's the server owner... "
                    "I can't deny them from entering your room."
                )
            elif await self.is_admin_or_admin_role(member_or_role):
                denied_message = "Whoa you're trying to lock an admin{} out of your room. I'm soo telling.".format(
                    " role" if isinstance(member_or_role, discord.Role) else ""
                )
            elif await self.is_mod_or_mod_role(member_or_role):
                denied_message = "Whoa you're trying to lock a moderator{} out of your room. I'm soo telling.".format(
                    " role" if isinstance(member_or_role, discord.Role) else ""
                )
        if denied_message:
            hint = await ctx.send(
                error(f"{ctx.message.author.mention}, {denied_message}")
            )
            await delete(ctx.message, delay=10)
            await delete(hint, delay=10)
            return False

        overwrites = dict(channel.overwrites)
        do_edit = False
        if not isinstance(member_or_role, list):
            member_or_role = [member_or_role]
        for target in member_or_role:
            if target in overwrites:
                if overwrites[target].view_channel != allow:
                    overwrites[target].update(view_channel=allow)
                    do_edit = True
                if overwrites[target].connect != allow:
                    overwrites[target].update(connect=allow)
                    do_edit = True
            else:
                overwrites[target] = discord.PermissionOverwrite(
                    connect=allow
                )
                overwrites[target] = discord.PermissionOverwrite(
                    view_channel=True
                )
                #overwrites[target].update(view_channel=allow)
                do_edit = True
        if do_edit:
            await channel.edit(
                overwrites=overwrites,
                reason="Room: Permission change",
            )
        await ctx.tick()
        await delete(ctx.message, delay=5)
        return True

    @staticmethod
    def _get_current_voice_channel(member: discord.Member):
        """Get the members current voice channel, or None if not in a voice channel."""
        if member.voice:
            return member.voice.channel
        return None

    async def _get_autoroom_info(self, autoroom: discord.VoiceChannel):
        """Get info for an room, or None if the voice channel isn't a room."""
        if not autoroom:
            return None
        owner_id = await self.config.channel(autoroom).owner()
        if not owner_id:
            return None
        owner = autoroom.guild.get_member(owner_id)
        member_roles = []
        for member_role_id in await self.config.channel(autoroom).member_roles():
            member_role = autoroom.guild.get_role(member_role_id)
            if member_role:
                member_roles.append(member_role)
        if not member_roles:
            member_roles = [autoroom.guild.default_role]
        return {
            "owner": owner,
            "member_roles": member_roles,
        }
