import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load .env from the current working directory (project root)
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

intents = discord.Intents.default()
intents.message_content = True
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
            await bot.start(TOKEN)

    asyncio.run(main())
