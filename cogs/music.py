import asyncio
import logging
from typing import cast
import json
import os

import wavelink.player
import settings
from settings import load_playlists, save_playlists
from utils.pagination import PaginationView, format_duration, create_green_embed, create_red_embed

import discord
from discord.ext import commands
import wavelink

logger = settings.logging.getLogger(__name__)

# ==================== Class Definition ==================== # 

class MusicBot(commands.Cog):

    def __init__(self, bot) -> None:
        self.bot = bot
        self.loop_enabled = False

    async def setup_hook(self) -> None:
        nodes = [wavelink.Node(
            uri = "http://localhost:2333",
            password = "youshallnotpass"
        )]
        await wavelink.Pool.connect(
            nodes = nodes,
            client = self.bot,
            cache_capacity = 100
        )

    # ==================== Event Listeners ==================== #

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        logger.info(f"Wavelink node connected: {payload.node} | Resumed: {payload.resumed}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player: wavelink.Player | None = payload.player
        if not player:
            # This is handled in other functions
            return 
        
        original: wavelink.Playable | None = payload.original
        track: wavelink.Playable = payload.track

        embed: discord.Embed = create_green_embed(
            title="Now Playing:", 
        )
        embed.add_field(name=f"**{track.title}**", value=f"By **{track.author}**")
        if track.artwork:
            embed.set_image(url = track.artwork)

        if original and original.recommended:
            embed.description += f"\n\n'This track was recommended via {track.source}'"

        if track.album.name:
            embed.add_field(name = "Album", value = track.album.name)

        await player.home.send(embed = embed)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player: wavelink.Player | None = payload.player
        if not player:
            return

        if self.loop_enabled:
            track: wavelink.Playable = payload.track
            await player.queue.put_wait(track)

    # ==================== Player Commands ==================== #

    @commands.command()
    async def join(self, ctx: commands.Context) -> None:
        """Join the user's current voice channel."""
        if not ctx.guild:
            return
        
        player = cast(wavelink.Player, ctx.voice_client) 
        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls = wavelink.Player)
            except AttributeError:
                embed: discord.Embed = create_red_embed(
                    description="Please join a voice channel first before using this command."
                )
                await ctx.send(embed=embed)
                return
            except discord.ClientException:
                embed: discord.Embed = create_red_embed(
                    description="I was unable to join this voice channel. Please try again."
                )
                await ctx.send(embed=embed)
                return
        elif player and ctx.author.voice.channel != player.channel:
            embed: discord.Embed = create_red_embed(
                description=f"I can't join other channels while already playing in <#{player.channel.id}>."
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a song with the given query."""
        await self.join(ctx)
        player = cast(wavelink.Player, ctx.voice_client)  

        if player:  
            player.autoplay = wavelink.AutoPlayMode.partial

            if not hasattr(player, "home"):
                player.home = ctx.channel
            # The following code locks the bot to the initial text channel
            # elif player.home != ctx.channel:
            #     await ctx.send(f"You can only play songs in {player.home.mention}, as the Player has already started there")
            #     return

            # Look for spotify tracks first, otherwise use YouTube
            if "open.spotify.com" in query:
                tracks: wavelink.Search = await wavelink.Playable.search(query)
            else:
                tracks: wavelink.Search = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
        
            if not tracks:
                embed: discord.Embed = create_red_embed(
                    description="I Could not find any tracks with that query."
                )
                await ctx.send(embed=embed)
                return
            
            if isinstance(tracks, wavelink.Playlist):
                added: int = await player.queue.put_wait(tracks)
                embed: discord.Embed = create_green_embed(
                    description=f"Added the playlist **{tracks.name}** ({added} songs) to the queue."
                )
                await ctx.send(embed=embed)
            else:
                track: wavelink.Playable = tracks[0]
                await player.queue.put_wait(track)
                embed: discord.Embed = create_green_embed(
                    description=f"Added **{track}** by **{track.author}** to the queue."
                )
                await ctx.send(embed=embed)

            if not player.playing:
                await player.play(player.queue.get(), volume = 15)
        else:
            return
        
    @commands.command(aliases = ["next"])
    async def skip(self, ctx: commands.Context) -> None:
        """Skip the current song."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return
        
        await player.skip(force = True)
        embed: discord.Embed = create_green_embed(
            description="Skipped the current track."
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def pause(self, ctx: commands.Context) -> None:
        """Pause the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        await player.pause(True)
        embed: discord.Embed = create_green_embed(
            description="Paused the Player."
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def resume(self, ctx: commands.Context) -> None:
        """Resume the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        await player.pause(False)
        embed: discord.Embed = create_green_embed(
            description="Resumed the Player."
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def stop(self, ctx: commands.Context) -> None:
        """Stop the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        await self.clear(ctx)
        await player.stop()
        self.loop_enabled = False
        embed: discord.Embed = create_green_embed(
            description="Stopped the Player."
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def leave(self, ctx: commands.Context) -> None:
        """Disconnect the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return
        
        await player.disconnect()
        embed: discord.Embed = create_green_embed(
            description="Bye! :wave:"
        )
        await ctx.send(embed=embed)

    # ==================== Queue Commands ==================== #
    
    @commands.command()
    async def queue(self, ctx: commands.Context) -> None:
        """Displays the song queue"""
        player = cast(wavelink.Player, ctx.voice_client)
        
        if not player or not player.queue and not player.playing:
            embed: discord.Embed = create_red_embed(
                description="There are no songs in the queue."
            )
            await ctx.send(embed=embed)
            return
        
        titles = []
        descriptions = []
        if player.playing:
            titles.append(f"Now Playing: {player.current.title}")
            descriptions.append(f"By {player.current.author} | Duration: {format_duration(player.current.length)}")

        for track in player.queue:
            titles.append(f"{track.title}")
            descriptions.append(f"By {track.author} | Duration: {format_duration(track.length)}")
        
        pagination_view = PaginationView(playlist_title="Current Queue", titles=titles, descriptions=descriptions)
        await pagination_view.send(ctx)

    @commands.command()
    async def loop(self, ctx: commands.Context) -> None:
        """Toggles Loop on the current queue"""
        self.loop_enabled = not self.loop_enabled
        status = "enabled" if self.loop_enabled else "disabled"
        embed: discord.Embed = create_green_embed(
            description=f"Looping has been {status}"
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def shuffle(self, ctx: commands.Context) -> None:
        player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue:
            embed: discord.Embed = create_red_embed(
                description="The queue is empty."
            )
            await ctx.send(embed=embed)
            return
        
        player.queue.shuffle()
        embed: discord.Embed = create_green_embed(
            description="The queue has been shuffled."
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def jump(self, ctx: commands.Context, *, query: str) ->None:
        """Jump to a song in the queue and play it"""
        player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue:
            embed: discord.Embed = create_red_embed(
                description="The queue is empty."
            )
            await ctx.send(embed=embed)
            return
        
        found_track = None
        for i, track in enumerate(player.queue):
            if query.lower() in track.title.lower():
                found_track = track
                player.queue.delete(i)
                break
        
        if found_track == None:
            embed: discord.Embed = create_red_embed(
                description=f"No track found that matches the query: **{query}**."
            )
            await ctx.send(embed=embed)
            return
        
        embed: discord.Embed = create_green_embed(
            description=f"Jumped to **{found_track.title}** by **{found_track.author}**."
        )
        await ctx.send(embed=embed)
        await player.play(found_track)

    @commands.command()
    async def clear(self, ctx: commands.Context) -> None:
        """Clears the queue"""
        player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue:
            embed: discord.Embed = create_red_embed(
                description=f"The queue is already empty."
            )
            await ctx.send(embed=embed)
            return
        
        player.queue.clear()
        embed: discord.Embed = create_green_embed(
            description="The queue has been cleared."
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def remove(self, ctx: commands.Context, *, query: str) -> None:
        """Removes the specified song from the queue"""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue:
            embed: discord.Embed = create_red_embed(
            title="The queue is already empty."
            )
            await ctx.send(embed=embed)
            return
        
        found_track = None
        for i, track in enumerate(player.queue):
            if query.lower() in track.title.lower():
                found_track = track
                player.queue.delete(i)
                break
        
        if found_track == None:
            embed: discord.Embed = create_red_embed(
                title=f"No track found that matches the query: **{query}**"
            )
            await ctx.send(embed=embed)
            return

        embed: discord.Embed = create_green_embed(
            title=f"Removed {found_track.title} by {found_track.author} from the queue."
        )
        await ctx.send(embed=embed)

    # ==================== Miscellaneous Commands ==================== #

    @commands.command()
    async def helldive(self, ctx: commands.Context) -> None:
        """Plays Fortunate Son by Creedence Clearwater Revival"""
        await self.play(ctx, query = "https://www.youtube.com/watch?v=ZWijx_AgPiA")
        

async def setup(bot):
    music_bot = MusicBot(bot)
    await bot.add_cog(music_bot)
    await music_bot.setup_hook()