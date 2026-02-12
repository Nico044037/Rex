import os
import json
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

# ================= CONFIG =================
TOKEN = "YOUR_BOT_TOKEN_HERE"
CONFIG_FILE = "config.json"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["!", "?"], intents=intents)

# ================= EMBED SYSTEM =================
def success(t, d): return discord.Embed(title=f"✅ {t}", description=d, color=discord.Color.green())
def error(t, d): return discord.Embed(title=f"❌ {t}", description=d, color=discord.Color.red())
def info(t, d): return discord.Embed(title=f"ℹ️ {t}", description=d, color=discord.Color.blurple())
def log_embed(t, d): return discord.Embed(title=f"📜 {t}", description=d, color=discord.Color.orange())

# ================= PERSISTENT CONFIG =================
default_config = {
    "welcome_channel": None,
    "verify_channel": None,
    "verified_role": None,
    "logs_channel": None,
    "ticket_category": None,
    "antinuke": False
}

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump(default_config, f)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# ================= LOG FUNCTION =================
async def log(guild, embed):
    channel_id = config["logs_channel"]
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        await channel.send(embed=embed)

# ================= RULES EMBED =================
def rules_embed():
    e = discord.Embed(
        title="📜 Server Rules",
        description="By staying in this server you agree to follow these rules.",
        color=discord.Color.red()
    )
    e.add_field(name="Respect", value="No harassment or hate.", inline=False)
    e.add_field(name="No Spam", value="No flooding channels.", inline=False)
    e.add_field(name="No NSFW", value="Keep content appropriate.", inline=False)
    e.add_field(name="No Advertising", value="No self promotion.", inline=False)
    return e

# ================= VERIFY SYSTEM =================
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction, button):
        role_id = config["verified_role"]
        if not role_id:
            return await interaction.response.send_message(embed=error("Error", "Verified role not set."), ephemeral=True)

        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message(embed=error("Error", "Role not found."), ephemeral=True)

        await interaction.user.add_roles(role)
        await interaction.response.send_message(embed=success("Verified", "Access granted."), ephemeral=True)

        await log(interaction.guild, log_embed("User Verified", interaction.user.mention))

# ================= TICKET SYSTEM =================
ticket_owners = {}

class CloseModal(Modal):
    def __init__(self, channel):
        super().__init__(title="Close Ticket")
        self.channel = channel
        self.reason = TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        await self.channel.send(embed=info("Ticket Closed", f"Reason:\n{self.reason.value}"))
        await asyncio.sleep(2)
        await self.channel.delete()

class CloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction, button):
        owner = ticket_owners.get(interaction.channel.id)
        if interaction.user.id != owner and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(embed=error("Denied", "Only owner/admin."), ephemeral=True)

        await interaction.response.send_modal(CloseModal(interaction.channel))

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction, button):
        category_id = config["ticket_category"]
        if not category_id:
            return await interaction.response.send_message(embed=error("Error", "Ticket category not set."), ephemeral=True)

        category = interaction.guild.get_channel(category_id)
        if not category:
            return await interaction.response.send_message(embed=error("Error", "Category not found."), ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category
        )

        ticket_owners[channel.id] = interaction.user.id

        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True)

        await channel.send(embed=info("Ticket Opened", "Describe your issue below."), view=CloseView())
        await interaction.response.send_message(embed=success("Created", channel.mention), ephemeral=True)

# ================= EVENTS =================
@bot.event
async def on_ready():
    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(CloseView())
    print("Bot running.")

@bot.event
async def on_member_join(member):
    try:
        await member.send(embed=rules_embed())
    except:
        pass

    channel_id = config["welcome_channel"]
    if channel_id:
        channel = member.guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=success("New Member", member.mention))

    await log(member.guild, log_embed("Member Joined", member.mention))

@bot.event
async def on_member_remove(member):
    await log(member.guild, log_embed("Member Left", str(member)))

# ================= ANTI NUKE =================
@bot.event
async def on_guild_channel_delete(channel):
    if not config["antinuke"]:
        return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        await channel.guild.ban(entry.user, reason="Anti-nuke")
        await log(channel.guild, log_embed("Anti-Nuke", f"{entry.user} banned."))

@bot.event
async def on_guild_role_delete(role):
    if not config["antinuke"]:
        return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        await role.guild.ban(entry.user, reason="Anti-nuke")
        await log(role.guild, log_embed("Anti-Nuke", f"{entry.user} banned."))

# ================= SETUP =================
@bot.group()
async def setup(ctx):
    pass

@setup.command()
async def welcome(ctx, channel: discord.TextChannel):
    config["welcome_channel"] = channel.id
    save_config()
    await ctx.send(embed=success("Welcome Channel Set", channel.mention))

@setup.command()
async def verify(ctx, channel: discord.TextChannel):
    config["verify_channel"] = channel.id
    save_config()
    await ctx.send(embed=success("Verify Channel Set", channel.mention))

@setup.command()
async def verifiedrole(ctx, role: discord.Role):
    config["verified_role"] = role.id
    save_config()
    await ctx.send(embed=success("Verified Role Set", role.mention))

@setup.command()
async def logs(ctx, channel: discord.TextChannel):
    config["logs_channel"] = channel.id
    save_config()
    await ctx.send(embed=success("Logs Channel Set", channel.mention))

@setup.command()
async def ticket(ctx):
    category = await ctx.guild.create_category("Tickets")
    config["ticket_category"] = category.id
    save_config()

    panel = await ctx.guild.create_text_channel("ticket-panel", category=category)
    await panel.send(embed=info("Ticket System", "Click below to create ticket."), view=TicketView())
    await ctx.send(embed=success("Ticket System Created", panel.mention))

# ================= COMMANDS =================
@bot.command()
async def verify(ctx):
    channel_id = config["verify_channel"]
    if channel_id:
        channel = ctx.guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=info("Verification", "Click below."), view=VerifyView())

@bot.command()
async def antinuke(ctx):
    config["antinuke"] = not config["antinuke"]
    save_config()
    await ctx.send(embed=success("Anti-Nuke Toggled", str(config["antinuke"])))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(embed=success("Purged", f"{len(deleted)} messages."))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def clear(ctx):
    old = ctx.channel
    new = await old.clone()
    await new.edit(position=old.position, category=old.category)
    await old.delete()

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(embed=success("User Kicked", member.mention))

@bot.command(name="send")
@commands.has_permissions(administrator=True)
async def send(ctx, user: discord.Member, *, message):
    try:
        await user.send(embed=info("Message from Server", message))
        await ctx.send(embed=success("DM Sent", user.mention))
    except:
        await ctx.send(embed=error("Failed", "Could not DM user."))

# ================= START =================
bot.run(TOKEN)