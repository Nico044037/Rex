import os
import asyncio
import asyncpg
import aiohttp
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Button
from datetime import datetime
import io

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["!", "?", "$"], intents=intents, help_command=None)

db = None
ticket_owners = {}

# ================= EMBEDS =================
def success(t,d): return discord.Embed(title=f"✅ {t}",description=d,color=discord.Color.green())
def error(t,d): return discord.Embed(title=f"❌ {t}",description=d,color=discord.Color.red())
def info(t,d): return discord.Embed(title=f"ℹ️ {t}",description=d,color=discord.Color.blurple())
def log_embed(t,d): return discord.Embed(title=f"📜 {t}",description=d,color=discord.Color.orange())

# ================= DATABASE =================
@bot.event
async def on_ready():
    global db
    db = await asyncpg.create_pool(DATABASE_URL)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id BIGINT PRIMARY KEY,
        welcome_channel BIGINT,
        verify_channel BIGINT,
        verified_role BIGINT,
        logs_channel BIGINT,
        rules_channel BIGINT,
        ticket_category BIGINT,
        antinuke BOOLEAN DEFAULT FALSE
    );
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS autoroles (
        guild_id BIGINT,
        role_id BIGINT
    );
    """)

    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(CloseView())

    print("Bot ready.")

async def get_settings(guild_id):
    row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    if not row:
        await db.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", guild_id)
        row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    return row

async def update_setting(guild_id, column, value):
    await db.execute(f"UPDATE guild_settings SET {column}=$1 WHERE guild_id=$2", value, guild_id)

# ================= LOG SYSTEM =================
async def log(guild, embed, file=None):
    try:
        settings = await get_settings(guild.id)
        channel_id = settings["logs_channel"]
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed, file=file)
    except Exception as e:
        print("LOG ERROR:", e)

# ================= AUTOROLE =================
async def add_autorole(guild_id, role_id):
    await db.execute("INSERT INTO autoroles (guild_id, role_id) VALUES ($1,$2)", guild_id, role_id)

async def remove_autorole(guild_id, role_id):
    await db.execute("DELETE FROM autoroles WHERE guild_id=$1 AND role_id=$2", guild_id, role_id)

async def get_autoroles(guild_id):
    rows = await db.fetch("SELECT role_id FROM autoroles WHERE guild_id=$1", guild_id)
    return [r["role_id"] for r in rows]

# ================= RULES =================
def rules_embed():
    e = discord.Embed(title="📜 Server Rules",
                      description="By staying you agree to follow these rules.",
                      color=discord.Color.red())
    e.add_field(name="Respect", value="No harassment.", inline=False)
    e.add_field(name="No Spam", value="No flooding.", inline=False)
    e.add_field(name="No NSFW", value="Keep content safe.", inline=False)
    e.add_field(name="No Advertising", value="No promotion.", inline=False)
    return e

# ================= VERIFY =================
async def try_send_verify_panel(guild):
    settings = await get_settings(guild.id)
    if settings["verify_channel"] and settings["verified_role"]:
        ch = guild.get_channel(settings["verify_channel"])
        if ch:
            await ch.send(embed=info("Verification Required",
                                     "Click the button below to verify."),
                          view=VerifyView())

class VerifyView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green)
    async def verify(self, interaction, button):
        settings = await get_settings(interaction.guild.id)
        role = interaction.guild.get_role(settings["verified_role"])
        if not role:
            return await interaction.response.send_message(embed=error("Error","Role missing."),ephemeral=True)

        await interaction.user.add_roles(role)
        await interaction.response.send_message(embed=success("Verified","Access granted."),ephemeral=True)
        await log(interaction.guild, log_embed("User Verified", interaction.user.mention))

# ================= TICKETS =================
async def create_transcript(channel):
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
    return discord.File(io.BytesIO("\n".join(messages).encode()), filename=f"{channel.name}.txt")

class CloseModal(Modal):
    def __init__(self, channel):
        super().__init__(title="Close Ticket")
        self.channel = channel
        self.reason = TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        transcript = await create_transcript(self.channel)
        await log(interaction.guild,
                  log_embed("Ticket Closed",
                            f"{self.channel.name}\nReason: {self.reason.value}"),
                  transcript)
        await self.channel.delete()

class CloseView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction, button):
        owner = ticket_owners.get(interaction.channel.id)
        if interaction.user.id != owner and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(embed=error("Denied","Only owner/admin."),ephemeral=True)
        await interaction.response.send_modal(CloseModal(interaction.channel))

class TicketView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary)
    async def create_ticket(self, interaction, button):
        settings = await get_settings(interaction.guild.id)
        category = interaction.guild.get_channel(settings["ticket_category"])
        if not category:
            return await interaction.response.send_message(embed=error("Ticket not setup","Run !setup ticket"),ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}", category=category)

        ticket_owners[channel.id] = interaction.user.id

        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True)

        await channel.send(embed=info("Ticket Opened","Describe your issue."), view=CloseView())
        await interaction.response.send_message(embed=success("Created",channel.mention),ephemeral=True)

# ================= EVENTS =================
@bot.event
async def on_member_join(member):
    try:
        await member.send(embed=rules_embed())
    except:
        pass

    settings = await get_settings(member.guild.id)

    if settings["welcome_channel"]:
        ch = member.guild.get_channel(settings["welcome_channel"])
        if ch:
            await ch.send(embed=success("New Member Joined", member.mention))

    # Autoroles
    autorole_ids = await get_autoroles(member.guild.id)
    roles = [member.guild.get_role(r) for r in autorole_ids if member.guild.get_role(r)]
    if roles:
        await member.add_roles(*roles, reason="Autorole")

    await log(member.guild, log_embed("Member Joined", member.mention))

# ================= ROLE TOGGLE =================
@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
async def role_toggle(ctx, member: discord.Member, role: discord.Role):
    if role >= ctx.guild.me.top_role:
        return await ctx.send(embed=error("Hierarchy Error","Role higher than bot."))

    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(embed=success("Role Removed", f"{role.mention} removed from {member.mention}"))
    else:
        await member.add_roles(role)
        await ctx.send(embed=success("Role Added", f"{role.mention} added to {member.mention}"))

    await log(ctx.guild, log_embed("Role Toggled", f"{member.mention} → {role.mention}"))

# ================= SETUP =================
@bot.group()
async def setup(ctx): pass

@setup.command()
async def logs(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"logs_channel",channel.id)
    await ctx.send(embed=success("Logs Channel Set",channel.mention))

@setup.command()
async def welcome(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"welcome_channel",channel.id)
    await ctx.send(embed=success("Welcome Channel Set",channel.mention))

@setup.command()
async def rules(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"rules_channel",channel.id)
    await channel.send(embed=rules_embed())
    await ctx.send(embed=success("Rules Sent",channel.mention))

@setup.command()
async def verify(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"verify_channel",channel.id)
    await ctx.send(embed=success("Verify Channel Set",channel.mention))
    await try_send_verify_panel(ctx.guild)

@setup.command()
async def verifiedrole(ctx, role:discord.Role):
    await update_setting(ctx.guild.id,"verified_role",role.id)
    await ctx.send(embed=success("Verified Role Set",role.mention))
    await try_send_verify_panel(ctx.guild)

@setup.command()
async def ticket(ctx):
    category = await ctx.guild.create_category("Tickets")
    await update_setting(ctx.guild.id,"ticket_category",category.id)
    panel = await ctx.guild.create_text_channel("ticket-panel",category=category)
    await panel.send(embed=info("Support Tickets","Click below to create a ticket."),view=TicketView())
    await ctx.send(embed=success("Ticket System Created",panel.mention))

@setup.group()
async def autorole(ctx): pass

@autorole.command(name="add")
async def autorole_add(ctx, role:discord.Role):
    await add_autorole(ctx.guild.id, role.id)
    await ctx.send(embed=success("Autorole Added", role.mention))

@autorole.command(name="remove")
async def autorole_remove(ctx, role:discord.Role):
    await remove_autorole(ctx.guild.id, role.id)
    await ctx.send(embed=success("Autorole Removed", role.mention))

bot.run(TOKEN)
