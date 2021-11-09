# -*- coding: utf-8 -*-
from .profile import Profile

async def setup(bot):
    bot.add_cog(Profile(bot))
