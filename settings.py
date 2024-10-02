import pathlib
import os
import logging
from logging.config import dictConfig
from dotenv import load_dotenv
import discord
import json

load_dotenv()

DISCORD_API_TOKEN = os.getenv("TOKEN")

BASE_DIR = pathlib.Path(__file__).parent

CMDS_DIR = BASE_DIR / "cmds"
COGS_DIR = BASE_DIR / "cogs"

GUILDS_ID = discord.Object(id=int(os.getenv("GUILD")))
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

PLAYLISTS_PATH = BASE_DIR / "playlists.json"

def load_playlists():
    if os.path.exists(PLAYLISTS_PATH):
        with open("playlists.json", 'r') as f:
            playlists = json.load(f)
        return playlists 

def save_playlists(playlists):
    with open("playlists.json", 'w') as f:
        json.dump(playlists, f, indent=4)

playlists = load_playlists()

LOGGING_CONFIG = {
    "version": 1,
    "disabled_existing_Loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)-10s - %(asctime)s - %(module)-15s : %(message)s"
        },
        "standard": {
            "format": "%(levelname)-10s - %(name)-15s : %(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard"
        },
        "console2": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "standard"
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/infos.log",
            "mode": "w",
            "formatter": "verbose"
        }
    },
    "Loggers": {
        "bot": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False
        },
        "discord": {
            "handlers": ["console2", "file"],
            "level": "INFO",
            "propagate": False
        }
    } 
}

dictConfig(LOGGING_CONFIG)
