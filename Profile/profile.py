# -*- coding: utf-8 -*-
import asyncio
import logging
import re
from collections import namedtuple
from typing import Optional, Union

import discord
from redbot.core import checks, Config, commands, bot

log = logging.getLogger("red.cbd-cogs.profile")

__all__ = ["UNIQUE_ID", "Profile"]

UNIQUE_ID = 0x62696F68617A61723060


class Profile(commands.Cog):
    """Create and view member profiles.
    
    Use `[p]help profile` for details."""
    def __init__(self, bot: bot.Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_user(profile={})
        self.conf.register_guild(profileoptions=[])

    @commands.group(autohelp=False)
    @commands.guild_only()
    async def profileoptions(self, ctx: commands.Context):
        """See available profile options."""
        if ctx.invoked_subcommand is not None:
            return
        profileOptions = await self.conf.guild(ctx.guild).profileoptions()
        if len(profileOptions):
            embed = discord.Embed()
            embed.title = f"Available Profile Options"
            embed.description = "\n".join(profileOptions)
            embed.colour = 0xfafafa
            embed.set_footer(text="Type `k,profile option text` to add an option to your profile.")
            await ctx.send(embed=embed)
            #await ctx.send("\n".join(profileOptions))
        else:
            await ctx.send("Oop. Not there being ZERO options set up... <a:pepe_bite_lip:804628368305029151>")

    @profileoptions.command(name="add")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def add_option(self, ctx: commands.Context, *, argOption: str):
        """Add a profile option members can set."""
        profileOptions = await self.conf.guild(ctx.guild).profileoptions()
        for option in profileOptions:
            if option.lower() == argOption.lower():
                await ctx.send(f"Dude. '{option}' already exists. -_-")
                return
        profileOptions.append(argOption)
        await self.conf.guild(ctx.guild).profileoptions.set(profileOptions)
        await ctx.send(f"Done. Added '{argOption}' as a profile option.")

    @profileoptions.command(name="remove")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove_option(self, ctx:commands.Context, *args):
        """Remove a profile option. Note: This also removes them from profiles."""
        profileOptions = await self.conf.guild(ctx.guild).profileoptions()
        argOption = " ".join(args)
        try:
            profileOptions.remove(argOption)
        except KeyError:
            for option in profileOptions:
                if option.lower() == argOption.lower():
                    profileOptions.remove(option)
                    break
            else:
                await ctx.send(f"Uhhh... '{argOption}' isn't an option.")
                return
        await self.conf.guild(ctx.guild).profileoptions.set(profileOptions)
        count = 0
        for member, conf in (await self.conf.all_users()).items():
            memberProfile = conf.get("profile")
            if argOption in memberProfile.keys():
                del memberProfile[argOption]
                await self.conf.user(self.bot.get_user(member)).profile.set(memberProfile)
                count += 1
        await ctx.send(f"You got it, boss. '{argOption}'' is donezo. {count} people will be sad about it.")

    @commands.command()
    @commands.guild_only()
    async def profile(self, ctx: commands.Context, userOrOption: Optional[str] = None, *options):
        """Show/edit your profile or view someone else's.
        
        You can also view a specific option only. 
        (Ex. `[p]profile @someone optionname` (If the option name has spaces wrap it in quotes.)
        
        To remove a option from your profile, type the optionname with nothing in it.
        (Ex. `[p]profile optionname`)
        """
        await self._profile(ctx, userOrOption, *options)

    async def _profile(self, ctx: commands.Context, user: Optional[str] = None, *args):
        profileOptions = await self.conf.guild(ctx.guild).profileoptions()
        server = ctx.message.guild.name
        key = None
        if re.search(r'<@!\d+>', str(user)):
            user = ctx.guild.get_member(int(user[3:-1]))
            if not user:
                await ctx.send("lol who's that??")
                return
        if not isinstance(user, discord.abc.User):
            # Argument is a key to set, not a user
            key = user
            user = ctx.author
        profileDict = await self.conf.user(user).profile()

        # User is setting own profile
        warnings = []
        if key is not None and user is ctx.author:
            if key not in profileOptions:
                keySwap = False
                for option in profileOptions:
                    if key.lower() == option.lower():
                        key = option
                        break
                else:
                    await ctx.send("Uhhh... That isn't an option.")
                    return
            if args:
                profileDict[key] = " ".join(args)
                await self.conf.user(user).profile.set(profileDict)
                await ctx.send(f"Perf. I set your '{key}' to *“{profileDict[key]}”* — Type `k,profile` to see the updates.")
            else:
                try:
                    del profileDict[key]
                except KeyError:
                    await ctx.send(f"I can't find '{key}'. <a:pepe_sideeye:894652027387396166>")
                    return
                await self.conf.user(user).profile.set(profileDict)
                await ctx.send(f"'{key}' has been **blokT** <:blockt:792967939849453578>\n\nj/k you can add it again with `k,profile {key}`. <:hm:893502960464711710>")
            return

        # Filter dict to key(s)
        elif user and len(args):
            data = {}
            for arg in args:
                try:
                    data[arg] = profileDict[arg]
                except KeyError:
                    for option in profileOptions:
                        if arg.lower() == option.lower() and option in profileDict.keys():
                            data[option] = profileDict[option]
                            break
                    else:
                        warnings.append(f"I can't find '{arg}'. <a:pepe_sideeye:894652027387396166>")
            profileDict = data

        embed = discord.Embed()
        embed.title = f"{user.display_name}"
        embed.description = server + "\n\n"
        embed.set_thumbnail(url=user.avatar_url)
        embed.set_footer(text="\n".join(warnings))
        for option, value in profileDict.items():
            geo = profileDict.get['Location, TZ']
            if geo != "":
                loc = str("*" + geo + "*")
            else:
                loc = "*Ask me for my location/tz*"
            if option == 'Intro' and value != "":
                headline = value                
                embed.add_field(name="*“" + headline + "”*", value=loc, inline=False)                
            if option and option != 'Vibe' and option != 'Intro' and option != 'Location, TZ':
                embed.add_field(name=option, value=value, inline=True)
            else:
                embed.add_field(name="Flourishing in . . .", value=loc, inline=False)
            if option == 'Vibe':
                if value != "":
                    pic = value                
                    embed.add_field(name=option, value="My curent vibe is . . .*\n<:sh_space:755971083210981426>", inline=False)
                else:
                    pic = user.avatar_url
                embed.set_image(url=pic)
        embed.colour = ctx.author.colour
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def profilesearch(self, ctx: commands.Context, *args):
        """See what everyone's saying in their profiles.
        
        Ex. `[p]profilesearch pronouns` —  See what everyone listed as their pronouns.        
        Ex. `[p]profilesearch gender pronouns 'Steam Friend Code'` — See multiple options, including one with spaces.
        
        """
        argsLower = [x.lower() for x in args]
        embed = discord.Embed()
        embed.title = "Profile Search"
        for member, conf in (await self.conf.all_users()).items():
            memberProfile = conf.get("profile")
            if len(args) > 1:
                values = [f"{x}: {y}" for x,y in memberProfile.items() if x.lower() in argsLower]
            else:
                values = [y for x,y in memberProfile.items() if x.lower() in argsLower]
            if len(values):
                try:
                    memberName = ctx.guild.get_member(int(member)).display_name
                except:
                    continue
                embed.add_field(name=memberName,
                                value="\n".join(values),
                                inline=False)
        await ctx.send(embed=embed)
