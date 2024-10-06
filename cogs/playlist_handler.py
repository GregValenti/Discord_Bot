import asyncio
import logging
from typing import cast
import json
import os

import wavelink.player
import settings
from settings import load_playlists, save_playlists
from utils.pagination import PaginationView, ConfirmationView
from utils.pagination import format_duration, create_green_embed, create_red_embed

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

    # ==================== Playlists Commands ==================== #

    @commands.group()
    async def playlist(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            embed: discord.Embed = create_red_embed(
                description="Use **.playlist help** for informations on available playlist commands."
            )
            await ctx.send(embed=embed)

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
            embed: discord.Embed = create_green_embed(
                description=f"Added playlist **{tracks.name}** ({len(tracks)} songs) to the playlist **{name}**."
            )
            await ctx.send(embed=embed)
        else:
            track: wavelink.Playable = tracks[0]
            playlists[guild_id][name].append({
                "title": track.title,
                "description": f"By {track.author} | Duration: {format_duration(track.length)}",
                "url": track.uri
            })
            embed: discord.Embed = create_green_embed(
                description=f"Added **{track.title}** by **{track.author}** to the playlist **{name}**."
            )
            await ctx.send(embed=embed)

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

                embed: discord.Embed = create_green_embed(
                    description=f"Playing playlist **{name}**."
                )
                await ctx.send(embed=embed)
                if not player.playing:
                    await player.play(player.queue.get(), volume = 15)
        else:
            embed: discord.Embed = create_red_embed(
                description=f"Playlist **{name}** not found."
            )
            await ctx.send(embed=embed)

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
                embed: discord.Embed = create_red_embed(
                    description=f"Playlist **{name}** is empty."
                )
                await ctx.send(embed=embed)
        else:
            embed: discord.Embed = create_red_embed(
                description=f"Playlist **{name}** not found."
            )
            await ctx.send(embed=embed)
            
    @playlist.command()
    async def remove(self, ctx: commands.Context, name: str, *, song_name: str = None) -> None:
        """Remove a song from a specific playlist."""
        guild_id = str(ctx.guild.id)

        if guild_id in playlists and name in playlists[guild_id]:
            
            # The following code is to remove the entire playlist
            if song_name is None:
                view = ConfirmationView(ctx, name, playlists)
                await view.send(ctx)
                return
            
            # The following code is to remove a secific song
            playlist_songs = playlists[guild_id][name]
            if playlist_songs:

                found_track = None
                for i, track in enumerate(playlist_songs):
                    if song_name.lower() in track["title"].lower():
                        found_track = track
                        playlist_songs.pop(i)
                        settings.save_playlists(playlists)
                        embed: discord.Embed = create_green_embed(
                            description=f"Removed {found_track['title']} from playlist {name}."
                        )
                        await ctx.send(embed=embed) 

                if found_track == None:
                    embed: discord.Embed = create_red_embed(
                        description=f"Track {song_name} not found in playlist {name}."
                    )
                    await ctx.send(embed=embed)
            else:
                embed: discord.Embed = create_red_embed(
                    description=f"Playlist {name} is empty."
                )
                await ctx.send(embed=embed)
        else:
            embed: discord.Embed = create_red_embed(
                description=f"Playlist {name} not found."
            )
            await ctx.send(embed=embed)   
        
async def setup(bot):
    playlist_handler = PlaylistHandler(bot)
    await bot.add_cog(playlist_handler)