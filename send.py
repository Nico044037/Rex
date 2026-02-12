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

# ================= EMBED SYSTEM =================
def success(title, desc):
    return discord.Embed(title=f"✅ {title}", description=desc, color=discord.Color.green())

def error(title, desc):
    return discord.Embed(title=f"❌ {title}", description=desc, color=discord.Color.red())

def info(title, desc):
    return discord.Embed(title=f"ℹ️ {title}", description=desc, color=discord.Color.blurple())

def log_embed(title, desc):
    return discord.Embed(title=f"📜 {title}", description=desc, color=discord.Color.orange())

# ================= STORAGE =================
default_data = {
    "welcome_channel": None,
    "verify_channel": None,
    "verified_role": None,
    "logs_channel": None,
    "rules_channel": None,
    "ticket_category": None,
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
rules_channel_id = data["rules_channel"]
ticket_category_id = data["ticket_category"]
antinuke_enabled = data["antinuke"]

ticket_owners = {}

def save():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "welcome_channel": welcome_channel_id,
            "verify_channel": verify_channel_id,
            "verified_role": verified_role_id,
            "logs_channel": logs_channel_id,
            "rules_channel": rules_channel_id,
            "ticket_category": ticket_category_id,
            "antinuke": antinuke_enabled
        }, f, indent=4)

async def log(guild, embed):
    if not logs_channel_id:
        return
    ch = guild.get_channel(logs_channel_id)
    if ch:
        await ch.send(embed=embed)

# ================= RULES =================
def rules_embed():
    embed = discord.Embed(
        title="📜 Server Rules",
        description="Please read carefully before participating.",
        color=discord.Color.red()
    )
    embed.add_field(name="🔹 Respect", value="Be respectful to everyone.", inline=False)
    embed.add_field(name="🔹 No Spam", value="Do not spam.", inline=False)
    embed.add_field(name="🔹 No NSFW", value="No NSFW content.", inline=False)
    embed.add_field(name="🔹 No Advertising", value="No self promotion.", inline=False)
    embed.add_field(name="🔹 Follow TOS", value="Follow Discord Terms.", inline=False)
    embed.set_footer(text="By staying you agree to these rules.")
    return embed

# ================= VERIFY =================
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction, button):
        role = interaction.guild.get_role(verified_role_id)
        if not role:
            return await interaction.response.send_message(embed=error("Error", "Verified role not set."), ephemeral=True)

        await interaction.user.add_roles(role)
        await interaction.response.send_message(embed=success("Verified", "You now have access."), ephemeral=True)

        await log(interaction.guild, log_embed("User Verified", interaction.user.mention))

# ================= TICKETS =================
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
            return await interaction.response.send_message(embed=error("Permission Denied", "Only owner or admin."), ephemeral=True)

        await interaction.response.send_modal(CloseModal(interaction.channel))

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction, button):
        category = interaction.guild.get_channel(ticket_category_id)
        if not category:
            return await interaction.response.send_message(embed=error("Error", "Ticket system not set."), ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category
        )

        ticket_owners[channel.id] = interaction.user.id

        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True)

        await channel.send(embed=info("Ticket Opened", "Describe your issue below."), view=CloseView())
        await interaction.response.send_message(embed=success("Ticket Created", channel.mention), ephemeral=True)

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
            await ch.send(embed=success("New Member", f"Welcome {member.mention}!"))

    await log(member.guild, log_embed("Member Joined", member.mention))

@bot.event
async def on_member_remove(member):
    await log(member.guild, log_embed("Member Left", str(member)))

# ================= ANTI NUKE =================
@bot.event
async def on_guild_channel_delete(channel):
    if not antinuke_enabled:
        return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        await channel.guild.ban(entry.user, reason="Anti-nuke")
        await log(channel.guild, log_embed("Anti-Nuke Triggered", f"{entry.user} banned."))

@bot.event
async def on_guild_role_delete(role):
    if not antinuke_enabled:
        return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        await role.guild.ban(entry.user, reason="Anti-nuke")
        await log(role.guild, log_embed("Anti-Nuke Triggered", f"{entry.user} banned."))

# ================= COMMANDS =================
@bot.group()
async def setup(ctx):
    pass

@setup.command()
async def welcome(ctx, channel: discord.TextChannel):
    global welcome_channel_id
    welcome_channel_id = channel.id
    save()
    await ctx.send(embed=success("Welcome Channel Set", channel.mention))

@setup.command()
async def verify(ctx, channel: discord.TextChannel):
    global verify_channel_id
    verify_channel_id = channel.id
    save()
    await ctx.send(embed=success("Verify Channel Set", channel.mention))

@setup.command()
async def verifiedrole(ctx, role: discord.Role):
    global verified_role_id
    verified_role_id = role.id
    save()
    await ctx.send(embed=success("Verified Role Set", role.mention))

@setup.command()
async def logs(ctx, channel: discord.TextChannel):
    global logs_channel_id
    logs_channel_id = channel.id
    save()
    await ctx.send(embed=success("Logs Channel Set", channel.mention))

@setup.command()
async def rules(ctx, channel: discord.TextChannel):
    global rules_channel_id
    rules_channel_id = channel.id
    save()
    await channel.send(embed=rules_embed())
    await ctx.send(embed=success("Rules Sent", channel.mention))

@setup.command()
async def ticket(ctx):
    category = await ctx.guild.create_category("Tickets")
    panel = await ctx.guild.create_text_channel("ticket-panel", category=category)
    global ticket_category_id
    ticket_category_id = category.id
    save()
    await panel.send(embed=info("Ticket System", "Click below to create ticket."), view=TicketView())
    await ctx.send(embed=success("Ticket System Created", panel.mention))

@bot.command()
async def verify(ctx):
    channel = ctx.guild.get_channel(verify_channel_id)
    if channel:
        await channel.send(embed=info("Verification Required", "Click button below."), view=VerifyView())

@bot.command()
async def antinuke(ctx):
    global antinuke_enabled
    antinuke_enabled = not antinuke_enabled
    save()
    await ctx.send(embed=success("Anti-Nuke Toggled", f"Now {'ON' if antinuke_enabled else 'OFF'}"))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(embed=success("Messages Purged", f"Deleted {len(deleted)} messages."))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def clear(ctx):
    old = ctx.channel
    new = await old.clone()
    await new.edit(position=old.position, category=old.category)
    await old.delete()

@bot.command(name="send")
@commands.has_permissions(administrator=True)
async def send(ctx, user: discord.Member, *, message):
    try:
        await user.send(embed=info("Message from Server", message))
        await ctx.send(embed=success("DM Sent", user.mention))
    except:
        await ctx.send(embed=error("Failed", "Could not send DM."))

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(embed=success("User Kicked", member.mention))

bot.run(TOKEN)