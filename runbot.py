# %% imports
# std lib
import asyncio
from asyncio import Semaphore
import random
import os
from datetime import datetime, timedelta, timezone
import json
import io
from typing import Union, Any
import pandas as pd
from matplotlib import pyplot as plt

# 3rd party
# from skimage.metrics import structural_similarity as ssim
# import numpy as np
import aiohttp
from aiohttp import ClientSession
from dotenv import dotenv_values
from tqdm.asyncio import tqdm as async_tqdm
from tqdm import tqdm
from PIL import Image as PILImage
from PIL.Image import Image

# custom
import discord
from discord.ext import commands
from discord import Member, TextChannel, VoiceChannel, CategoryChannel
from discord.guild import Guild

GuildChannel = Union[TextChannel, VoiceChannel, CategoryChannel]

# %% config
config = dotenv_values(".env")
assert config["TOKEN"], "TOKEN is not set in .env"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class Momo(commands.Bot):
    guild: Guild
    channel: GuildChannel
    guild_members: list[Any]


bot = Momo(command_prefix="$", intents=intents)

DELV_GUILD_ID = 754739461707006013
ROBOTS_CHANNEL = 1035343815088816258
MIHAI_ID = 135898637422166016

delv_pfp: Image = PILImage.open("delvpfp.png").convert("RGB")

# %% commands


async def populate_recent_joiners(guild):
    user_data = {}
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    for member in tqdm(guild.members, desc="Populating recent joiners"):
        joined_at = member.joined_at
        if joined_at and joined_at > seven_days_ago:
            user_data[str(member.id)] = joined_at.isoformat()

    with open("members.json", "w", encoding="utf-8") as file:
        json.dump(user_data, file)


# async def is_imposter(member: Member, delv_pfp: Image, timeout=5):
#     avatar = str(member.display_avatar)

#     async with httpx.AsyncClient() as client:
#         response = await client.get(avatar, timeout=timeout)
#     avatar_img: Image = PILImage.open(io.BytesIO(response.content)).convert("RGB")

#     # Convert images to numpy arrays
#     avatar_img_np = np.array(avatar_img)
#     delv_pfp_np = np.array(delv_pfp)

#     # Ensure both images have the same dimensions
#     if avatar_img_np.shape != delv_pfp_np.shape:
#         return False

#     # Compute SSIM between two images
#     similarity_index = ssim(avatar_img_np, delv_pfp_np, multichannel=True)
#     print(f"{similarity_index=}")

#     # Return True if images are identical, False otherwise
#     return similarity_index == 1.0


async def find_member(guild: Guild, delv_pfp: Image, channel: GuildChannel):
    # member_display_name = "Element Finance® NOTICE#8822"
    # member = discord.utils.find(lambda m: m.display_name == member_display_name, guild.members)
    member_name_plus_discriminator = "mihai#3002"
    member = discord.utils.find(lambda m: f"{m.name}#{m.discriminator}" == member_name_plus_discriminator, guild.members)
    if member is None:
        print("Member not found")
    else:
        print(f"Found member {member.display_name} with ID {member.id} joined at {member.joined_at} role {member.top_role}")
        is_imposter_result = await is_imposter(member, delv_pfp)  # type: ignore
        print(f"They {'ARE' if is_imposter_result else 'ARE NOT'} an imposter")


# print(f"{member.display_name} is an imposter! ID {member.id} joined {member_join_time.strftime('%d %B %Y')}")

# await member.kick(reason="Imposter")


async def report_imposter(member: Member, channel: GuildChannel):
    member_join_time = member.joined_at
    assert isinstance(member_join_time, datetime), "join time is not a datetime for {member.display_name}#{member.discriminator} ({member.id})"
    # print(f"Found member {member.display_name} with ID {member.id} joined at {member.joined_at} role {member.top_role}")
    # print(f"{member.display_name}#{member.discriminator} is an imposter! ID {member.id} joined {member_join_time.strftime('%d %B %Y')}")
    # Create an embed message
    embed = discord.Embed(title=f"{member.display_name} is an imposter!", description=f"Joined {member_join_time.strftime('%d %B %Y')}", color=discord.Color.red())
    embed.set_thumbnail(url=str(member.display_avatar))

    # Send the embed message to the channel
    await channel.send(embed=embed)


async def check_for_imposters(guild, channel: GuildChannel, atatime=5):
    semaphore: Semaphore = asyncio.Semaphore(atatime)  # Initialize a semaphore with a limit of 5 simultaneous tasks
    async with aiohttp.ClientSession() as session:
        tasks = [check_member(member, session, semaphore, channel) for member in tqdm(guild.members, desc="Checking for imposters") if member.display_avatar]
        for future in async_tqdm.as_completed(tasks, desc="Checking for imposters"):
            await future


async def get_member(member: Member, semaphore, session) -> dict:
    async with semaphore:
        return {
            "id": member.id,
            "name": member.name,
            "discriminator": member.discriminator,
            "joined_at": member.joined_at,
            "created_at": member.created_at,
            "avatar": member.avatar,
            "display_avatar": member.display_avatar,
            "display_name": member.display_name,
            "top_role": member.top_role,
        }


async def get_guild_members(atatime=5) -> pd.DataFrame:
    semaphore: asyncio.Semaphore = asyncio.Semaphore(atatime)  # Initialize a semaphore with a limit of 5 simultaneous tasks
    async with aiohttp.ClientSession() as session:
        tasks = [
            get_member(member, semaphore, session)
            for member in bot.guild.members
            # if member.display_avatar
        ]
        guild_members = []
        for future in async_tqdm.as_completed(tasks, desc="Getting members"):
            result = await future
            guild_members.append(result)
        return pd.DataFrame(guild_members)


