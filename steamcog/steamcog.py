import asyncio

from datetime import datetime

# Required by Red
import aiohttp
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import bold, humanize_number
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from .stores import STORES

USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36"
}


class SteamCog(commands.Cog):
    """Get info about a Steam game and fetch PC game deals."""

    __author__ = "ifelsehatsumi"
    __version__ = "1.0.0"

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Thanks Sinbad!"""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    def __init__(self, bot: Red):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.emojis = self.bot.loop.create_task(self.init())

    def cog_unload(self):
        if self.emojis:
            self.emojis.cancel()
        self.bot.loop.create_task(self.session.close())

    # Credits and many thanks to flare#0001 for providing this logic ❤️
    async def init(self):
        await self.bot.wait_until_ready()
        self.platform_emojis = {
            "windows": discord.utils.get(self.bot.emojis, id=501562795880349696),
            "mac": discord.utils.get(self.bot.emojis, id=501561088815661066),
            "linux": discord.utils.get(self.bot.emojis, id=501561148156542996),
        }

    # Logic taken from https://github.com/TrustyJAID/Trusty-cogs/blob/master/notsobot/notsobot.py#L212
    # All credits to TrustyJAID ❤️, I do not claim any credit for this.
    async def fetch_steam_game_id(self, ctx: commands.Context, query: str):
        url = "https://store.steampowered.com/api/storesearch"
        params = {"cc": "us", "l": "en", "term": query}
        try:
            async with self.session.get(url, params=params, headers=USER_AGENT) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except asyncio.TimeoutError:
            return None
        
        if data.get("total") == 0:
            return None
        elif data.get("total") == 1:
            app_id = data.get("items")[0].get("id")
            return app_id
        elif data.get("total") > 1:
            # This logic taken from https://github.com/Sitryk/sitcogsv3/blob/master/lyrics/lyrics.py#L142
            # All credits belong to Sitryk, I do not take any credit for this code snippet.
            items = ""

            for i, value in enumerate(data.get("items"), start=1):
                items += f"**{i}.** {value.get('name')}\n"
            choices = (
                f"Found multiple games. Which # are you asking about?\n\n{items}"
            )
        
            embed = discord.Embed(
                description = choices,
                colour = 0x000000,
            )
            
            #send_to_channel = await ctx.send(choices)
            send_to_channel = await ctx.send(embed=embed)

            def check(msg):
                content = msg.content
                if (
                    content.isdigit()
                    and int(content) in range(0, len(items) + 1)
                    and msg.author is ctx.author
                    and msg.channel is ctx.channel
                ):
                    return True

            try:
                choice = await self.bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                choice = None

            if choice is None or choice.content.strip() == "0":
                await send_to_channel.edit(content="You took way too long for that bruh.")
                return None
            else:
                choice = choice.content.strip()
                choice = int(choice) - 1
                app_id = data.get("items")[choice].get("id")
                await send_to_channel.delete()
                return app_id
        else:
            return None

    @commands.command()
    @commands.bot_has_permissions(add_reactions=True, embed_links=True, read_message_history=True)
    async def steam(self, ctx: commands.Context, *, query: str):
        """Show various info and metadata about a Steam game."""
        await ctx.trigger_typing()
        app_id = await self.fetch_steam_game_id(ctx, query)
        if not app_id:
            return await ctx.send("Could not find any results.")

        base_url = "https://store.steampowered.com/api/appdetails"
        params = {"appids": app_id, "l": "en", "cc": "us", "json": 1}
        try:
            async with self.session.get(base_url, params=params, headers=USER_AGENT) as response:
                if response.status != 200:
                    return await ctx.send(f"https://http.cat/{response.status}")
                data = await response.json()
        except asyncio.TimeoutError:
            return await ctx.send("Operation timed out.")

        appdata = data[f"{app_id}"].get("data")

        pages = []
        embed = discord.Embed(
            title=appdata["name"],
            description=appdata.get("short_description", ""),
            colour=await ctx.embed_color(),
        )
        embed.url = f"https://store.steampowered.com/app/{app_id}"
        embed.set_author(name="Steam", icon_url="https://i.imgur.com/xxr2UBZ.png")
        embed.set_image(url=str(appdata.get("header_image")).replace("\\", ""))
        if appdata.get("price_overview"):
            embed.add_field(
                name="Price",
                value=appdata["price_overview"].get("final_formatted"),
            )
        if appdata.get("release_date").get("coming_soon"):
            embed.add_field(name="Release Date", value="Coming Soon")
        else:
            embed.add_field(name="Release Date", value=appdata["release_date"].get("date"))
        if appdata.get("metacritic"):
            metacritic = (
                bold(str(appdata.get("metacritic").get("score")))
                + f" ([Critic Reviews]({appdata['metacritic'].get('url')}))"
            )
            embed.add_field(name="Metacritic Score", value=metacritic)
        if appdata.get("recommendations"):
            embed.add_field(
                name="Recommendations",
                value=humanize_number(appdata["recommendations"].get("total")),
            )
        if appdata.get("achievements"):
            embed.add_field(name="Achievements", value=appdata["achievements"].get("total"))
        if appdata.get("dlc"):
            embed.add_field(name="DLC Avail.", value=len(appdata["dlc"]))
        if appdata.get("developers"):
            embed.add_field(name="Developer(s)", value=", ".join(appdata["developers"]))
        if appdata.get("publishers") and appdata.get("publishers") != [""]:
            embed.add_field(name="Publisher(s)", value=", ".join(appdata.get("publishers")))
        if appdata.get("platforms"):
            windows_emoji = self.platform_emojis["windows"] or "Microsoft Windows\n"
            linux_emoji = self.platform_emojis["linux"] or "Linux\n"
            macos_emoji = self.platform_emojis["mac"] or "Mac OS\n"
            platforms = ""
            if appdata["platforms"].get("windows"):
                platforms += f"{windows_emoji}"
            if appdata["platforms"].get("linux"):
                platforms += f"{linux_emoji}"
            if appdata["platforms"].get("mac"):
                platforms += f"{macos_emoji}"
            embed.add_field(name="Supported Platforms", value=platforms)
        if appdata.get("genres"):
            genres = ", ".join(m.get("description") for m in appdata["genres"])
            embed.add_field(name="Genre(s)", value=genres)
        footer = "Use arrows to browse through game screenshots\n"
        if appdata.get("content_descriptors").get("notes"):
            footer += f"Note: {appdata['content_descriptors']['notes']}"
        embed.set_footer(text=footer)
        pages.append(embed)

        if appdata.get("screenshots"):
            for i, preview in enumerate(appdata["screenshots"], start=1):
                embed = discord.Embed(colour=await ctx.embed_color())
                embed.title = appdata["name"]
                embed.url = f"https://store.steampowered.com/app/{app_id}"
                embed.set_author(name="Steam", icon_url="https://i.imgur.com/xxr2UBZ.png")
                embed.set_image(url=preview["path_full"])
                embed.set_footer(text=f"Preview {i} of {len(appdata['screenshots'])}")
                pages.append(embed)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60.0)

    async def fetch_deal_id(self, ctx, query: str):
        url = f"https://www.cheapshark.com/api/1.0/games?title={query}"
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except asyncio.TimeoutError:
            return None

        if len(data) == 0:
            return None
        elif len(data) == 1:
            deal_id = data[0].get("cheapestDealID")
            return deal_id
        elif len(data) > 1:
            # Attribution: https://github.com/Sitryk/sitcogsv3/blob/master/lyrics/lyrics.py#L142
            # All credits to Sitryk
            items = ""
            for i, value in enumerate(data[:20], start=1):
                items += f"**{i}.** {value.get('external')}\n"
            count = len(data) if len(data) <= 20 else 20
            choices = f"Here's the first {count} results. Choose a # or be more specific:\n\n{items}"
            send_to_channel = await ctx.send(choices)

            def check(msg):
                content = msg.content
                if (
                    content.isdigit()
                    and int(content) in range(0, len(items) + 1)
                    and msg.author is ctx.author
                    and msg.channel is ctx.channel
                ):
                    return True

            try:
                choice = await self.bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                choice = None

            if choice is None or choice.content.strip() == "0":
                await send_to_channel.delete()
                return None
            else:
                choice = choice.content.strip()
                choice = int(choice) - 1
                deal_id = data[choice].get("cheapestDealID")
                await send_to_channel.delete()
                return deal_id
        else:
            return None

    @commands.command()
    @commands.bot_has_permissions(embed_links=True, read_message_history=True)
    async def gamedeal(self, ctx: commands.Context, *, game_name: str):
        """Fetch cheapest deal for a PC game from cheaphark.com"""
        deal_id = await self.fetch_deal_id(ctx, game_name)
        if deal_id is None:
            return await ctx.send("No results.")

        async with ctx.typing():
            deal_url = f"https://www.cheapshark.com/api/1.0/deals?id={deal_id}"
            async with self.session.get(deal_url) as response:
                data = await response.json()

            embed = discord.Embed(colour=await ctx.embed_colour())
            embed.title = str(data["gameInfo"].get("name"))
            if data["gameInfo"].get("steamAppID"):
                embed.url = f"https://store.steampowered.com/app/{data['gameInfo'].get('steamAppID')}"
            embed.set_thumbnail(url=data["gameInfo"].get("thumb"))
            if data["gameInfo"].get("salePrice") == data["gameInfo"].get("retailPrice"):
                embed.description = "This game currently has no cheaper deals."
            else:
                mrp_price = data["gameInfo"].get("retailPrice")
                deal_price = data["gameInfo"].get("salePrice")
                embed.add_field(name="Retail Price", value=f"~~{mrp_price} USD~~")
                discount = round(100 - ((float(deal_price) * 100) / float(mrp_price)))
                final_deal = f"**{deal_price} USD**\n({discount}% discount)"
                embed.add_field(name="Deal Price", value=final_deal)
                deal_store_info = (
                    f"[{bold(STORES[data['gameInfo'].get('storeID')])}]"
                    + f"(https://cheapshark.com/redirect?dealID={deal_id} 'See deal')"
                )
                embed.add_field(name="Deal available on", value=deal_store_info)
            if data["gameInfo"].get("steamRatingPercent") != "0" and data["gameInfo"].get("steamRatingText"):
                steam_rating = f"{data['gameInfo'].get('steamRatingPercent')}% ({data['gameInfo'].get('steamRatingText')})"
                embed.add_field(name="Rating", value=steam_rating)
            if data.get("cheapestPrice") and data["cheapestPrice"].get("price"):
                date_from_epoch = datetime.utcfromtimestamp(data["cheapestPrice"]["date"]).strftime("%d %b %Y")
                cheapest_price = (
                    f"{data['cheapestPrice'].get('price')} USD\n(was on {date_from_epoch})"
                )
                embed.add_field(name="Historical Cheapest Price", value=cheapest_price)
            if len(embed.fields) == 5:
                embed.add_field(name="\u200b", value="\u200b")
            embed.set_footer(text="Info provided by cheapshark.com")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.bot_has_permissions(embed_links=True, read_message_history=True)
    async def latestdeals(self, ctx: commands.Context, *, sort_by: str = "recent"):
        """Fetch list of recent cheapest games from cheapshark.com

        `sort_by` argument accepts only one of the following parameter:
        `deal rating`, `title`, `savings`, `price`, `metacritic`, `reviews`, `release`, `store`, `recent`
        """
        base_url = f"https://www.cheapshark.com/api/1.0/deals?sortBy={sort_by}"

        async with ctx.typing():
            try:
                async with self.session.get(base_url) as response:
                    if response.status != 200:
                        return await ctx.send(f"https://http.cat/{response.status}")
                    results = await response.json()
            except asyncio.TimeoutError:
                return await ctx.send("Operation timed out.")

            pages = []
            for i, data in enumerate(results, start=1):
                embed = discord.Embed(colour=await ctx.embed_color())
                embed.title = str(data["title"])
                shop = data.get('storeID')
                if data.get("steamAppID"):
                    embed.url = f"https://store.steampowered.com/app/{data.get('steamAppID')}"
                embed.set_thumbnail(url=data.get("thumb"))
                if data.get("salePrice") == data.get("normalPrice"):
                    embed.description = "This game currently has no cheaper deals."
                else:
                    mrp_price = data.get("normalPrice")
                    deal_price = data.get("salePrice")
                    embed.add_field(name="Retail Price", value=f"~~{mrp_price} USD~~")
                    discount = round(float(data.get("savings")))
                    final_deal = f"**{deal_price} USD**\n({discount}% discount)"
                    embed.add_field(name="Deal Price", value=final_deal)
                    deal_store_info = (
                        f"[{bold(STORES[shop])}]"
                        + f"(https://cheapshark.com/redirect?dealID={data['dealID']} 'See deal')"
                    )
                    embed.add_field(name="Deal available on", value=deal_store_info)
                if data.get("steamRatingPercent") != "0" and data.get("steamRatingText"):
                    steam_rating = f"{data.get('steamRatingPercent')}% ({data.get('steamRatingText')})"
                    embed.add_field(name="Rating", value=steam_rating)
                if len(embed.fields) == 5:
                    embed.add_field(name="\u200b", value="\u200b")
                embed.set_footer(text=f"Deal {i} of " + str(len(results)) + " | Info provided by cheapshark.com.")
                pages.append(embed)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60.0)
