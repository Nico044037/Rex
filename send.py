import os
import asyncio
import asyncpg
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import io

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["!", "?"], intents=intents)

db = None
ticket_owners = {}

# ================= EMBED SYSTEM =================
def success(t,d): return discord.Embed(title=f"✅ {t}",description=d,color=discord.Color.green())
def error(t,d): return discord.Embed(title=f"❌ {t}",description=d,color=discord.Color.red())
def info(t,d): return discord.Embed(title=f"ℹ️ {t}",description=d,color=discord.Color.blurple())
def log_embed(t,d): return discord.Embed(title=f"📜 {t}",description=d,color=discord.Color.orange())

# ================= DATABASE =================
@bot.event
async def on_ready():
    global db
    db = await asyncpg.create_pool(DATABASE_URL)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id BIGINT PRIMARY KEY,
        welcome_channel BIGINT,
        verify_channel BIGINT,
        verified_role BIGINT,
        logs_channel BIGINT,
        rules_channel BIGINT,
        ticket_category BIGINT,
        antinuke BOOLEAN DEFAULT FALSE
    );
    """)

    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(CloseView())

    print("Bot ready (Public PostgreSQL Version)")

async def get_settings(guild_id):
    row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    if not row:
        await db.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", guild_id)
        row = await db.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)
    return row

async def update_setting(guild_id, column, value):
    await db.execute(
        f"UPDATE guild_settings SET {column}=$1 WHERE guild_id=$2",
        value, guild_id
    )

# ================= LOG FUNCTION =================
async def log(guild, embed, file=None):
    settings = await get_settings(guild.id)
    if settings["logs_channel"]:
        ch = guild.get_channel(settings["logs_channel"])
        if ch:
            await ch.send(embed=embed, file=file)

# ================= RULES =================
def rules_embed():
    e = discord.Embed(
        title="📜 Server Rules",
        description="By staying you agree to follow these rules.",
        color=discord.Color.red()
    )
    e.add_field(name="Respect", value="No harassment or hate.", inline=False)
    e.add_field(name="No Spam", value="No flooding channels.", inline=False)
    e.add_field(name="No NSFW", value="Keep content safe.", inline=False)
    e.add_field(name="No Advertising", value="No promotion.", inline=False)
    e.set_footer(text="Breaking rules may result in punishment.")
    return e

# ================= VERIFY =================
class VerifyView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_btn")
    async def verify(self, interaction, button):
        settings = await get_settings(interaction.guild.id)
        role_id = settings["verified_role"]
        if not role_id:
            return await interaction.response.send_message(embed=error("Error","Verified role not set."),ephemeral=True)

        role = interaction.guild.get_role(role_id)
        await interaction.user.add_roles(role)
        await interaction.response.send_message(embed=success("Verified","Access granted."),ephemeral=True)
        await log(interaction.guild, log_embed("User Verified",interaction.user.mention))

# ================= TICKETS =================
async def create_transcript(channel):
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
    data = "\n".join(messages)
    return discord.File(io.BytesIO(data.encode()), filename=f"{channel.name}.txt")

class CloseModal(Modal):
    def __init__(self, channel):
        super().__init__(title="Close Ticket")
        self.channel = channel
        self.reason = TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        transcript = await create_transcript(self.channel)
        await log(interaction.guild,
                  log_embed("Ticket Closed",
                            f"{self.channel.name}\nReason: {self.reason.value}"),
                  transcript)
        await self.channel.delete()

class CloseView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction, button):
        owner = ticket_owners.get(interaction.channel.id)
        if interaction.user.id != owner and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(embed=error("Denied","Only owner/admin."),ephemeral=True)
        await interaction.response.send_modal(CloseModal(interaction.channel))

class TicketView(View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction, button):
        settings = await get_settings(interaction.guild.id)
        if not settings["ticket_category"]:
            return await interaction.response.send_message(embed=error("Error","Ticket system not set."),ephemeral=True)

        category = interaction.guild.get_channel(settings["ticket_category"])
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category
        )

        ticket_owners[channel.id] = interaction.user.id

        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True)

        await channel.send(embed=info("Ticket Opened","Describe your issue."),view=CloseView())
        await interaction.response.send_message(embed=success("Ticket Created",channel.mention),ephemeral=True)

# ================= EVENTS =================
@bot.event
async def on_member_join(member):
    try:
        await member.send(embed=rules_embed())
    except:
        pass

    settings = await get_settings(member.guild.id)
    if settings["welcome_channel"]:
        ch = member.guild.get_channel(settings["welcome_channel"])
        if ch:
            await ch.send(embed=success("New Member",member.mention))

    await log(member.guild, log_embed("Member Joined",member.mention))

@bot.event
async def on_member_remove(member):
    await log(member.guild, log_embed("Member Left",str(member)))

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    await log(message.guild,
              log_embed("Message Deleted",
                        f"{message.author} in {message.channel.mention}\n{message.content}"))

@bot.event
async def on_message_edit(before, after):
    if before.author.bot: return
    await log(before.guild,
              log_embed("Message Edited",
                        f"{before.author}\nBefore: {before.content}\nAfter: {after.content}"))

# ================= ANTI-NUKE =================
@bot.event
async def on_guild_channel_delete(channel):
    settings = await get_settings(channel.guild.id)
    if not settings["antinuke"]: return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        await channel.guild.ban(entry.user, reason="Anti-nuke")
        await log(channel.guild, log_embed("Anti-Nuke Triggered",f"{entry.user} banned."))

# ================= COMMANDS =================
@bot.group()
async def setup(ctx): pass

@setup.command()
async def welcome(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"welcome_channel",channel.id)
    await ctx.send(embed=success("Welcome Channel Set",channel.mention))

@setup.command()
async def verify(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"verify_channel",channel.id)
    await ctx.send(embed=success("Verify Channel Set",channel.mention))

@setup.command()
async def verifiedrole(ctx, role:discord.Role):
    await update_setting(ctx.guild.id,"verified_role",role.id)
    await ctx.send(embed=success("Verified Role Set",role.mention))

@setup.command()
async def logs(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"logs_channel",channel.id)
    await ctx.send(embed=success("Logs Channel Set",channel.mention))

@setup.command()
async def rules(ctx, channel:discord.TextChannel):
    await update_setting(ctx.guild.id,"rules_channel",channel.id)
    await channel.send(embed=rules_embed())
    await ctx.send(embed=success("Rules Sent",channel.mention))

@setup.command()
async def ticket(ctx):
    category = await ctx.guild.create_category("Tickets")
    await update_setting(ctx.guild.id,"ticket_category",category.id)
    panel = await ctx.guild.create_text_channel("ticket-panel",category=category)
    await panel.send(embed=info("Ticket System","Click below."),view=TicketView())
    await ctx.send(embed=success("Ticket System Created",panel.mention))

@bot.command()
async def antinuke(ctx):
    settings = await get_settings(ctx.guild.id)
    new = not settings["antinuke"]
    await update_setting(ctx.guild.id,"antinuke",new)
    await ctx.send(embed=success("Anti-Nuke Toggled",str(new)))

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount:int):
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(embed=success("Purged",f"{len(deleted)} messages."))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def clear(ctx):
    old = ctx.channel
    new = await old.clone()
    await new.edit(position=old.position,category=old.category)
    await old.delete()

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member:discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(embed=success("User Kicked",member.mention))

@bot.command(name="send")
@commands.has_permissions(administrator=True)
async def send(ctx, user:discord.Member, *, message):
    try:
        await user.send(embed=info("Message from Server",message))
        await ctx.send(embed=success("DM Sent",user.mention))
    except:
        await ctx.send(embed=error("Failed","Could not DM user."))

bot.run(TOKEN)
