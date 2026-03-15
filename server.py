import os
import re
import datetime
import traceback
import asyncio
import random
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from keep_alive import keep_alive
import aiosqlite

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True

BANNED_WORDS = ["badword1", "badword2"]

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")
        
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        await interaction.response.send_message(f"Ticket created: {ticket_channel.mention}", ephemeral=True)
        await ticket_channel.send(f"Welcome {interaction.user.mention}. Please explain your issue. Support will be with you shortly. Use !close to end this ticket.")

class ReactionRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Gamer Role", style=discord.ButtonStyle.secondary, custom_id="role_gamer")
    async def gamer_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Gamer")
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message("Removed Gamer role.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("Added Gamer role.", ephemeral=True)

    @discord.ui.button(label="Artist Role", style=discord.ButtonStyle.secondary, custom_id="role_artist")
    async def artist_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Artist")
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message("Removed Artist role.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("Added Artist role.", ephemeral=True)

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Here", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        verified_role = discord.utils.get(interaction.guild.roles, name="Verified")
        unverified_role = discord.utils.get(interaction.guild.roles, name="Unverified")
        if verified_role:
            await interaction.user.add_roles(verified_role)
            if unverified_role in interaction.user.roles:
                await interaction.user.remove_roles(unverified_role)
            await interaction.response.send_message("You have been verified. Welcome!", ephemeral=True)
        else:
            await interaction.response.send_message("The Verified role does not exist. Please contact an admin.", ephemeral=True)

class SynqBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(VerificationView())
        self.add_view(TicketView())
        self.add_view(ReactionRoleView())
        await self.setup_db()

    async def setup_db(self):
        async with aiosqlite.connect('bot_data.db') as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            await db.execute('''CREATE TABLE IF NOT EXISTS leveling (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )''')
            await db.commit()

bot = SynqBot()

recent_joins = {}

async def get_warning_count(guild_id, user_id):
    async with aiosqlite.connect('bot_data.db') as db:
        async with db.execute('SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def add_warning(guild_id, user_id, mod_id, reason):
    async with aiosqlite.connect('bot_data.db') as db:
        await db.execute('INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?, ?, ?, ?)', (user_id, guild_id, mod_id, reason))
        await db.commit()
    
    guild = bot.get_guild(guild_id)
    if not guild: return
    member = guild.get_member(user_id)
    if not member: return

    count = await get_warning_count(guild_id, user_id)
    log_channel = discord.utils.get(guild.channels, name="mod-logs")
    
    action_taken = "Warned"
    
    if count == 2:
        try:
            duration = datetime.timedelta(hours=1)
            await member.timeout(duration, reason="Escalation: 2nd Warning")
            action_taken = "Muted for 1 hour"
        except:
            pass
    elif count == 3:
        try:
            await member.kick(reason="Escalation: 3rd Warning")
            action_taken = "Kicked"
        except:
            pass
    elif count >= 4:
        try:
            await member.ban(reason="Escalation: 4th Warning")
            action_taken = "Banned"
        except:
            pass

    if log_channel:
        await log_channel.send(f"[Auto-Punish] {member.name} ({member.id}) reached warning {count}. Action: {action_taken}. Reason: {reason}.")

    # Banned words filter
    for word in BANNED_WORDS:
        if word in message.content.lower():
            if not message.author.guild_permissions.manage_messages:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, your message contained a blacklisted word and was removed.")
                return

    # Leveling System
    await update_xp(message.guild.id, message.author.id, message.channel)

    await bot.process_commands(message)

async def update_xp(guild_id, user_id, channel):
    async with aiosqlite.connect('bot_data.db') as db:
        async with db.execute('SELECT xp, level FROM leveling WHERE guild_id = ? AND user_id = ?', (guild_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute('INSERT INTO leveling (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)', (guild_id, user_id, 5, 0))
                await db.commit()
                return
            
            xp, level = row
            new_xp = xp + random.randint(5, 15)
            next_level_xp = (level + 1) * 100

            if new_xp >= next_level_xp:
                new_level = level + 1
                await db.execute('UPDATE leveling SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?', (new_xp, new_level, guild_id, user_id))
                await channel.send(f"Congratulations <@{user_id}>, you reached level {new_level}!")
            else:
                await db.execute('UPDATE leveling SET xp = ? WHERE guild_id = ? AND user_id = ?', (new_xp, guild_id, user_id))
            await db.commit()

@bot.event
async def on_member_join(member):
    now = datetime.datetime.now()
    guild_id = member.guild.id
    if guild_id not in recent_joins:
        recent_joins[guild_id] = []
    
    recent_joins[guild_id] = [t for t in recent_joins[guild_id] if (now - t).total_seconds() < 60]
    recent_joins[guild_id].append(now)

    log_channel = discord.utils.get(member.guild.channels, name="mod-logs")

    if len(recent_joins[guild_id]) > 10:
        if log_channel:
            await log_channel.send(f"[Raid Protection] Mass join detected! Quarantining new user {member.name}.")
        quarantine_role = discord.utils.get(member.guild.roles, name="Quarantined")
        if quarantine_role:
            await member.add_roles(quarantine_role)
            return

    unverified_role = discord.utils.get(member.guild.roles, name="Unverified")
    if unverified_role:
        await member.add_roles(unverified_role)
    
    channel = discord.utils.get(member.guild.channels, name="👋-introductions")
    
    if channel:
        welcome_1_liner = f"Welcome to the community, {member.mention}! Glad to have you here."
        await channel.send(welcome_1_liner)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_channel = discord.utils.get(message.guild.channels, name="mod-logs")
    if log_channel:
        await log_channel.send(f"[Message Deleted] Author: {message.author.name} | Channel: {message.channel.name}\\nContent: {message.content}")

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    log_channel = discord.utils.get(before.guild.channels, name="mod-logs")
    if log_channel:
        await log_channel.send(f"[Message Edited] Author: {before.author.name} | Channel: {before.channel.name}\\nBefore: {before.content}\\nAfter: {after.content}")

@bot.event
async def on_member_ban(guild, user):
    log_channel = discord.utils.get(guild.channels, name="mod-logs")
    if log_channel:
        await log_channel.send(f"[Member Banned] {user.name} ({user.id})")

@bot.event
async def on_member_unban(guild, user):
    log_channel = discord.utils.get(guild.channels, name="mod-logs")
    if log_channel:
        await log_channel.send(f"[Member Unbanned] {user.name} ({user.id})")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    if not ping_channel.is_running():
        ping_channel.start()

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {len(deleted)-1} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"Member {member.name} has been kicked. Reason: {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f"Member {member.name} has been banned. Reason: {reason}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason=None):
    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f"Member {member.name} has been timed out for {minutes} minutes. Reason: {reason}")

def get_rules_embed():
    embed = discord.Embed(
        title="Server Rules",
        description="Welcome to our community! Keep it chill, keep it cool.",
        color=discord.Color.blue()
    )
    embed.add_field(name="1. Be Respectful", value="Treat everyone with respect. No harassment, hate speech, or personal attacks. We are all here to vibe and grow.", inline=False)
    embed.add_field(name="2. No Spam", value="Avoid excessive messages, self-promotion, or link dumping. Quality over quantity.", inline=False)
    embed.add_field(name="3. Stay On Topic", value="Use the right channels for the right conversations. Keep discussions relevant.", inline=False)
    embed.add_field(name="4. No NSFW Content", value="Keep it clean. No explicit, offensive, or inappropriate content.", inline=False)
    embed.add_field(name="5. Help, Dont Gatekeep", value="Everyone starts somewhere. Be supportive of beginners and share knowledge freely.", inline=False)
    embed.add_field(name="6. No Piracy", value="Dont share or request pirated software, courses, or copyrighted material.", inline=False)
    embed.add_field(name="7. Respect Privacy", value="Dont share others personal information. What is shared here stays here.", inline=False)
    embed.add_field(name="8. Verified Links Only", value="Only admin-whitelisted domains are allowed. Videos are always welcome! If you want a site added, ask a mod.", inline=False)
    embed.add_field(name="9. Use Common Sense", value="If it feels wrong, it probably is. When in doubt, ask a mod.", inline=False)
    embed.set_footer(text="Breaking rules may result in warnings, mutes, or bans. Let's keep this a great place to code!")
    return embed

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    guild = ctx.guild
    await ctx.send("Starting server auto-setup...")
    
    # 1. Ensure Categories exist
    info_cat = discord.utils.get(guild.categories, name="Information")
    if not info_cat:
        info_cat = await guild.create_category("Information")
        
    mod_cat = discord.utils.get(guild.categories, name="Moderation")
    if not mod_cat:
        mod_cat = await guild.create_category("Moderation")

    # 2. Setup Moderation Logs (#mod-logs)
    admin_roles = [r for r in guild.roles if r.permissions.administrator or r.permissions.manage_guild or r.permissions.manage_messages]
    mod_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    for role in admin_roles:
        mod_overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
    mod_logs = discord.utils.get(guild.channels, name="mod-logs")
    if not mod_logs:
        mod_logs = await guild.create_text_channel("mod-logs", category=mod_cat, overwrites=mod_overwrites)
        await mod_logs.send("[System] Moderation log channel created and secured.")
    else:
        await mod_logs.edit(category=mod_cat, overwrites=mod_overwrites)
        await mod_logs.send("[System] Moderation log permissions auto-corrected.")

    # 3. Setup Rules Channel (#rules)
    read_only_overwrites = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    rules_channel = discord.utils.get(guild.channels, name="rules")
    if not rules_channel:
        rules_channel = await guild.create_text_channel("rules", category=info_cat, overwrites=read_only_overwrites)
        await rules_channel.send(embed=get_rules_embed())
    else:
        await rules_channel.edit(category=info_cat, overwrites=read_only_overwrites)
        # Check if empty, maybe send rules
        hist = [m async for m in rules_channel.history(limit=5)]
        if not hist:
            await rules_channel.send(embed=get_rules_embed())

    # 4. Setup Roles Channel (#roles)
    roles_channel = discord.utils.get(guild.channels, name="roles")
    if not roles_channel:
        roles_channel = await guild.create_text_channel("roles", category=info_cat, overwrites=read_only_overwrites)
        await roles_channel.send("Click a button below to pick your roles.", view=ReactionRoleView())
    else:
        await roles_channel.edit(category=info_cat, overwrites=read_only_overwrites)

    # 5. Setup Introductions (#👋-introductions)
    intro_channel = discord.utils.get(guild.channels, name="👋-introductions")
    if not intro_channel:
        intro_channel = await guild.create_text_channel("👋-introductions", category=info_cat)
    else:
        await intro_channel.edit(category=info_cat)

    await ctx.send(f"Setup complete! Channels are configured in {info_cat.name} and {mod_cat.name}.")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    await ctx.send("Click the button below to open a support ticket.", view=TicketView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    await ctx.send("Click a button below to pick your roles.", view=ReactionRoleView())

@bot.command()
async def close(ctx):
    if "ticket-" in ctx.channel.name:
        await ctx.send("Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await ctx.channel.delete()

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    async with aiosqlite.connect('bot_data.db') as db:
        async with db.execute('SELECT xp, level FROM leveling WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, member.id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send(f"{member.name} has no rank yet.")
                return
            xp, level = row
            await ctx.send(f"Rank for {member.name}: Level {level} | XP: {xp}")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [role.name for role in member.roles if role.name != "@everyone"]
    await ctx.send(f"User: {member.name}\\nID: {member.id}\\nJoined: {member.joined_at.strftime('%Y-%m-%d')}\\nRoles: {', '.join(roles) if roles else 'None'}")

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    await ctx.send(f"Server: {guild.name}\\nID: {guild.id}\\nMembers: {guild.member_count}\\nCreated: {guild.created_at.strftime('%Y-%m-%d')}")

@bot.command()
async def rules(ctx):
    await ctx.send(embed=get_rules_embed())

@bot.event
async def on_guild_channel_create(channel):
    log_channel = discord.utils.get(channel.guild.channels, name="mod-logs")
    if log_channel:
        await log_channel.send(f"[Channel Created] Name: {channel.name} | Type: {channel.type}")

@bot.event
async def on_guild_channel_delete(channel):
    log_channel = discord.utils.get(channel.guild.channels, name="mod-logs")
    if log_channel:
        await log_channel.send(f"[Channel Deleted] Name: {channel.name}")

@bot.event
async def on_member_update(before, after):
    log_channel = discord.utils.get(before.guild.channels, name="mod-logs")
    if not log_channel: return
    if before.nick != after.nick:
        await log_channel.send(f"[Nickname Change] User: {after.name} | Before: {before.nick} | After: {after.nick}")
    if before.roles != after.roles:
        added = [r.name for r in after.roles if r not in before.roles]
        removed = [r.name for r in before.roles if r not in after.roles]
        if added: await log_channel.send(f"[Roles Update] User: {after.name} | Added: {', '.join(added)}")
        if removed: await log_channel.send(f"[Roles Update] User: {after.name} | Removed: {', '.join(removed)}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to do that.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: {error.param.name}")
    else:
        traceback.print_exception(type(error), error, error.__traceback__)

if TOKEN:
    keep_alive()
    bot.run(TOKEN)
else:
    print("Error: No token found. Check .env file!")