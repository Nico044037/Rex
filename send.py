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

    print("Bot ready (FULL VERSION)")

async def get_settings(guild_id):
    row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    if not row:
        await db.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", guild_id)
        row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    return row

async def update_setting(guild_id, column, value):
    await db.execute(f"UPDATE guild_settings SET {column}=$1 WHERE guild_id=$2", value, guild_id)

# ================= LOG FUNCTION =================
async def log(guild, embed, file=None):
    settings = await get_settings(guild.id)
    if settings["logs_channel"]:
        ch = guild.get_channel(settings["logs_channel"])
        if ch:
            await ch.send(embed=embed, file=file)

# ================= RULES =================
def rules_embed():
    e = discord.Embed(
        title="📜 Server Rules",
        description="By staying in this server you agree to follow these rules.",
        color=discord.Color.red()
    )
    e.add_field(name="Respect", value="No harassment or hate.", inline=False)
    e.add_field(name="No Spam", value="No flooding channels.", inline=False)
    e.add_field(name="No NSFW", value="Keep content safe.", inline=False)
    e.add_field(name="No Advertising", value="No promotion.", inline=False)
    e.set_footer(text="Breaking rules may result in punishment.")
    return e

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

# ================= VERIFY =================
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
        await log(interaction.guild, log_embed("User Verified", interaction.user.mention))

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

    await log(member.guild, log_embed("Member Joined", member.mention))

@bot.event
async def on_member_remove(member):
    await log(member.guild, log_embed("Member Left", str(member)))

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    await log(message.guild,
              log_embed("Message Deleted",
                        f"{message.author} in {message.channel.mention}\n{message.content}"))

# ================= SETUP COMMANDS =================
@bot.group()
async def setup(ctx): pass

@setup.command()
async def welcome(ctx, channel: discord.TextChannel):
    await update_setting(ctx.guild.id, "welcome_channel", channel.id)
    await ctx.send(embed=success("Welcome Channel Set", channel.mention))

@setup.command()
async def logs(ctx, channel: discord.TextChannel):
    await update_setting(ctx.guild.id, "logs_channel", channel.id)
    await ctx.send(embed=success("Logs Channel Set", channel.mention))

@setup.command()
async def rules(ctx, channel: discord.TextChannel):
    await update_setting(ctx.guild.id, "rules_channel", channel.id)
    await channel.send(embed=rules_embed())
    await ctx.send(embed=success("Rules Sent", channel.mention))

@setup.command()
async def verify(ctx, channel: discord.TextChannel):
    await update_setting(ctx.guild.id,"verify_channel",channel.id)
    await ctx.send(embed=success("Verify Channel Set",channel.mention))
    await try_send_verify_panel(ctx.guild)

@setup.command()
async def verifiedrole(ctx, role: discord.Role):
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
