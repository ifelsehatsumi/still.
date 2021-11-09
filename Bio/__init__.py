# -*- coding: utf-8 -*-
from .bio import Bio

async def setup(bot):
    bot.add_cog(Bio(bot))