import os
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1452967364470505565

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=["!", "?"], intents=intents)

# ================= CONFIG =================
welcome_channel_id: int | None = None
autoroles: set[int] = set()  # stores role IDs

# ================= EMBEDS =================
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

# ================= READY =================
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print(f"✅ Logged in as {bot.user}")

# ================= MEMBER JOIN =================
@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != GUILD_ID:
        return

    # DM rules
    try:
        await member.send(embed=rules_embed())
    except discord.Forbidden:
        pass

    # Autoroles
    for role_id in autoroles:
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                pass

    # Welcome message
    if welcome_channel_id:
        channel = bot.get_channel(welcome_channel_id)
        if channel:
            await channel.send(
                f"👋 Welcome {member.mention}!\n"
                f"📜 Check your DMs for the rules ❤️"
            )

# ================= SETUP =================
@bot.tree.command(name="setup", description="Set welcome channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_setup(interaction: discord.Interaction, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    await interaction.response.send_message(
        f"✅ Welcome channel set to {channel.mention}",
        ephemeral=True
    )

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setup(ctx, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    await ctx.send(f"✅ Welcome channel set to {channel.mention}")

# ================= SEND RULES =================
@bot.tree.command(name="send", description="Send rules")
async def slash_send(interaction: discord.Interaction):
    await interaction.response.send_message(embed=rules_embed())

@bot.command()
async def send(ctx):
    await ctx.send(embed=rules_embed())

# ================= HELP =================
@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="📖 Help Menu",
        description="Dyno-style commands",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="⚙️ Setup",
        value="`/setup #channel`\n`!setup #channel`\n`?setup #channel`",
        inline=False
    )

    embed.add_field(
        name="🏷️ Autorole",
        value="`?autorole add @role`\n`?autorole remove @role`",
        inline=False
    )

    embed.add_field(
        name="📜 Rules",
        value="`/send`\n`!send`\n`?send`",
        inline=False
    )

    embed.add_field(
        name="🔨 Moderation",
        value="`?kick @user [reason]`\n`?role add/remove @user @role`",
        inline=False
    )

    await ctx.send(embed=embed)

# ================= MODERATION =================
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 Kicked {member.mention}\n📄 Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I can't kick this user.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, action: str, member: discord.Member, role: discord.Role):
    if action.lower() == "add":
        await member.add_roles(role)
        await ctx.send(f"🏷️ Added {role.mention} to {member.mention}")
    elif action.lower() == "remove":
        await member.remove_roles(role)
        await ctx.send(f"🏷️ Removed {role.mention} from {member.mention}")
    else:
        await ctx.send("❌ Use: `?role add @user @role` or `?role remove @user @role`")

# ================= AUTOROLE =================
@bot.command()
@commands.has_permissions(manage_roles=True)
async def autorole(ctx, action: str, role: discord.Role):
    if action.lower() == "add":
        autoroles.add(role.id)
        await ctx.send(f"✅ {role.mention} added to autoroles")
    elif action.lower() == "remove":
        autoroles.discard(role.id)
        await ctx.send(f"❌ {role.mention} removed from autoroles")
    else:
        await ctx.send("❌ Use: `?autorole add @role` or `?autorole remove @role`")

# ================= START =================
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set")

bot.run(TOKEN)