async def check_member(member: Member, session: ClientSession, semaphore, channel: GuildChannel):
    async with semaphore:
        is_member_imposter = await is_imposter(member, delv_pfp, session)
        if is_member_imposter:
            await report_imposter(member, channel)


async def is_imposter(member: Member, delv_pfp: Image, session=aiohttp.ClientSession(), timeout=5):
    avatar = str(member.display_avatar)
    try:
        async with session.get(avatar, timeout=timeout) as response:
            response_content = await response.read()
        avatar_img: Image = PILImage.open(io.BytesIO(response_content)).convert("RGB")
        return avatar_img == delv_pfp
    except asyncio.TimeoutError:
        print(f"Timeout error occurred while fetching avatar for {member.display_name}#{member.discriminator} ({member.id})")
        return False


@bot.event
async def on_member_join(member):
    joined_at = member.joined_at  # datetime object
    if joined_at > datetime.now(timezone.utc) - timedelta(days=7):  # Check if the member joined within the last 7 days
        user_data = {str(member.id): joined_at.isoformat()}  # Convert datetime to string
        if os.path.exists("members.json"):  # If the file already exists, load it and append the new member
            with open("members.json", "r", encoding="utf-8") as file:
                data = json.load(file)
            data.update(user_data)
            with open("members.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
        else:  # If the file doesn't exist, create it and add the new member
            with open("members.json", "w", encoding="utf-8") as file:
                json.dump(user_data, file)


@bot.command(
    name="imposters",
    description="Checks for imposters",
    pass_context=True,
)
async def imposters(context):
    if context.channel != bot.channel:
        await context.send("This command can only be used in the 🤖︱ro-bots channel.")
        return
    if context.guild != bot.guild:
        await context.send("This command can only be used in the DELV server.")
        return
    await check_for_imposters(context.guild, context.channel)


@bot.command(
    name="say",
    description="Tells you what to say",
    pass_context=True,
)
async def say(context, *args):
    if context.channel != bot.channel:
        return
    if context.author.id != MIHAI_ID:
        response_list = ["You're not my mom! :angry:", "I only listen to Mihai! :dogegun:", "*bites a toe* :dogelick:", "You can't tell me what to do! :dogwhat:"]
        await context.send(random.choice(response_list))
    await context.send(" ".join(args))


@bot.command(
    name="hello",
    description="Sends a hello message",
    pass_context=True,
)
async def hello(context):
    await context.send("Hello!")


@bot.command(
    name="hardstyle",
    description="Plays a random hardstyle mp3 from Mihai's collection",
    pass_context=True,
)
async def hardstyle(context):
    user = context.author  # grab the user who sent the command
    voice_channel = user.voice.channel if user.voice else None
    channel = None
    # only play music if user is in a voice channel
    if voice_channel is not None:
        # grab user's voice channel
        channel = voice_channel.name
        # connect to voice channel and create AudioSource
        vc = await voice_channel.connect()
        # pick a random file from /data/mp3s
        file = random.choice(os.listdir("/data/mp3s"))
        await context.send(f"Playing {file[:-4]} in {channel}")
        source = discord.FFmpegPCMAudio(f"/data/mp3s/{file}")
        vc.play(source, after=lambda e: print("Player error: {e}") if e else None)
        while vc.is_playing():
            await asyncio.sleep(1)
        # disconnect after the player has finished
        vc.stop()
        await vc.disconnect()
    else:
        await context.send("User is not in a channel.")


async def save_guild_members_df():
    guild_members = await get_guild_members()
    guild_members_df = pd.DataFrame(guild_members)
    guild_members_df.to_csv("guild_members.csv", index=False)
    print("saved guild members to csv")


# %%
@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    assert (guild := bot.get_guild(DELV_GUILD_ID)), "Guild not found"
    bot.guild = guild
    assert (channel := bot.get_channel(ROBOTS_CHANNEL)), "Channel not found"
    assert isinstance(channel, GuildChannel), "Channel is not a GuildChannel = Union[TextChannel, VoiceChannel, CategoryChannel]"
    bot.channel = channel
    df = await get_guild_members()
    df.to_csv("guild_members.csv", index=False)
    print("saved guild members to csv")
    # await populate_recent_joiners(guild)
    # await find_member(guild, delv_pfp, channel)


# %% run it
bot.run(config["TOKEN"])

# %%
df = pd.read_csv("guild_members.csv")

# count cumulative joins without a 5 minute break
# date format "2021-05-11 07:27:17+00:00"
df["joined_at"] = pd.to_datetime(df["joined_at"], format="mixed")
df = df.sort_values(by="joined_at", ascending=True).reset_index(drop=True)
df["previous_joined_at"] = df["joined_at"].shift(1)
df["join_delta"] = df["joined_at"] - df["previous_joined_at"]
df["join_delta"] = df["join_delta"].dt.seconds / 60  # in minutes

# boolean column which will be True when `join_delta` > 5 and False otherwise
df["reset_point"] = df["join_delta"] > 5

# `cumsum` on a boolean column will create distinct groups each time `reset_point` is True
df["group"] = df["reset_point"].cumsum()

# groupby 'group' and create a running count within each group
df["consecutive_joins"] = df.groupby("group").cumcount()

# If you don't want to keep the 'group' and 'reset_point' columns, you can drop them
df = df.drop(columns=["reset_point", "group"])

# %%
df.loc[len(df) - 5 : len(df), ["joined_at", "join_delta", "consecutive_joins"]]

# %%
df.plot(x="joined_at", y="consecutive_joins")

# %%
