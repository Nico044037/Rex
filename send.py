import os
import json
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

# ================= BASIC CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "data.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= STORAGE =================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({
            "welcome_channel": None,
            "verify_channel": None,
            "verified_role": None,
            "logs_channel": None,
            "ticket_category": None,
            "ticket_panel": None,
            "antinuke": False
        }, f)

with open(DATA_FILE, "r") as f:
    data = json.load(f)

welcome_channel_id = data.get("welcome_channel")
verify_channel_id = data.get("verify_channel")
verified_role_id = data.get("verified_role")
logs_channel_id = data.get("logs_channel")
ticket_category_id = data.get("ticket_category")
ticket_panel_id = data.get("ticket_panel")
antinuke_enabled = data.get("antinuke")

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

# ================= VERIFY VIEW =================
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(verified_role_id)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You are verified!", ephemeral=True)

            embed = discord.Embed(title="🔐 Verified", description=f"{interaction.user.mention} verified", color=discord.Color.blue())
            await log(interaction.guild, embed)

# ================= TICKET CLOSE MODAL =================
class CloseModal(Modal):
    def __init__(self, channel):
        super().__init__(title="Close Ticket")
        self.channel = channel
        self.reason = TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🔒 Ticket Closed", description=f"Reason:\n{self.reason.value}", color=discord.Color.red())
        await self.channel.send(embed=embed)

        await interaction.response.send_message("Ticket closing...", ephemeral=True)
        await asyncio.sleep(3)
        await self.channel.delete()

# ================= TICKET VIEW =================
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):

        category = interaction.guild.get_channel(ticket_category_id)
        if not category:
            return await interaction.response.send_message("Ticket category not set.", ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category
        )

        ticket_owners[channel.id] = interaction.user.id

        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)

        await channel.send(
            embed=discord.Embed(
                title="🎫 Ticket Opened",
                description="Describe your issue.\nPress close when finished.",
                color=discord.Color.green()
            ),
            view=CloseView()
        )

        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

class CloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):

        owner = ticket_owners.get(interaction.channel.id)
        is_admin = interaction.user.guild_permissions.administrator

        if interaction.user.id != owner and not is_admin:
            return await interaction.response.send_message("Only ticket owner or admin can close.", ephemeral=True)

        await interaction.response.send_modal(CloseModal(interaction.channel))

# ================= READY =================
@bot.event
async def on_ready():
    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(CloseView())
    print(f"Logged in as {bot.user}")

# ================= MEMBER EVENTS =================
@bot.event
async def on_member_join(member):
    if welcome_channel_id:
        ch = member.guild.get_channel(welcome_channel_id)
        if ch:
            await ch.send(f"👋 Welcome {member.mention}")

    embed = discord.Embed(title="📥 Member Joined", description=member.mention, color=discord.Color.green())
    await log(member.guild, embed)

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="📤 Member Left", description=str(member), color=discord.Color.red())
    await log(member.guild, embed)

# ================= ANTI NUKE =================
@bot.event
async def on_guild_channel_delete(channel):
    if not antinuke_enabled:
        return

    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        if entry.user.bot:
            continue
        await channel.guild.ban(entry.user, reason="Anti-Nuke: Channel deletion")
        embed = discord.Embed(title="🛡 Anti-Nuke", description=f"{entry.user} banned for deleting channel", color=discord.Color.red())
        await log(channel.guild, embed)

# ================= COMMANDS =================
@bot.group(invoke_without_command=True)
async def setup(ctx):
    await ctx.send("Use subcommands.")

@setup.command()
async def welcome(ctx, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    save()
    await ctx.send("Welcome channel set.")

@setup.command()
async def verify(ctx, channel: discord.TextChannel):
    global verify_channel_id
    verify_channel_id = channel.id
    save()
    await ctx.send("Verify channel set.")

@setup.command()
async def verifiedrole(ctx, role: discord.Role):
    global verified_role_id
    verified_role_id = role.id
    save()
    await ctx.send("Verified role set.")

@setup.command()
async def logs(ctx, channel: discord.TextChannel):
    global logs_channel_id
    logs_channel_id = channel.id
    save()
    await ctx.send("Logs channel set.")

@setup.command()
async def ticket(ctx):
    category = await ctx.guild.create_category("Tickets")
    channel = await ctx.guild.create_text_channel("ticket-panel", category=category)

    global ticket_category_id, ticket_panel_id
    ticket_category_id = category.id
    ticket_panel_id = channel.id
    save()

    await channel.send("🎫 Click below to create a ticket.", view=TicketView())
    await ctx.send("Ticket system created.")

@bot.command()
async def verify(ctx):
    channel = ctx.guild.get_channel(verify_channel_id)
    if channel:
        await channel.send("🔐 Click to verify", view=VerifyView())
        await ctx.send("Verify panel sent.")

@bot.command()
async def antinuke(ctx):
    global antinuke_enabled
    antinuke_enabled = not antinuke_enabled
    save()
    await ctx.send(f"Anti-Nuke is now {'ON' if antinuke_enabled else 'OFF'}")

# ================= START =================
bot.run(TOKEN)