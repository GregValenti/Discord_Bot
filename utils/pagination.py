import logging
import discord 
from discord.ext import commands
import wavelink
import settings

logger = settings.logging.getLogger("bot")

def format_duration(duration: int) -> str:
    minutes, seconds = divmod(duration // 1000, 60)
    return f"{minutes}:{seconds:02d}"  

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
    
    async def send(self, ctx: commands.Context):
        self.message = await ctx.send(view=self)
        await self.update_message(self.titles[:self.separator], self.descriptions[:self.separator])

    def create_embed(self, titles, descriptions) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.blurple(), title=f"{self.playlist_title}:")
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

class ConfirmationView(discord.ui.View):
    ctx: commands.Context
    player: wavelink.Player
    playlist_title: str
    playlists: list
    guild_id: str
    confirmation_received: bool

    def __init__(self, ctx: commands.Context, playlist_title: str, playlists: list, timeout: float = 20.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.playlist_title = playlist_title
        self.playlists = playlists
        self.guild_id = str(ctx.guild.id)
        self.confirmation_received = False

    async def send(self, ctx: commands.Context) -> None:
        embed = discord.Embed(
            color=discord.Color.dark_green(),
            title="",
            description=f"Are you sure you want to permanently delete **{self.playlist_title}**?"
        )
        self.message = await ctx.send(embed=embed, view=self)
        await self.update_buttons()

    async def remove_playlist(self) -> None:
        if self.guild_id in self.playlists and self.playlist_title in self.playlists[self.guild_id]:
            self.playlists[self.guild_id].pop(self.playlist_title)
            settings.save_playlists(self.playlists)

            embed = create_green_embed(
                description=f"Playlist **{self.playlist_title}** has been removed."
            )
            await self.ctx.send(embed=embed)

    async def cancel_removal(self):
        embed = create_red_embed(
            description=f"Canceled the removal of playlist **{self.playlist_title}**."
        )
        await self.ctx.send(embed=embed)
    
    def disable_buttons(self):
        self.confirm_button.disabled = True
        self.cancel_button.disabled = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user == self.ctx.author:
            await interaction.response.defer()
            await self.remove_playlist()
            
            self.disable_buttons()
            await self.message.edit(view=self)
            self.stop()
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user == self.ctx.author:
            await interaction.response.defer()
            await self.cancel_removal()

            self.disable_buttons()
            await self.message.edit(view=self)
            self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the request author can interact with the buttons.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self) -> None:
        self.disable_buttons()
        await self.message.edit(view=self)

        timeout_embed = create_red_embed(
            description="No interaction detected, disabling buttons...",
        )
        await self.ctx.send(embed=timeout_embed)