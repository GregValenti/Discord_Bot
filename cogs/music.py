import asyncio
import logging
from typing import cast

import wavelink.player
import settings

import discord
from discord.ext import commands
import wavelink

logger = settings.logging.getLogger(__name__)

def format_duration(duration: int) -> str:
    minutes, seconds = divmod(duration // 1000, 60)
    return f"{minutes}:{seconds:02d}"  

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
            # TODO - Handle edge cases
            return 
        
        original: wavelink.Playable | None = payload.original
        track: wavelink.Playable = payload.track

        embed: discord.Embed = discord.Embed(title = "Now Playing:")
        embed.description = f"**{track.title}** by **{track.author}**"
        
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
                await ctx.send("Please join a voice channel first before using this command")
                return
            except discord.ClientException:
                await ctx.send("I was unable to join this voice channel. Please try again")
                return
        elif player and ctx.author.voice.channel != player.channel:
            await ctx.send(f"I can't join other channels while already playing in <#{player.channel.id}>")

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
                        
            tracks: wavelink.Search = await wavelink.Playable.search(query)
            if not tracks:
                await ctx.send(f"{ctx.author.mention} - Could not find any tracks with that query")
                return
            
            if isinstance(tracks, wavelink.Playlist):
                added: int = await player.queue.put_wait(tracks)
                await ctx.send(f"Added the playlist **{tracks.name}** ({added} songs) to the queue")
            else:
                track = wavelink.Playable = tracks[0]
                await player.queue.put_wait(track)
                await ctx.send(f"Added **{track}** by **{track.author}** to the queue")

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
        await ctx.send(f"Skipped the current track")

    @commands.command()
    async def pause(self, ctx: commands.Context) -> None:
        """Pause the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        await player.pause(True)
        await ctx.send(f"Paused the Player")

    @commands.command()
    async def resume(self, ctx: commands.Context) -> None:
        """Pause the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        await player.pause(False)
        await ctx.send(f"Resumed the Player")

    @commands.command()
    async def stop(self, ctx: commands.Context) -> None:
        """Stop the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        await player.stop()
        await ctx.send(f"Stopped the Player")

    @commands.command()
    async def leave(self, ctx: commands.Context) -> None:
        """Disconnect the Player."""
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return
        
        await player.disconnect()
        await ctx.send(f"Left the voice channel")

    # ==================== Queue Commands ==================== #

    @commands.command()
    async def queue(self, ctx: commands.Context) -> None:
        """Displays the song queue"""
        player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue and not player.playing:
            await ctx.send(f"There are no songs in the queue")
            return

        embed = discord.Embed(title = "Current Queue", color = discord.Color.blurple())

        if player.playing:
            embed.add_field(
                name = "Now playing",
                value = f"**{player.current.title}** by {player.current.author} | Duration: {format_duration(player.current.length)}",
                inline = False
            )

        for i, track in enumerate(player.queue):
            embed.add_field(
                name = f"{i+1}. {track.title}",
                value = f"By {track.author} | Duration: {format_duration(track.length)}",
                inline = False
            )
        
        await ctx.send(embed = embed)

    @commands.command()
    async def loop(self, ctx: commands.Context) -> None:
        """Toggles Loop on the current queue"""
        self.loop_enabled = not self.loop_enabled
        status = "enabled" if self.loop_enabled else "disabled"
        await ctx.send(f"Looping has been {status}")

    @commands.command()
    async def shuffle(self, ctx: commands.Context) -> None:
        player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue:
            await ctx.send(f"The queue is empty")
            return
        
        player.queue.shuffle()    
        await ctx.send(f"The queue has been shuffled")

    @commands.command()
    async def jump(self, ctx: commands.Context, *, query: str) ->None:
        """Jump to a song in the queue and play it"""
        player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue:
            await ctx.send(f"The queue is empty")
            return
        
        found_track = None
        for i, track in enumerate(player.queue):
            if query.lower() in track.title.lower():
                found_track = track
                player.queue.delete(i)
                break
        
        if found_track == None:
            await ctx.send(f"No track found that matches the query: **{query}**")
            return
        
        await ctx.send(f"Jumped to **{found_track.title}** by **{found_track.author}**")  
        await player.play(found_track)

    @commands.command()
    async def clear(self, ctx: commands.Context) -> None:
        """Clears the queue"""
        player = cast(wavelink.Player, ctx.voice_client)

        if not player or not player.queue:
            await ctx.send(f"The queue is already empty")
            return
        
        player.queue.clear()
        await ctx.send(f"The queue has been cleared")

    # ==================== Miscellaneous Commands ==================== #

    @commands.command()
    async def helldive(self, ctx: commands.Context) -> None:
        """Plays Fortunate Son by Creedence Clearwater Revival"""
        await self.play(ctx, query = "https://www.youtube.com/watch?v=ZWijx_AgPiA")
        

async def setup(bot):
    music_bot = MusicBot(bot)
    await bot.add_cog(music_bot)
    await music_bot.setup_hook()