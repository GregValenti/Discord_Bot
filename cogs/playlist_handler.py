import asyncio
import logging
from typing import cast
import json
import os

import wavelink.player
import settings
from settings import load_playlists, save_playlists
from utils.pagination import PaginationView
from utils.pagination import format_duration

import discord
from discord.ext import commands
import wavelink

logger = settings.logging.getLogger(__name__)
playlists = load_playlists()

class PlaylistHandler(commands.Cog):

    def __init__(self, bot) -> None:
        self.bot = bot

    async def join(self, ctx: commands.Context) -> None:
        """Join the user's current voice channel."""
        if not ctx.guild:
            return
        
        player = cast(wavelink.Player, ctx.voice_client) 

        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls = wavelink.Player)
            except AttributeError:
                await ctx.send("Please join a voice channel first before using this command")
                return
            except discord.ClientException:
                await ctx.send("I was unable to join this voice channel. Please try again")
                return
        elif player and ctx.author.voice.channel != player.channel:
            await ctx.send(f"I can't join other channels while already playing in <#{player.channel.id}>")

    # ==================== Playlists Commands ==================== #

    @commands.group()
    async def playlist(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send(f"Use .**playlist add**, **.playlist play**, or **.playlist remove** to manage your playlists.")    

    @playlist.command()
    async def add(self, ctx: commands.Context, name: str, *, query: str):
        """Add a song to a specific playlist."""
        guild_id = str(ctx.guild.id)

        # Create a new playlist if it doesn't exist
        if guild_id not in playlists:
            playlists[guild_id] = {}

        # Add the song to the playlist
        if name not in playlists[guild_id]:
            playlists[guild_id][name] = []
        
        if "open.spotify.com" in query:
            tracks: wavelink.Search = await wavelink.Playable.search(query)
        else:
            tracks: wavelink.Search = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)

        if isinstance(tracks, wavelink.Playlist):
            for track in tracks:
                playlists[guild_id][name].append({
                    "title": track.title,
                    "description": f"By {track.author} | Duration: {format_duration(track.length)}",
                    "url": track.uri
                })
            await ctx.send(f"Added playlist **{tracks.name}** ({len(tracks)} songs) to the playlist **{name}**")
        else:
            track: wavelink.Playable = tracks[0]
            playlists[guild_id][name].append({
                "title": track.title,
                "description": f"By {track.author} | Duration: {format_duration(track.length)}",
                "url": track.uri
            })
            await ctx.send(f"Added **{track.title}** by **{track.author}** to the playlist **{name}**")

        # Save the updated playlists
        settings.save_playlists(playlists)

    @playlist.command()
    async def play(self, ctx: commands.Context, name: str):
        """Play a specific playlist."""
        guild_id = str(ctx.guild.id)

        if guild_id in playlists and name in playlists[guild_id]:
            await self.join(ctx)
            player = cast(wavelink.Player, ctx.voice_client)

            if player:
                player.autoplay = wavelink.AutoPlayMode.partial

                if not hasattr(player, "home"):
                    player.home = ctx.channel

                for track_data in playlists[guild_id][name]:
                    query = track_data["url"]
                    if "open.spotify.com" in query:
                        tracks: wavelink.Search = await wavelink.Playable.search(query)
                    else:
                        tracks: wavelink.Search = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)

                    track: wavelink.Playable = tracks[0]
                    await player.queue.put_wait(track)

                await ctx.send(f"Playing playlist **{name}**.")
                if not player.playing:
                    await player.play(player.queue.get(), volume = 15)
        else:
            await ctx.send(f"Playlist **{name}** not found.")

    @playlist.command()
    async def list(self, ctx: commands.Context, name: str) -> None:
        """List songs from a specific playlist"""
        guild_id = str(ctx.guild.id)    

        if guild_id in playlists and name in playlists[guild_id]:
            playlist_songs = playlists[guild_id][name]
            if playlist_songs:
                titles = [song["title"] for song in playlist_songs]
                descriptions = [song["description"] for song in playlist_songs]
                view = PaginationView(playlist_title=name, titles=titles, descriptions=descriptions)
                await view.send(ctx)
            else:
                await ctx.send(f"Playlist **{name}** is empty")
        else:
            await ctx.send(f"Playlist **{name}** not found")
            
    @playlist.command()
    async def remove(self, ctx: commands.Context, name: str, *, query: str):
        """Remove a song from a specific playlist."""
        await ctx.send("work in progress")
        
async def setup(bot):
    playlist_handler = PlaylistHandler(bot)
    await bot.add_cog(playlist_handler)