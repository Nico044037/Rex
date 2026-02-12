import os
import json
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "data.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=["!", "?"], intents=intents)

# ================= STORAGE =================
default_data = {
    "welcome_channel": None,
    "verify_channel": None,
    "verified_role": None,
    "logs_channel": None,
    "ticket_category": None,
    "ticket_panel": None,
    "antinuke": False
}

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump(default_data, f)

with open(DATA_FILE, "r") as f:
    data = json.load(f)

welcome_channel_id = data["welcome_channel"]
verify_channel_id = data["verify_channel"]
verified_role_id = data["verified_role"]
logs_channel_id = data["logs_channel"]
ticket_category_id = data["ticket_category"]
ticket_panel_id = data["ticket_panel"]
antinuke_enabled = data["antinuke"]

ticket_owners = {}

def save():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "welcome_channel": welcome_channel_id,
            "verify_channel": verify_channel_id,
            "verified_role": verified_role_id,
            "logs_channel": logs_channel_id,
            "ticket_category": ticket_category_id,
            "ticket_panel": ticket_panel_id,
            "antinuke": antinuke_enabled
        }, f, indent=4)

async def log(guild, embed):
    if not logs_channel_id:
        return
    ch = guild.get_channel(logs_channel_id)
    if ch:
        await ch.send(embed=embed)

# ================= RULES EMBED =================
def rules_embed():
    embed = discord.Embed(
        title="📜 Server Rules",
        description="Please read before participating.",
        color=discord.Color.red()
    )
    embed.add_field(
        name="Rules",
        value=(
            "1️⃣ Be respectful\n"
            "2️⃣ No spamming\n"
            "3️⃣ No NSFW\n"
            "4️⃣ No advertising\n"
            "5️⃣ No illegal content\n"
            "6️⃣ Staff decisions are final"
        ),
        inline=False
    )
    return embed

# ================= VERIFY =================
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(verified_role_id)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ Verified!", ephemeral=True)

            embed = discord.Embed(title="🔐 Verified", description=interaction.user.mention)
            await log(interaction.guild, embed)

# ================= TICKETS =================
class CloseModal(Modal):
    def __init__(self, channel):
        super().__init__(title="Close Ticket")
        self.channel = channel
        self.reason = TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"Reason:\n{self.reason.value}",
            color=discord.Color.red()
        )
        await self.channel.send(embed=embed)
        await asyncio.sleep(2)
        await self.channel.delete()

class CloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction, button):
        owner = ticket_owners.get(interaction.channel.id)
        if interaction.user.id != owner and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Not allowed.", ephemeral=True)
        await interaction.response.send_modal(CloseModal(interaction.channel))

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction, button):
        category = interaction.guild.get_channel(ticket_category_id)
        if not category:
            return await interaction.response.send_message("Ticket not set.", ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category
        )

        ticket_owners[channel.id] = interaction.user.id

        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True)

        await channel.send(
            embed=discord.Embed(title="🎫 Ticket Opened"),
            view=CloseView()
        )

        await interaction.response.send_message(f"Created {channel.mention}", ephemeral=True)

# ================= READY =================
@bot.event
async def on_ready():
    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(CloseView())
    print("Bot ready.")

# ================= JOIN =================
@bot.event
async def on_member_join(member):
    try:
        await member.send(embed=rules_embed())
    except:
        pass

    if welcome_channel_id:
        ch = member.guild.get_channel(welcome_channel_id)
        if ch:
            await ch.send(f"👋 Welcome {member.mention}")

    embed = discord.Embed(title="📥 Member Joined", description=member.mention)
    await log(member.guild, embed)

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="📤 Member Left", description=str(member))
    await log(member.guild, embed)

# ================= ANTI NUKE =================
@bot.event
async def on_guild_channel_delete(channel):
    if not antinuke_enabled:
        return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        await channel.guild.ban(entry.user, reason="Anti-nuke")
        embed = discord.Embed(title="🛡 Anti-Nuke", description=f"{entry.user} banned.")
        await log(channel.guild, embed)

@bot.event
async def on_guild_role_delete(role):
    if not antinuke_enabled:
        return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        await role.guild.ban(entry.user, reason="Anti-nuke")
        embed = discord.Embed(title="🛡 Anti-Nuke", description=f"{entry.user} banned.")
        await log(role.guild, embed)

# ================= COMMANDS =================
@bot.group()
async def setup(ctx):
    pass

@setup.command()
async def welcome(ctx, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    save()
    await ctx.send("Set.")

@setup.command()
async def verify(ctx, channel: discord.TextChannel):
    global verify_channel_id
    verify_channel_id = channel.id
    save()
    await ctx.send("Set.")

@setup.command()
async def verifiedrole(ctx, role: discord.Role):
    global verified_role_id
    verified_role_id = role.id
    save()
    await ctx.send("Set.")

@setup.command()
async def logs(ctx, channel: discord.TextChannel):
    global logs_channel_id
    logs_channel_id = channel.id
    save()
    await ctx.send("Set.")

@setup.command()
async def ticket(ctx):
    category = await ctx.guild.create_category("Tickets")
    panel = await ctx.guild.create_text_channel("ticket-panel", category=category)
    global ticket_category_id
    ticket_category_id = category.id
    save()
    await panel.send("Create ticket:", view=TicketView())

@bot.command()
async def verify(ctx):
    channel = ctx.guild.get_channel(verify_channel_id)
    if channel:
        await channel.send("Click to verify", view=VerifyView())

@bot.command()
async def antinuke(ctx):
    global antinuke_enabled
    antinuke_enabled = not antinuke_enabled
    save()
    await ctx.send(f"Anti-nuke {'ON' if antinuke_enabled else 'OFF'}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def clear(ctx):
    old = ctx.channel
    new = await old.clone()
    await new.edit(position=old.position, category=old.category)
    await old.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def senddm(ctx, user: discord.User, *, message):
    await user.send(message)
    await ctx.send("Sent.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send("Kicked.")

bot.run(TOKEN)