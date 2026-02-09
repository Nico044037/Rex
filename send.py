
import os
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1402852587325358232

# ======================
# INTENTS
# ======================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=["!", "?"], intents=intents)

# ======================
# HELPERS
# ======================
def get_log_channel(guild: discord.Guild):
    return discord.utils.get(guild.text_channels, name="log")

# ======================
# RULES EMBED
# ======================
def rules_embed():
    embed = discord.Embed(
        title="📜 Welcome to the Server!",
        description="Please read the rules carefully ❤️",
        color=discord.Color.red()
    )

    embed.add_field(
        name="💬 Discord Rules",
        value=(
            "🤝 Be respectful to everyone\n"
            "🚫 No spamming or excessive tagging\n"
            "🔞 No NSFW or disturbing content\n"
            "📢 No advertising without staff permission\n"
            "⚠️ No illegal activity\n"
            "🔐 Do not share personal information\n"
            "🧭 Use the correct channels\n"
            "👮 Staff decisions are final"
        ),
        inline=False
    )

    embed.set_footer(text="⚠️ Breaking rules may result in punishment")
    return embed

# ======================
# READY
# ======================
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print(f"✅ Logged in as {bot.user}")

# ======================
# MEMBER JOIN
# ======================
@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != GUILD_ID:
        return

    try:
        await member.send(embed=rules_embed())
    except discord.Forbidden:
        pass

# ======================
# SEND RULES
# ======================
@bot.tree.command(name="send", description="Send rules")
async def slash_send(interaction: discord.Interaction):
    await interaction.response.send_message(embed=rules_embed())

@bot.command()
async def send(ctx):
    await ctx.send(embed=rules_embed())

# ==================================================
# 🔨 MODERATION COMMANDS
# ==================================================

# ===== KICK =====
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 **Kicked** {member.mention}\n📄 Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don’t have permission to kick this user.")

# ===== ROLE ADD / REMOVE =====
@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, action: str, member: discord.Member, role: discord.Role):
    if ctx.guild.id != GUILD_ID:
        return

    try:
        if action.lower() == "add":
            await member.add_roles(role)
            await ctx.send(f"🏷️ Added {role.mention} to {member.mention}")

        elif action.lower() == "remove":
            await member.remove_roles(role)
            await ctx.send(f"🏷️ Removed {role.mention} from {member.mention}")

        else:
            await ctx.send("❌ Usage: `?role add @user @role` or `?role remove @user @role`")

    except discord.Forbidden:
        await ctx.send("❌ I can’t manage that role (role hierarchy issue).")

# ==================================================
# 📋 LOGGING EVENTS
# ==================================================

# ===== ROLE CHANGE LOG =====
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.guild.id != GUILD_ID:
        return

    log_channel = get_log_channel(after.guild)
    if not log_channel:
        return

    before_roles = set(before.roles)
    after_roles = set(after.roles)

    added_roles = after_roles - before_roles
    removed_roles = before_roles - after_roles

    for role in added_roles:
        await log_channel.send(
            f"➕ **Role Added**\n"
            f"👤 User: {after.mention}\n"
            f"🏷️ Role: {role.mention}"
        )

    for role in removed_roles:
        await log_channel.send(
            f"➖ **Role Removed**\n"
            f"👤 User: {after.mention}\n"
            f"🏷️ Role: {role.mention}"
        )

# ===== MESSAGE DELETE LOG =====
@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.guild.id != GUILD_ID:
        return

    if message.author.bot:
        return

    log_channel = get_log_channel(message.guild)
    if not log_channel:
        return

    await log_channel.send(
        f"🗑️ **Message Deleted**\n"
        f"👤 Author: {message.author.mention}\n"
        f"📍 Channel: {message.channel.mention}\n"
        f"💬 Content:\n```{message.content or 'No text content'}```"
    )

# ======================
# START BOT
# ======================
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set")


bot.run(TOKEN)
