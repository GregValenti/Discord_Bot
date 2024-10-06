import settings
import discord
from discord.ext import commands
from utils.pagination import create_green_embed, create_red_embed

logger = settings.logging.getLogger("bot")

def run():
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix=".", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"User: {bot.user} (ID: {bot.user.id})")
        await bot.load_extension("cogs.music")
        await bot.load_extension("cogs.playlist_handler")

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            embed: discord.Embed = create_red_embed(
                description=f"Command **{ctx.invoked_with}** not found. Use **.help** for informations on available commands."
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.NotOwner):
            embed: discord.Embed = create_red_embed(
                description="You do not have permission to use this command."
            )
            await ctx.send(embed=embed)
        else:
            raise error

    @bot.command(hidden=True)
    @commands.is_owner()
    async def load(ctx: commands.Context, cog: str):
        await bot.load_extension(f"cogs.{cog.lower()}")

    @bot.command(hidden=True)
    @commands.is_owner()
    async def unload(ctx: commands.Context, cog: str):
        await bot.unload_extension(f"cogs.{cog.lower()}")

    @bot.command(hidden=True)
    @commands.is_owner()
    async def reload(ctx: commands.Context, cog: str):
        await bot.reload_extension(f"cogs.{cog.lower()}")

    bot.run(settings.DISCORD_API_TOKEN, root_logger=True)

if __name__ == "__main__":
    run()