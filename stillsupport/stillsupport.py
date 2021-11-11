from redbot.core.bot import Red
from redbot.core import commands, Config
from typing import Optional
import datetime
import contextlib
import discord
import random
import asyncio
import time

from abc import ABC

# ABC Mixins
from stillsupport.extensions.mixin import RTMixin
from stillsupport.extensions.base import StillSupportBaseMixin
from stillsupport.extensions.basesettings import StillSupportBaseSettingsMixin
from stillsupport.extensions.closeticketsimport StillSupportCloseSettingsMixin
from stillsupport.extensions.usersettings import StillSupportUserSettingsMixin


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's
    metaclass."""


class StillSupport(
    StillSupportBaseMixin,
    StillSupportBaseSettingsMixin,
    StillSupportCloseSettingsMixin,
    StillSupportUserSettingsMixin,
    RTMixin,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    def __init__(self, bot: Red):
        self.bot: Red = bot

        default_guild = {
            # Initial ticket creation settings
            "reaction": "\N{ADMISSION TICKETS}",
            "msg": "0-0",
            "openmessage": "{default}",
            "maxtickets": 1,
            "maxticketsenddm": False,
            # Permission settings
            "memberclose": False,
            "memberedit": False,
            "membername": False,
            # Post creation settings
            "category": 0,
            "archive": {"category": 0, "enabled": False},
            "dm": False,
            "presetname": {"selected": 0, "presets": ["ticket-{userid}"]},
            "closeonleave": False,
            "closeafter": 0,
            "exemptlist": [],
            # Miscellaneous
            "staffroles": [],
            "block": [],
            "report": 0,
            "enabled": False,
            "created": {},
        }

        self.config: Config = Config.get_conf(
            self, identifier=473541068378341107, force_registration=True
        )
        self.config.register_guild(**default_guild)
        self.config.register_global(
            first_migration=False,
            second_migration=False,
            third_migration=False,
            fourth_migration=False,
        )
        self.bot.loop.create_task(self.possibly_migrate())

    async def possibly_migrate(self):
        await self.bot.wait_until_red_ready()

        has_migrated: bool = await self.config.first_migration()
        if not has_migrated:
            await self.migrate_first()

        has_second_migrated: bool = await self.config.second_migration()
        if not has_second_migrated:
            await self.migrate_second()

        has_third_migrated: bool = await self.config.third_migration()
        if not has_third_migrated:
            await self.migrate_third()

        has_fourth_migrated: bool = await self.config.fourth_migration()
        if not has_fourth_migrated:
            await self.migrate_fourth()

    async def migrate_first(self):
        guilds = self.config._get_base_group(self.config.GUILD)
        async with guilds.all() as data:
            for guild_id, guild_data in data.items():
                saving = {}
                try:
                    for user_id, ticket in guild_data["created"].items():
                        saving[user_id] = {"channel": ticket, "added": []}
                except KeyError:
                    continue

                data[guild_id]["created"] = saving
        await self.config.first_migration.set(True)

    async def migrate_second(self):
        guilds = self.config._get_base_group(self.config.GUILD)
        async with guilds.all() as data:
            for guild_id, guild_data in data.items():
                saving = {}
                try:
                    for user_id, ticket in guild_data["created"].items():
                        saving[user_id] = [ticket]
                except KeyError:
                    continue

                data[guild_id]["created"] = saving

        await self.config.second_migration.set(True)

    async def migrate_third(self):
        guilds = self.config._get_base_group(self.config.GUILD)
        async with guilds.all() as data:
            for guild_id, guild_data in data.items():
                saving = {}
                try:
                    for user_id, tickets in guild_data["created"].items():
                        saving[user_id] = tickets
                        for index, ticket in enumerate(tickets):
                            ticket["assigned"] = 0
                            saving[user_id][index] = ticket
                except KeyError:
                    continue

                data[guild_id]["created"] = saving

        await self.config.third_migration.set(True)

    async def migrate_fourth(self):
        guilds = self.config._get_base_group(self.config.GUILD)
        async with guilds.all() as data:
            for guild_id, guild_data in data.items():
                saving = {}
                try:
                    for user_id, tickets in guild_data["created"].items():
                        saving[user_id] = tickets
                        for index, ticket in enumerate(tickets):
                            ticket["locked"] = False
                            saving[user_id][index] = ticket
                except KeyError:
                    continue

                data[guild_id]["created"] = saving

        await self.config.fourth_migration.set(True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild_settings = await self.config.guild(member.guild).all()

        if not guild_settings["closeonleave"]:
            return

        if (
            not str(member.id) in guild_settings["created"]
            or len(guild_settings["created"][str(member.id)]) == 0
        ):
            return

        archive = self.bot.get_channel(guild_settings["archive"]["category"])
        post_processing = {}  # Mapping of Dict[discord.TextChannel: List[discord.Member]]

        for ticket in guild_settings["created"][str(member.id)]:
            channel: Optional[discord.TextChannel] = self.bot.get_channel(ticket["channel"])
            added_users = [user for u in ticket["added"] if (user := member.guild.get_member(u))]
            guild = self.bot.get_guild(payload.guild_id)
            if guild_settings["report"] != 0:
                reporting_channel: Optional[discord.TextChannel] = self.bot.get_channel(
                    guild_settings["report"]
                )
                if reporting_channel:
                    if await self.embed_requested(reporting_channel):
                        embed = discord.Embed(
                            title="Ticket Closed",
                            description=(
                                f"Ticket {channel.mention} opened by "
                                f"{member.mention} "
                                f"closed. {user.display_name} is no longer a member of {guild.name}."
                            ),
                            color=await self.bot.get_embed_color(reporting_channel),
                        )
                        if ticket["assigned"]:
                            moderator = getattr(
                                member.guild.get_member(
                                    ticket["assigned"], "mention", "Unknown Staff Member"
                                )
                            )
                            embed.add_field(
                                name="Staff Assigned", value=moderator,
                            )
                        await reporting_channel.send(embed=embed)
                    else:
                        message = (
                            f"Ticket {channel.mention} opened by "
                            f"{str(member)} "
                            f"closed. {user.display_name} is no longer member of {guild.name}."
                        )
                        if ticket["assigned"]:
                            moderator = getattr(
                                member.guild.get_member(
                                    ticket["assigned"], "mention", "Unknown Staff Member"
                                )
                            )
                            message += f"\nAssigned To: {moderator}"
                        await reporting_channel.send(
                            message, allowed_mentions=discord.AllowedMentions.none()
                        )
            if guild_settings["archive"]["enabled"] and channel and archive:
                for user in added_users:
                    with contextlib.suppress(discord.HTTPException):
                        if user:
                            await channel.set_permissions(
                                user, send_messages=False, read_messages=True
                            )
                await channel.send(
                    f"Ticket {channel.mention} for {member.display_name} closed. Ticket owner is no longer a member of {guild.name}. "
                    "Archiving ticket in one minute . . ."
                )

                post_processing[channel] = added_users
            else:
                if channel:
                    for user in added_users:
                        with contextlib.suppress(discord.HTTPException):
                            if user:
                                await channel.set_permissions(
                                    user, send_messages=False, read_messages=True
                                )
                await channel.send(
                    f"Ticket {channel.mention} for {member.display_name} closed. Ticket owner is no longer a member of {guild.name}. "
                    "Deleting ticket in one minute — if open . . ."
                )
            async with self.config.guild(member.guild).created() as tickets:
                if str(member.id) in tickets:
                    del tickets[str(member.id)]

        await asyncio.sleep(60)

        for channel, added_users in post_processing.items():
            if guild_settings["archive"]["enabled"] and channel and archive:
                try:
                    admin_roles = [
                        member.guild.get_role(role_id)
                        for role_id in (await self.bot._config.guild(member.guild).admin_role())
                        if member.guild.get_role(role_id)
                    ]
                    support_roles = [
                        member.guild.get_role(role_id)
                        for role_id in guild_settings["staffroles"]
                        if member.guild.get_role(role_id)
                    ]

                    all_roles = admin_roles + support_roles
                    overwrites = {
                        member.guild.default_role: discord.PermissionOverwrite(
                            read_messages=False
                        ),
                        member.guild.me: discord.PermissionOverwrite(
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
                    await channel.send(f"Couldn't archive ticket. {str(e)}")
            else:
                if channel:
                    try:
                        await channel.delete()
                    except discord.HTTPException:
                        with contextlib.suppress(discord.HTTPException):
                            await channel.send(
                                'Could not delete ticket. Check that I have "Manage Channels" '
                                "perms in the category."
                            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        if not payload.guild_id:
            return

        guild_settings = await self.config.guild_from_id(payload.guild_id).all()
        if not guild_settings["enabled"]:
            return

        if guild_settings["msg"] == "0-0":
            await self.config.guild_from_id(payload.guild_id).enabled.set(False)
            return

        if guild_settings["msg"] != f"{payload.channel_id}-{payload.message_id}":
            return

        if (guild_settings["reaction"].isdigit() and payload.emoji.is_unicode_emoji()) or (
            not guild_settings["reaction"].isdigit() and payload.emoji.is_custom_emoji()
        ):
            return

        if payload.emoji.is_custom_emoji():
            if payload.emoji.id != int(guild_settings["reaction"]):
                return
        else:
            if str(payload.emoji) != guild_settings["reaction"]:
                return

        category = self.bot.get_channel(guild_settings["category"])
        if not category:
            await self.config.guild_from_id(payload.guild_id).enabled.set(False)
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not category.permissions_for(guild.me).administrator:
            await self.config.guild_from_id(payload.guild_id).enabled.set(False)
            return

        if payload.user_id in guild_settings["block"]:
            return

        user = guild.get_member(payload.user_id)

        if (
            len(guild_settings["created"].get(str(payload.user_id), []))
            >= guild_settings["maxtickets"]
        ):
            if guild_settings["maxticketsenddm"]:
                try:
                    await user.send(
                        f"Sorry, you can't open any more tickets in {guild.name}. Please allow staff to resolve your current ones first. If you need more help, please use one of your existing tickets."
                    )
                except discord.HTTPException:
                    pass

            with contextlib.suppress(discord.HTTPException):
                message = await self.bot.get_channel(payload.channel_id).fetch_message(
                    payload.message_id
                )
                await message.remove_reaction(payload.emoji, member=user)
            return

        admin_roles = [
            guild.get_role(role_id)
            for role_id in (await self.bot._config.guild(guild).admin_role())
            if guild.get_role(role_id)
        ]
        support_roles = [
            guild.get_role(role_id)
            for role_id in (await self.config.guild(guild).staffroles())
            if guild.get_role(role_id)
        ]

        all_roles = admin_roles + support_roles

        can_read = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        can_read_and_manage = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True
        )  # Since Discord can't make up their mind about manage channels/manage permissions

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: can_read_and_manage,
            user: can_read,
        }
        for role in all_roles:
            overwrites[role] = can_read

        now = datetime.datetime.now(datetime.timezone.utc)

        channel_name = (
            guild_settings["presetname"]["presets"][guild_settings["presetname"]["selected"]]
            .replace("{user}", user.display_name)
            .replace("{userid}", str(user.id))
            .replace("{minute}", str(now.minute))
            .replace("{hour}", str(now.hour))
            .replace("{day_name}", now.strftime("%A"))
            .replace("{day}", str(now.day))
            .replace("{month_name}", now.strftime("%B"))
            .replace("{month}", str(now.month))
            .replace("{year}", str(now.year))
            .replace("{random}", str(random.randint(100000, 999999)))
        )[:100]

        created_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
        if guild_settings["openmessage"] == "{default}":
            if guild_settings["memberclose"]:
                sent = await created_channel.send(
                    f"Ticket opened for {user.display_name}.\nTo close it, type `[p]stillsupport close`."
                )
            else:
                sent = await created_channel.send(
                    f"Ticket opened for {user.display_name}.\n"
                    "Staff: To close this ticket, type `[p]stillsupport close`."
                )
        else:
            try:
                message = (
                    guild_settings["openmessage"]
                    .replace("{mention}", user.mention)
                    .replace("{username}", user.display_name)
                    .replace("{id}", str(user.id))
                )
                sent = await created_channel.send(
                    message, allowed_mentions=discord.AllowedMentions(users=True, roles=True)
                )
            except Exception as e:
                # Something went wrong, let's go to default for now
                print(e)
                if guild_settings["memberclose"]:
                    sent = await created_channel.send(
                        f"Ticket opened for {user.display_name}\nTo close it, type `[p]stillsupport close`."
                    )
                else:
                    sent = await created_channel.send(
                        f"Ticket opened for {user.display_name}\n"
                        "Staff: To close this ticket, type `[p]stillsupport close`."
                    )

        # To prevent race conditions...
        async with self.config.guild(guild).created() as created:
            if str(payload.user_id) not in created:
                created[str(payload.user_id)] = []
            created[str(payload.user_id)].append(
                {
                    "channel": created_channel.id,
                    "added": [],
                    "opened": time.time(),
                    "assigned": 0,
                    "locked": False,
                }
            )

        # If removing the reaction fails... eh
        with contextlib.suppress(discord.HTTPException):
            message = await self.bot.get_channel(payload.channel_id).fetch_message(
                payload.message_id
            )
            await message.remove_reaction(payload.emoji, member=user)

        if guild_settings["report"] != 0:
            reporting_channel = self.bot.get_channel(guild_settings["report"])
            if reporting_channel:
                if await self.embed_requested(reporting_channel):
                    embed = discord.Embed(
                        title="Ticket Opened",
                        description=(
                            f"A new ticket has been opened by {user.mention}.\n"
                            f"Click [here]({sent.jump_url}) to view it."
                        ),
                    )
                    description = ""
                    if guild_settings["memberclose"]:
                        description += "Members can close their own tickets.\n"
                    else:
                        description += "Members can not close their own tickets.\n"

                    if guild_settings["memberedit"]:
                        description += (
                            "Members can add/remove others to/from their tickets.\n"
                        )
                    else:
                        description += (
                            "Members can not add/remove others to/from their tickets.\n"
                        )
                    embed.add_field(name="User Permission", value=description)
                    await reporting_channel.send(embed=embed)
                else:
                    message = (
                        f"A new ticket has been opened by {str(user)}.\n"
                        f"Click [here]({sent.jump_url}) to view it.\n"
                    )

                    if guild_settings["memberclose"] and guild_settings["memberedit"]:
                        message += (
                            "Members can close their own tickets "
                            "and add/remove users to/from them."
                        )
                    elif guild_settings["memberclose"]:
                        message += (
                            "Members can close their own tickets, "
                            "but cannot add/remove users to/from them."
                        )
                    elif guild_settings["memberedit"]:
                        message += (
                            "Members can add/remove others to/from their tickets, "
                            "but can not close them."
                        )
                    else:
                        message += "Members cannot close their own tickets or add/remove others to/from them."

                    await reporting_channel.send(message)
