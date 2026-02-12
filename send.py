import os
import json
import asyncio
import discord
from discord.ext import commands

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
                "verify_channel": None,
                "verified_role": None,
                "logs_channel": None,
                "autoroles": []
            },
            f
        )

with open(DATA_FILE, "r") as f:
    data = json.load(f)

welcome_channel_id: int | None = data.get("welcome_channel")
verify_channel_id: int | None = data.get("verify_channel")
verified_role_id: int | None = data.get("verified_role")
logs_channel_id: int | None = data.get("logs_channel")
autoroles: set[int] = set(data.get("autoroles", []))


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(
            {
                "welcome_channel": welcome_channel_id,
                "verify_channel": verify_channel_id,
                "verified_role": verified_role_id,
                "logs_channel": logs_channel_id,
                "autoroles": list(autoroles)
            },
            f,
            indent=4
        )

# ================= LOG FUNCTION =================
async def send_log(guild: discord.Guild, embed: discord.Embed):
    if not logs_channel_id:
        return
    channel = guild.get_channel(logs_channel_id)
    if channel:
        await channel.send(embed=embed)

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

# ================= VERIFY BUTTON =================
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.green,
        emoji="✅",
        custom_id="verify_button"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not verified_role_id:
            return await interaction.response.send_message(
                "❌ Verified role not set.",
                ephemeral=True
            )

        role = interaction.guild.get_role(verified_role_id)

        if not role:
            return await interaction.response.send_message(
                "❌ Role not found.",
                ephemeral=True
            )

        if role in interaction.user.roles:
            return await interaction.response.send_message(
                "✅ You are already verified.",
                ephemeral=True
            )

        try:
            await interaction.user.add_roles(role, reason="User verified")

            await interaction.response.send_message(
                "🎉 You are now verified!",
                ephemeral=True
            )

            # Log verification
            embed = discord.Embed(
                title="🔐 Member Verified",
                description=f"{interaction.user.mention} has verified.",
                color=discord.Color.blue()
            )
            embed.add_field(name="User ID", value=interaction.user.id)
            await send_log(interaction.guild, embed)

        except:
            await interaction.response.send_message(
                "❌ I cannot assign that role.",
                ephemeral=True
            )

# ================= READY =================
@bot.event
async def on_ready():
    bot.add_view(VerifyView())
    print(f"✅ Logged in as {bot.user}")

# ================= MEMBER JOIN =================
@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != MAIN_GUILD_ID:
        return

    await asyncio.sleep(2)

    # DM Rules
    try:
        await member.send(embed=rules_embed())
    except:
        pass

    # Welcome message
    if welcome_channel_id:
        channel = member.guild.get_channel(welcome_channel_id)
        if channel:
            await channel.send(
                f"👋 Welcome {member.mention}!\n📜 Check your DMs ❤️"
            )

    # Log join
    embed = discord.Embed(
        title="📥 Member Joined",
        description=f"{member.mention} joined the server.",
        color=discord.Color.green()
    )
    embed.add_field(name="User ID", value=member.id)
    embed.set_footer(text=f"Account created: {member.created_at.strftime('%Y-%m-%d')}")
    await send_log(member.guild, embed)

# ================= MEMBER LEAVE =================
@bot.event
async def on_member_remove(member: discord.Member):
    embed = discord.Embed(
        title="📤 Member Left",
        description=f"{member} left the server.",
        color=discord.Color.red()
    )
    embed.add_field(name="User ID", value=member.id)
    await send_log(member.guild, embed)

# ================= SETUP GROUP =================
@bot.group(invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def setup(ctx):
    await ctx.send(
        "Use:\n"
        "`!setup welcome #channel`\n"
        "`!setup verify #channel`\n"
        "`!setup verifiedrole @role`\n"
        "`!setup logs #channel`"
    )

@setup.command()
@commands.has_permissions(manage_guild=True)
async def welcome(ctx, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    save_data()
    await ctx.send(f"✅ Welcome channel set to {channel.mention}")

@setup.command()
@commands.has_permissions(manage_guild=True)
async def verify(ctx, channel: discord.TextChannel):
    global verify_channel_id
    verify_channel_id = channel.id
    save_data()
    await ctx.send(f"✅ Verify channel set to {channel.mention}")

@setup.command()
@commands.has_permissions(manage_roles=True)
async def verifiedrole(ctx, role: discord.Role):
    global verified_role_id

    if role >= ctx.guild.me.top_role:
        return await ctx.send("❌ Role too high.")

    verified_role_id = role.id
    save_data()
    await ctx.send(f"✅ Verified role set to {role.mention}")

@setup.command()
@commands.has_permissions(manage_guild=True)
async def logs(ctx, channel: discord.TextChannel):
    global logs_channel_id
    logs_channel_id = channel.id
    save_data()
    await ctx.send(f"✅ Logs channel set to {channel.mention}")

# ================= SEND VERIFY PANEL =================
@bot.command()
@commands.has_permissions(manage_guild=True)
async def verify(ctx):
    if not verify_channel_id:
        return await ctx.send("❌ Verify channel not set.")

    channel = ctx.guild.get_channel(verify_channel_id)
    if not channel:
        return await ctx.send("❌ Channel not found.")

    embed = discord.Embed(
        title="🔐 Server Verification",
        description="Click the button below to verify and access the server.",
        color=discord.Color.green()
    )

    await channel.send(embed=embed, view=VerifyView())
    await ctx.send("✅ Verification panel sent.")

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

# ================= KICK =================
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 Kicked {member.mention}")

        embed = discord.Embed(
            title="👢 Member Kicked",
            color=discord.Color.orange()
        )
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        await send_log(ctx.guild, embed)

    except:
        await ctx.send("❌ Cannot kick this user.")

# ================= START =================
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(TOKEN)