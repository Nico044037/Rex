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
                "autoroles": []
            },
            f
        )

with open(DATA_FILE, "r") as f:
    data = json.load(f)

welcome_channel_id: int | None = data.get("welcome_channel")
verify_channel_id: int | None = data.get("verify_channel")
verified_role_id: int | None = data.get("verified_role")
autoroles: set[int] = set(data.get("autoroles", []))


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(
            {
                "welcome_channel": welcome_channel_id,
                "verify_channel": verify_channel_id,
                "verified_role": verified_role_id,
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

    # DM rules
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

# ================= SETUP GROUP =================
@bot.group(invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def setup(ctx):
    await ctx.send("Use: `!setup welcome #channel`, `!setup verify #channel`, `!setup verifiedrole @role`")


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
    except:
        await ctx.send("❌ Cannot kick this user.")

# ================= START =================
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(TOKEN)