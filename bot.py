import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
import os

# --- Database setup ---
conn = sqlite3.connect('events.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                date TEXT,
                description TEXT,
                attendees TEXT
            )''')
conn.commit()

# --- Bot setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Commands ---

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    weekly_reminder.start()
    cleanup_events.start()

@bot.command()
async def create_event(ctx, name: str, date: str, *, description: str):
    """Create a new event. Format: !create_event <name> <YYYY-MM-DD> <description>"""
    try:
        event_date = datetime.strptime(date, "%Y-%m-%d")
        c.execute("INSERT INTO events (name, date, description, attendees) VALUES (?, ?, ?, ?)",
                  (name, date, description, ""))
        conn.commit()
        await ctx.send(f"✅ Event '{name}' scheduled for {date}.")
    except ValueError:
        await ctx.send("⚠️ Invalid date format. Use YYYY-MM-DD.")

@bot.command()
async def show_events(ctx, month: str = None):
    """Show all events or only events for a specific month."""
    c.execute("SELECT * FROM events ORDER BY date")
    events = c.fetchall()
    if not events:
        await ctx.send("📭 No events found.")
        return

    now = datetime.now()
    event_list = []
    for e in events:
        event_date = datetime.strptime(e[2], "%Y-%m-%d")
        if not month or event_date.strftime("%B").lower() == month.lower():
            attendees = len(e[4].split(",")) if e[4] else 0
            event_list.append(f"**{e[1]}** — {e[2]} ({attendees} attending)\n{e[3]}")

    if not event_list:
        await ctx.send(f"📭 No events found for {month.capitalize()}.")
    else:
        await ctx.send("\n\n".join(event_list))

@bot.command()
async def rsvp(ctx, *, event_name: str):
    """RSVP to an event by name."""
    c.execute("SELECT * FROM events WHERE name = ?", (event_name,))
    event = c.fetchone()
    if not event:
        await ctx.send("⚠️ Event not found.")
        return

    attendees = event[4].split(",") if event[4] else []
    user_id = str(ctx.author.id)

    if user_id in attendees:
        await ctx.send("❌ You’ve already RSVP’d to this event.")
    else:
        attendees.append(user_id)
        c.execute("UPDATE events SET attendees = ? WHERE id = ?",
                  (",".join(attendees), event[0]))
        conn.commit()
        await ctx.send(f"✅ {ctx.author.mention} RSVP’d for **{event_name}**!")

@bot.command()
async def attendees(ctx, *, event_name: str):
    """See how many people RSVP’d to a specific event."""
    c.execute("SELECT * FROM events WHERE name = ?", (event_name,))
    event = c.fetchone()
    if not event:
        await ctx.send("⚠️ Event not found.")
        return

    attendees = event[4].split(",") if event[4] else []
    if not attendees:
        await ctx.send(f"📭 No one has RSVP’d for **{event_name}** yet.")
    else:
        user_mentions = []
        for uid in attendees:
            user = await bot.fetch_user(int(uid))
            user_mentions.append(user.mention)
        await ctx.send(f"🎉 **{len(attendees)} people** RSVP’d for **{event_name}**:\n" + ", ".join(user_mentions))

@bot.command(name="commands")
async def show_commands(ctx):
    """Show all available commands."""
    embed = discord.Embed(title="📜 Event Bot Commands", color=0x00ffcc)
    embed.add_field(name="!create_event <name> <YYYY-MM-DD> <description>", value="Create a new event.", inline=False)
    embed.add_field(name="!show_events [month]", value="Show all events or only for a specific month.", inline=False)
    embed.add_field(name="!rsvp <event_name>", value="RSVP for an event.", inline=False)
    embed.add_field(name="!attendees <event_name>", value="See who RSVP’d to an event.", inline=False)
    embed.add_field(name="!commands", value="Show this command list.", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def test(ctx):
    """Diagnostic command to check bot health and permissions."""
    guild = ctx.guild
    channel = ctx.channel
    me = guild.me
    perms = channel.permissions_for(me)

    embed = discord.Embed(title="🤖 Bot Diagnostic Report", color=0x00ffcc)
    embed.add_field(name="Server", value=guild.name, inline=False)
    embed.add_field(name="Channel", value=f"#{channel.name} ({channel.id})", inline=False)
    embed.add_field(name="Bot Role", value=", ".join([r.name for r in me.roles]), inline=False)

    permission_summary = (
        f"👁️ View Channel: {'✅' if perms.view_channel else '❌'}\n"
        f"💬 Send Messages: {'✅' if perms.send_messages else '❌'}\n"
        f"📖 Read Message History: {'✅' if perms.read_message_history else '❌'}\n"
        f"🧱 Embed Links: {'✅' if perms.embed_links else '❌'}\n"
        f"📎 Attach Files: {'✅' if perms.attach_files else '❌'}\n"
        f"🧹 Manage Messages: {'✅' if perms.manage_messages else '❌'}"
    )
    embed.add_field(name="Permissions", value=permission_summary, inline=False)

    try:
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("⚠️ I don't have permission to send embeds here!")
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: `{e}`")

# --- Background Tasks ---

@tasks.loop(hours=24)
async def cleanup_events():
    """Delete events 10 days after they’ve passed."""
    now = datetime.now()
    cutoff = now - timedelta(days=10)
    c.execute("SELECT * FROM events")
    events = c.fetchall()
    for e in events:
        event_date = datetime.strptime(e[2], "%Y-%m-%d")
        if event_date < cutoff:
            c.execute("DELETE FROM events WHERE id = ?", (e[0],))
    conn.commit()

@tasks.loop(hours=24)
async def weekly_reminder():
    """Send reminders every Monday for events in the next 14 days."""
    now = datetime.now()
    if now.weekday() == 0:  # Monday
        upcoming_start = now
        upcoming_end = now + timedelta(days=14)
        c.execute("SELECT * FROM events")
        events = c.fetchall()
        upcoming = []
        for e in events:
            event_date = datetime.strptime(e[2], "%Y-%m-%d")
            if upcoming_start <= event_date <= upcoming_end:
                upcoming.append(f"📅 **{e[1]}** — {e[2]}\n{e[3]}")

        if upcoming:
            reminder_channel_id = 956364618035527710  # replace with your channel ID
            channel = bot.get_channel(reminder_channel_id)
            if channel:
                await channel.send("🔔 **Upcoming Events (Next 14 Days):**\n\n" + "\n\n".join(upcoming))

# --- Run the bot ---
bot.run(os.getenv("DISCORD_BOT_TOKEN"))

