from .stillsupport import StillSupport


def setup(bot):
    bot.add_cog(StillSupport(bot))