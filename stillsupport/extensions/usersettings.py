from typing import Optional

from stillsupport.extensions.abc import MixinMeta
from stillsupport.extensions.mixin import settings


class StillSupportUserSettingsMixin(MixinMeta):
    @settings.group()
    async def memberperms(self, ctx):
        """Customize what members can do with their own tickets"""
        pass

    @memberperms.command()
    async def memberclose(self, ctx, yes_or_no: Optional[bool] = None):
        """Dis/allow members to close their own tickets."""
        if yes_or_no is None:
            yes_or_no = not await self.config.guild(ctx.guild).memberclose()

        await self.config.guild(ctx.guild).memberclose.set(yes_or_no)
        if yes_or_no:
            await ctx.send("Members can now close their own tickets.")
        else:
            await ctx.send("Only Staff can close tickets now.")

    @memberperms.command()
    async def memberedit(self, ctx, yes_or_no: Optional[bool] = None):
        """Dis/allow members to add/remove others to their tickets."""
        if yes_or_no is None:
            yes_or_no = not await self.config.guild(ctx.guild).memberedit()

        await self.config.guild(ctx.guild).memberedit.set(yes_or_no)
        if yes_or_no:
            await ctx.send("Members can now add/remove others to their tickets.")
        else:
            await ctx.send("Only Staff can add/remove others to a ticket now.")

    @memberperms.command()
    async def membername(self, ctx, yes_or_no: Optional[bool] = None):
        """Dis/allow members to name tickets they open."""
        if yes_or_no is None:
            yes_or_no = not await self.config.guild(ctx.guild).membername()

        await self.config.guild(ctx.guild).membername.set(yes_or_no)
        if yes_or_no:
            await ctx.send("Members can now name tickets they open.")
        else:
            await ctx.send("Only Staff can name tickets now.")