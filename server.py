import os
import discord
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_member_join(member):
    
    channel = discord.utils.get(member.guild.channels, name="👋 | introductions")
    
    if channel:
        welcome_1_liner = f"Welcome to the community, {member.mention}! Glad to have you here. "
        
        template = (
            "**Please introduce yourself so we can get to know you:**\n"
            "```\n"
            "Name: \n"
            "Role: \n"
            "What I'm building: \n"
            "```"
        )
        
        await channel.send(f"{welcome_1_liner}\n\n{template}")


@bot.command()
async def ping(ctx):
    await ctx.send(f"| Pong! {round(bot.latency * 500)}ms")


if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: No token found. Check .env file!")