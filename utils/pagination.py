import logging
import discord 
from discord.ext import commands
import wavelink
import settings

logger = settings.logging.getLogger("bot")

def format_duration(duration: int) -> str:
    minutes, seconds = divmod(duration // 1000, 60)
    return f"{minutes}:{seconds:02d}"  

class PaginationView(discord.ui.View):
    current_page: int = 1
    separator: int = 10
    songs: list
    title: str
    player: wavelink.Player

    def __init__(self, songs: list, title: str):
        super().__init__()
        self.songs = songs
        self.title = title
    
    async def send(self, ctx):
        self.message = await ctx.send(view=self)
        await self.update_message(self.songs[:self.separator])

    def create_embed(self, songs) -> discord.Embed:
        embed = discord.Embed(title=f"**{self.title}:**")
        for index, song in enumerate(songs, start=1):
            i = index + 10 * (self.current_page - 1)
            embed.add_field(name=f"{i}.  {song}", value="", inline=False)
        return embed
    
    async def update_message(self, songs) -> None:
        self.update_buttons()
        await self.message.edit(embed=self.create_embed(songs), view=self)

    def update_buttons(self) -> None:
        if self.current_page == 1:
            self.first_page_button.disabled = True
            self.prev_button.disabled = True
        else:
            self.first_page_button.disabled = False
            self.prev_button.disabled = False

        if self.current_page == int(len(self.songs) / self.separator) or len(self.songs) <= 10:
            self.next_button.disabled = True
            self.last_page_button.disabled = True
        else:
            self.next_button.disabled = False
            self.last_page_button.disabled = False

    @discord.ui.button(label="|<", style=discord.ButtonStyle.primary)
    async def first_page_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        self.current_page = 1
        until_item = self.current_page * self.separator # Number of the final item on the page
        await self.update_message(self.songs[:until_item])

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        self.current_page -= 1
        until_item = self.current_page * self.separator # Number of the final item on the page
        from_item = until_item - self.separator # Number of the first item of the page
        await self.update_message(self.songs[from_item:until_item])

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        self.current_page += 1
        until_item = self.current_page * self.separator # Number of the final item on the page
        from_item = until_item - self.separator # Number of the first item of the page
        await self.update_message(self.songs[from_item:until_item])

    @discord.ui.button(label=">|", style=discord.ButtonStyle.primary)
    async def last_page_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        self.current_page = int(len(self.songs) / self.separator)
        until_item = self.current_page * self.separator # Number of the final item on the page
        from_item = until_item - self.separator # Number of the first item of the page
        await self.update_message(self.songs[from_item:])

def create_green_embed(*, title: str = "", description: str = "") -> discord.Embed:
    embed: discord.Embed = discord.Embed(
        color=discord.Color.dark_green(),
        title = title,
        description=description)
    return embed

def create_red_embed(*, title: str = "", description: str = "") -> discord.Embed:
    embed: discord.Embed = discord.Embed(
        color=discord.Color.dark_red(),
        title=title,
        description=description)
    return embed