import os
import asyncio
import asyncpg
import aiohttp
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
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

    print("Bot ready (FULL PUBLIC VERSION)")

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

# ================= HELP =================
@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="📖 Help Menu", color=discord.Color.blurple())

    embed.add_field(
        name="Moderation",
        value="`?kick @user`\n`?ban @user`\n`?role @user @role`\n`?purge amount`\n`?clear`",
        inline=False
    )

    embed.add_field(
        name="Server Setup",
        value="`!setup welcome`\n`!setup verify`\n`!setup verifiedrole`\n`!setup logs`\n`!setup ticket`\n`!antinuke`",
        inline=False
    )

    embed.add_field(
        name="Minecraft",
        value="`$sudo info <username>`\n`$sudo head <username>`",
        inline=False
    )

    await ctx.send(embed=embed)

# ================= ROLE TOGGLE =================
@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, member: discord.Member, role: discord.Role):

    if role >= ctx.guild.me.top_role:
        return await ctx.send(embed=error("Error","I cannot manage that role."))

    embed = discord.Embed(color=discord.Color.blurple())
    embed.timestamp = datetime.utcnow()
    embed.set_footer(text=f"Moderator: {ctx.author}", icon_url=ctx.author.display_avatar.url)

    if role in member.roles:
        await member.remove_roles(role)
        embed.title = "Role Removed"
        embed.color = discord.Color.red()
    else:
        await member.add_roles(role)
        embed.title = "Role Added"
        embed.color = discord.Color.green()

    embed.description = f"**Member:** {member.mention}\n**Role:** {role.mention}"
    await ctx.send(embed=embed)

# ================= SUDO GROUP =================
@bot.group(name="sudo")
async def sudo(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send(embed=info("Sudo Commands","Subcommands: info, head"))

@sudo.command(name="info")
@commands.has_permissions(administrator=True)
async def sudo_info(ctx, mc_username: str):

    await ctx.send(embed=info("Fetching","Getting Minecraft data..."))

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{mc_username}") as response:

            if response.status != 200:
                return await ctx.send(embed=error("Error","Minecraft account not found."))

            data = await response.json()
            uuid_raw = data.get("id")

            uuid = f"{uuid_raw[:8]}-{uuid_raw[8:12]}-{uuid_raw[12:16]}-{uuid_raw[16:20]}-{uuid_raw[20:]}"

    embed = discord.Embed(title="🎮 Minecraft Account Info", color=discord.Color.green())
    embed.add_field(name="Username", value=mc_username, inline=False)
    embed.add_field(name="UUID", value=uuid, inline=False)
    embed.set_thumbnail(url=f"https://mc-heads.net/head/{uuid}")
    embed.set_image(url=f"https://mc-heads.net/body/{uuid}")

    await ctx.send(embed=embed)

@sudo.command(name="head")
@commands.has_permissions(administrator=True)
async def sudo_head(ctx, mc_username: str):

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{mc_username}") as response:

            if response.status != 200:
                return await ctx.send(embed=error("Error","Minecraft account not found."))

            data = await response.json()
            uuid_raw = data.get("id")
            uuid = f"{uuid_raw[:8]}-{uuid_raw[8:12]}-{uuid_raw[12:16]}-{uuid_raw[16:20]}-{uuid_raw[20:]}"

    embed = discord.Embed(title=f"🧠 {mc_username}'s Head", color=discord.Color.blue())
    embed.set_image(url=f"https://mc-heads.net/head/{uuid}")
    await ctx.send(embed=embed)

# ================= VERIFY =================
class VerifyView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction, button):
        settings = await get_settings(interaction.guild.id)
        role = interaction.guild.get_role(settings["verified_role"])
        await interaction.user.add_roles(role)
        await interaction.response.send_message(embed=success("Verified","Access granted."),ephemeral=True)

# ================= START =================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=error("Permission Denied","You lack permission."))
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await ctx.send(embed=error("Error",str(error)))

bot.run(TOKEN)
