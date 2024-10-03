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
    player: wavelink.Player
    current_page: int = 1
    separator: int = 10
    playlist_title: str
    titles: list
    descriptions: list

    def __init__(self, playlist_title: str, titles: list, descriptions: list):
        super().__init__()
        self.playlist_title = playlist_title
        self.titles = titles
        self.descriptions = descriptions
    
    async def send(self, ctx):
        self.message = await ctx.send(view=self)
        await self.update_message(self.titles[:self.separator], self.descriptions[:self.separator])

    def create_embed(self, titles, descriptions) -> discord.Embed:
        embed = discord.Embed(title=f"{self.playlist_title}:")
        for index, (title, description) in enumerate(zip(titles, descriptions), start=1):
            i = index + 10 * (self.current_page - 1) 
            embed.add_field(name=f"{i}.  {title}", value=f"{description}", inline=False)
        return embed
    
    async def update_message(self, titles, descriptions) -> None:
        self.update_buttons()
        await self.message.edit(embed=self.create_embed(titles, descriptions), view=self)

    def update_buttons(self) -> None:
        if self.current_page == 1:
            self.first_page_button.disabled = True
            self.prev_button.disabled = True
        else:
            self.first_page_button.disabled = False
            self.prev_button.disabled = False

        if self.current_page == int(len(self.titles) / self.separator) or len(self.titles) <= 10:
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
        await self.update_message(self.titles[:until_item], self.descriptions[:until_item])

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        self.current_page -= 1
        until_item = self.current_page * self.separator # Number of the final item on the page
        from_item = until_item - self.separator # Number of the first item of the page
        await self.update_message(self.titles[from_item:until_item], self.descriptions[from_item:until_item])

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        self.current_page += 1
        until_item = self.current_page * self.separator # Number of the final item on the page
        from_item = until_item - self.separator # Number of the first item of the page
        await self.update_message(self.titles[from_item:until_item], self.descriptions[from_item:until_item])

    @discord.ui.button(label=">|", style=discord.ButtonStyle.primary)
    async def last_page_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        self.current_page = int(len(self.titles) / self.separator)
        until_item = self.current_page * self.separator # Number of the final item on the page
        from_item = until_item - self.separator # Number of the first item of the page
        await self.update_message(self.titles[from_item:], self.descriptions[from_item:])

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