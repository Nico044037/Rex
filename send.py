import os
import json
import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# ================= BASIC CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN")

# Change this OR set GUILD_ID in Railway
MAIN_GUILD_ID = int(os.getenv("GUILD_ID", "1452967364470505565"))

DATA_FILE = "data.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=["!", "?"],
    intents=intents,
    help_command=None
)

# ================= STORAGE =================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"welcome_channel": None, "autoroles": []}, f)

with open(DATA_FILE, "r") as f:
    data = json.load(f)

welcome_channel_id: int | None = data.get("welcome_channel")
autoroles: set[int] = set(data.get("autoroles", []))

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
            "🚫 No spamming\n"
            "🔞 No NSFW\n"
            "📢 No advertising\n"
            "⚠️ No illegal content\n"
            "👮 Staff decisions are final"
        ),
        inline=False
    )

    embed.set_footer(text="⚠️ Breaking rules may result in punishment")
    return embed

# ================= READY =================
@bot.event
async def on_ready():
    guild = discord.Object(id=MAIN_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"✅ Logged in as {bot.user}")
    print(f"✅ Slash commands synced to guild {MAIN_GUILD_ID}")

# ================= MEMBER JOIN =================
@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != MAIN_GUILD_ID:
        return

    # small delay so Discord fully registers the member
    await asyncio.sleep(2)

    # ===== DM RULES =====
    try:
        await member.send(embed=rules_embed())
        print(f"📨 DM sent to {member}")
    except discord.Forbidden:
        print(f"❌ DM FAILED (DMs closed): {member}")
    except Exception as e:
        print(f"❌ DM ERROR for {member}: {e}")

    # ===== AUTOROLES =====
    for role_id in autoroles:
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                print(f"❌ Missing permission to add role {role.name}")

    # ===== WELCOME MESSAGE =====
    if welcome_channel_id:
        channel = member.guild.get_channel(welcome_channel_id)
        if channel:
            await channel.send(
                f"👋 Welcome {member.mention}!\n"
                f"📜 Check your DMs for the rules ❤️"
            )

# ================= SETUP =================
@bot.tree.command(name="setup", description="Set welcome channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_setup(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.guild_id != MAIN_GUILD_ID:
        return

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
    if ctx.guild.id != MAIN_GUILD_ID:
        return

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
    if ctx.guild.id != MAIN_GUILD_ID:
        return

    if action.lower() == "add":
        autoroles.add(role.id)
        save_data()
        await ctx.send(f"✅ Added {role.mention} to autoroles")
    elif action.lower() == "remove":
        autoroles.discard(role.id)
        save_data()
        await ctx.send(f"❌ Removed {role.mention} from autoroles")
    else:
        await ctx.send("❌ Use: `?autorole add @role` or `?autorole remove @role`")

# ================= START =================
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set")

bot.run(TOKEN)
