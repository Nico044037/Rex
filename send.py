import os
import asyncio
import asyncpg
import aiohttp
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput
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

    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(CloseView())

    print("Bot ready (AUTO VERIFY VERSION)")

async def get_settings(guild_id):
    row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    if not row:
        await db.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", guild_id)
        row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    return row

async def update_setting(guild_id, column, value):
    await db.execute(f"UPDATE guild_settings SET {column}=$1 WHERE guild_id=$2", value, guild_id)

# ================= AUTO VERIFY PANEL =================
async def try_send_verify_panel(guild):
    settings = await get_settings(guild.id)

    if settings["verify_channel"] and settings["verified_role"]:
        channel = guild.get_channel(settings["verify_channel"])
        if channel:
            await channel.send(
                embed=info("Verification Required",
                           "Click the button below to verify and gain access."),
                view=VerifyView()
            )

# ================= RULES =================
def rules_embed():
    e = discord.Embed(
        title="📜 Server Rules",
        description="By staying you agree to follow these rules.",
        color=discord.Color.red()
    )
    e.add_field(name="Respect", value="No harassment.", inline=False)
    e.add_field(name="No Spam", value="No flooding.", inline=False)
    e.add_field(name="No NSFW", value="Keep content safe.", inline=False)
    e.add_field(name="No Advertising", value="No promotion.", inline=False)
    return e

# ================= VERIFY SYSTEM =================
class VerifyView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction, button):
        settings = await get_settings(interaction.guild.id)
        role = interaction.guild.get_role(settings["verified_role"])
        if not role:
            return await interaction.response.send_message(embed=error("Error","Role not found."),ephemeral=True)

        await interaction.user.add_roles(role)
        await interaction.response.send_message(embed=success("Verified","Access granted."),ephemeral=True)

# ================= TICKETS =================
async def create_transcript(channel):
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
    data = "\n".join(messages)
    return discord.File(io.BytesIO(data.encode()), filename=f"{channel.name}.txt")

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
            return await interaction.response.send_message(embed=error("Error","Ticket system not set."),ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category
        )

        ticket_owners[channel.id] = interaction.user.id

        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True)

        await channel.send(embed=info("Ticket Opened","Describe your issue."),view=CloseView())
        await interaction.response.send_message(embed=success("Ticket Created",channel.mention),ephemeral=True)

# ================= LOG FUNCTION =================
async def log(guild, embed, file=None):
    settings = await get_settings(guild.id)
    if settings["logs_channel"]:
        ch = guild.get_channel(settings["logs_channel"])
        if ch:
            await ch.send(embed=embed, file=file)

# ================= SETUP =================
@bot.group()
async def setup(ctx): pass

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

# ================= ERROR HANDLER =================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=error("Permission Denied","You lack permission."))
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await ctx.send(embed=error("Error",str(error)))

bot.run(TOKEN)
