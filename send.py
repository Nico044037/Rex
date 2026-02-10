import os
import json
import discord
from discord.ext import commands
from discord import app_commands

# ================= BASIC CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1452967364470505565
DATA_FILE = "data.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=["!", "?"],
    intents=intents,
    help_command=None
)

# ================= PERSISTENT STORAGE =================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"welcome_channel": None, "autoroles": []}, f)

with open(DATA_FILE, "r") as f:
    data = json.load(f)

welcome_channel_id: int | None = data["welcome_channel"]
autoroles: set[int] = set(data["autoroles"])

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(
            {
                "welcome_channel": welcome_channel_id,
                "autoroles": list(autoroles)
            },
            f,
            indent=4
        )

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
            "🤝 Be respectful\n"
            "🚫 No spam\n"
            "🔞 No NSFW\n"
            "📢 No ads\n"
            "⚠️ No illegal content\n"
            "👮 Staff decisions are final"
        ),
        inline=False
    )
    return embed

# ================= READY =================
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"✅ Logged in as {bot.user}")
    print("✅ Slash commands synced to guild")

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
        channel = member.guild.get_channel(welcome_channel_id)
        if channel:
            await channel.send(f"👋 Welcome {member.mention}!")

# ================= SETUP =================
@bot.tree.command(name="setup", description="Set welcome channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_setup(interaction: discord.Interaction, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    save_data()
    await interaction.response.send_message(
        f"✅ Welcome channel set to {channel.mention}",
        ephemeral=True
    )

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setup(ctx, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    save_data()
    await ctx.send(f"✅ Welcome channel set to {channel.mention}")

# ================= SEND RULES =================
@bot.tree.command(name="send", description="Send rules")
async def slash_send(interaction: discord.Interaction):
    await interaction.response.send_message(embed=rules_embed())

@bot.command()
async def send(ctx):
    await ctx.send(embed=rules_embed())

# ================= HELP =================
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="📖 Help", color=discord.Color.blurple())
    embed.add_field(
        name="Setup",
        value="`/setup #channel`\n`!setup #channel`\n`?setup #channel`",
        inline=False
    )
    embed.add_field(
        name="Autorole",
        value="`?autorole add @role`\n`?autorole remove @role`",
        inline=False
    )
    embed.add_field(
        name="Moderation",
        value="`?kick @user`\n`?role add/remove @user @role`",
        inline=False
    )
    await ctx.send(embed=embed)

# ================= MODERATION =================
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 Kicked {member.mention}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, action: str, member: discord.Member, role: discord.Role):
    if action == "add":
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.mention}")
    elif action == "remove":
        await member.remove_roles(role)
        await ctx.send(f"❌ Removed {role.mention}")

# ================= AUTOROLE =================
@bot.command()
@commands.has_permissions(manage_roles=True)
async def autorole(ctx, action: str, role: discord.Role):
    if action == "add":
        autoroles.add(role.id)
        save_data()
        await ctx.send(f"✅ {role.mention} added to autoroles")
    elif action == "remove":
        autoroles.discard(role.id)
        save_data()
        await ctx.send(f"❌ {role.mention} removed from autoroles")
    else:
        await ctx.send("❌ Use: `?autorole add @role` or `?autorole remove @role`")

# ================= START =================
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(TOKEN)
