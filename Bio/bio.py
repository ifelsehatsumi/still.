# -*- coding: utf-8 -*-
import asyncio
import logging
import re
from collections import namedtuple
from typing import Optional, Union

import discord
from redbot.core import checks, Config, commands, bot

log = logging.getLogger("red.cbd-cogs.bio")

__all__ = ["UNIQUE_ID", "Bio"]

UNIQUE_ID = 0x62696F68617A61723060


class Bio(commands.Cog):
    """Add information to your player bio and lookup information others have shared.
    
    See `[p]help bio` for details."""
    def __init__(self, bot: bot.Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_user(bio={})
        self.conf.register_guild(biofields=[])

    @commands.group(autohelp=False)
    @commands.guild_only()
    async def biofields(self, ctx: commands.Context):
        """List the available bio fields
        
        Users will only be able to set a field in their bio if it has been added to this list"""
        if ctx.invoked_subcommand is not None:
            return
        bioFields = await self.conf.guild(ctx.guild).biofields()
        if len(bioFields):
            await ctx.send("Bio fields available:\n"
                            "\n".join(bioFields))
        else:
            await ctx.send("No bio fields available. Alert an admin!")

    @biofields.command(name="add")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def add_field(self, ctx: commands.Context, *, argField: str):
        """Add fields to the list available for adding to bios"""
        bioFields = await self.conf.guild(ctx.guild).biofields()
        for field in bioFields:
            if field.lower() == argField.lower():
                await ctx.send(f"Field '{field}' already exists!")
                return
        bioFields.append(argField)
        await self.conf.guild(ctx.guild).biofields.set(bioFields)
        await ctx.send(f"Field '{argField}' has been added")

    @biofields.command(name="remove")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove_field(self, ctx:commands.Context, *args):
        """Remove fields from bios and make them unavailable (DANGER!)
        
        USE WITH CAUTION: There is no way to restore deleted fields!"""
        bioFields = await self.conf.guild(ctx.guild).biofields()
        argField = " ".join(args)
        try:
            bioFields.remove(argField)
        except KeyError:
            for field in bioFields:
                if field.lower() == argField.lower():
                    bioFields.remove(field)
                    break
            else:
                await ctx.send(f"No field named '{argField}'")
                return
        await self.conf.guild(ctx.guild).biofields.set(bioFields)
        count = 0
        for member, conf in (await self.conf.all_users()).items():
            memberBio = conf.get("bio")
            if argField in memberBio.keys():
                del memberBio[argField]
                await self.conf.user(self.bot.get_user(member)).bio.set(memberBio)
                count += 1
        await ctx.send(f"Removed field '{argField}' from {count} bios")

    @commands.command()
    @commands.guild_only()
    async def bio(self, ctx: commands.Context, userOrField: Optional[str] = None, *fields):
        """Display and modify your bio or view someone else's bio
        
        Examples:
        Display your own bio
        `[p]bio`
        
        Display your friend's bio
        `[p]bio @friend`
        
        Display the 'foo' and 'bar' fields on your friend's bio
        `[p]bio @friend foo bar`
        
        Note that fields with spaces in the name must be in quotes
        `[p]bio @friend 'Three Word Field'`
        
        Set the 'foo' field on your bio to 'bar'
        `[p]bio foo bar`
        
        Remove the 'foo' field from your bio
        `[p]bio foo`
        
        Other commands to look into:
        `[p]help biofields`
        `[p]help biosearch`
        `[p]help bioreset`
        """
        await self._bio(ctx, userOrField, *fields)

    async def _bio(self, ctx: commands.Context, user: Optional[str] = None, *args):
        bioFields = await self.conf.guild(ctx.guild).biofields()
        server = ctx.message.guild.name
        key = None
        if re.search(r'<@!\d+>', str(user)):
            user = ctx.guild.get_member(int(user[3:-1]))
            if not user:
                await ctx.send("Unknown user")
                return
        if not isinstance(user, discord.abc.User):
            # Argument is a key to set, not a user
            key = user
            user = ctx.author
        bioDict = await self.conf.user(user).bio()

        # User is setting own bio
        warnings = []
        if key is not None and user is ctx.author:
            if key not in bioFields:
                keySwap = False
                for field in bioFields:
                    if key.lower() == field.lower():
                        key = field
                        break
                else:
                    await ctx.send("Sorry, that bio field is not available.\n"
                                   "Please request it from the server owner.")
                    return
            if args:
                bioDict[key] = " ".join(args)
                await self.conf.user(user).bio.set(bioDict)
                await ctx.send(f"Field '{key}' set to {bioDict[key]}")
            else:
                try:
                    del bioDict[key]
                except KeyError:
                    await ctx.send(f"Field '{key}' not found in your bio")
                    return
                await self.conf.user(user).bio.set(bioDict)
                await ctx.send(f"Field '{key}' removed from your bio")
            return

        # Filter dict to key(s)
        elif user and len(args):
            data = {}
            for arg in args:
                try:
                    data[arg] = bioDict[arg]
                except KeyError:
                    for field in bioFields:
                        if arg.lower() == field.lower() and field in bioDict.keys():
                            data[field] = bioDict[field]
                            break
                    else:
                        warnings.append(f"Field '{arg}' not found")
            bioDict = data
        embed = discord.Embed()
        embed.title = f"{user.display_name}"
        embed.description = server
        embed.set_thumbnail(url=user.avatar_url)
        embed.set_footer(text="\n".join(warnings))
        for field, value in bioDict.items():
            if field != 'Vibe':
                embed.add_field(name=field, value=value, inline=True)
            if field == 'Vibe':
                if value != "":
                    pic = value                
                    embed.add_field(name=field, value="", inline=False)
                else:
                    pic = user.avatar_url
                embed.set_image(url=pic)
        embed.colour = ctx.author.colour
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def biosearch(self, ctx: commands.Context, *args):
        """Find field values across all users
        
        Examples:
        Search for a single field 'foo'
        `[p]biosearch foo`
        
        Search for multiple fields 'foo', 'bar', and 'long name field'
        `[p]biosearch foo bar 'long name field'`
        """
        argsLower = [x.lower() for x in args]
        embed = discord.Embed()
        embed.title = "Bio Search"
        for member, conf in (await self.conf.all_users()).items():
            memberBio = conf.get("bio")
            if len(args) > 1:
                values = [f"{x}: {y}" for x,y in memberBio.items() if x.lower() in argsLower]
            else:
                values = [y for x,y in memberBio.items() if x.lower() in argsLower]
            if len(values):
                try:
                    memberName = ctx.guild.get_member(int(member)).display_name
                except:
                    continue
                embed.add_field(name=memberName,
                                value="\n".join(values),
                                inline=False)
        await ctx.send(embed=embed)
