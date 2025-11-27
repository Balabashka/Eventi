import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()  # will load from .env in project root if you run from there
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


async def setup_bot():
    await bot.load_extension("cogs.events")


if __name__ == "__main__":
    import asyncio

    async def main():
        async with bot:
            await setup_bot()
            await bot.start(token)

    asyncio.run(main())
