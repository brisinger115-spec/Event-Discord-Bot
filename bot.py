import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
import os
from flask import Flask
from threading import Thread

# ================= KEEP-ALIVE FLASK SERVER =================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ================= DISCORD BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATABASE SETUP =================
conn = sqlite3.connect('events.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    date TEXT,
    description TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS rsvps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT,
    user_id INTEGER
)''')
conn.commit()
conn.close()

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    weekly_reminder.start()
    cleanup_past_events.start()

@bot.command(name="add_event")
async def add_event(ctx, name: str, date: str, *, description: str):
    try:
        datetime.strptime(date, "%Y-%m-%d")
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute("INSERT INTO events (name, date, description) VALUES (?, ?, ?)", (name, date, description))
        conn.commit()
        conn.close()
        await ctx.send(f"✅ Event **{name}** added for {date}!")
    except ValueError:
        await ctx.send("❌ Please use the correct date format: YYYY-MM-DD")

@bot.command(name="view_events")
async def view_events(ctx, month: str = None):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute("SELECT name, date, description FROM events")
    events = c.fetchall()
    conn.close()

    if not events:
        await ctx.send("📭 No events found.")
        return

    if month:
        try:
            month_number = datetime.strptime(month, "%B").month
            events = [e for e in events if datetime.strptime(e[1], "%Y-%m-%d").month == month_number]
        except ValueError:
            await ctx.send("❌ Invalid month name. Example: October, March, etc.")
            return

    if not events:
        await ctx.send(f"📭 No events found for {month}.")
        return

    message = "**📅 Upcoming Events:**\n"
    for name, date, desc in events:
        message += f"• **{name}** on {date} — {desc}\n"
    await ctx.send(message)

@bot.command(name="rsvp")
async def rsvp(ctx, *, event_name: str):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute("SELECT name FROM events WHERE name = ?", (event_name,))
    event = c.fetchone()

    if not event:
        await ctx.send("❌ Event not found.")
        conn.close()
        return

    c.execute("SELECT * FROM rsvps WHERE event_name = ? AND user_id = ?", (event_name, ctx.author.id))
    if c.fetchone():
        await ctx.send("⚠️ You already RSVP’d for this event.")
    else:
        c.execute("INSERT INTO rsvps (event_name, user_id) VALUES (?, ?)", (event_name, ctx.author.id))
        conn.commit()
        await ctx.send(f"✅ {ctx.author.display_name} RSVP’d for **{event_name}**!")
    conn.close()

@bot.command(name="rsvp_count")
async def rsvp_count(ctx, *, event_name: str):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM rsvps WHERE event_name = ?", (event_name,))
    count = c.fetchone()[0]
    conn.close()
    await ctx.send(f"📋 **{count}** people have RSVP’d for **{event_name}**.")

@bot.command(name="delete_event")
async def delete_event(ctx, *, event_name: str):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute("DELETE FROM events WHERE name = ?", (event_name,))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        await ctx.send(f"🗑️ Event **{event_name}** deleted.")
    else:
        await ctx.send("❌ Event not found.")

@bot.command(name="commands")
async def commands_list(ctx):
    cmds = (
        "**🧾 Event Commands List:**\n"
        "`!add_event \"Name\" YYYY-MM-DD Description` — Add new event\n"
        "`!view_events [MonthName]` — View all or monthly events\n"
        "`!delete_event EventName` — Delete event\n"
        "`!rsvp EventName` — RSVP for event\n"
        "`!rsvp_count EventName` — See RSVP count\n"
        "`!commands` — Show this list"
    )
    await ctx.send(cmds)

# ================= AUTOMATION TASKS =================
@tasks.loop(hours=168)
async def weekly_reminder():
    channel_id = 956364618035527710  # replace with your channel ID
    channel = bot.get_channel(channel_id)
    if not channel:
        print("⚠️ Reminder channel not found. Check channel ID.")
        return

    today = datetime.now().date()
    reminder_range = today + timedelta(days=14)
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute("SELECT name, date, description FROM events")
    events = c.fetchall()
    conn.close()

    upcoming = [(n, d, desc) for n, d, desc in events if today <= datetime.strptime(d, "%Y-%m-%d").date() <= reminder_range]

    if upcoming:
        message = "**⏰ Upcoming Events in the Next 14 Days:**\n"
        for name, date, desc in upcoming:
            message += f"• **{name}** on {date} — {desc}\n"
        await channel.send(message)
    else:
        await channel.send("📭 No events in the next 14 days!")

@tasks.loop(hours=24)
async def cleanup_past_events():
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    cutoff_date = datetime.now() - timedelta(days=10)
    c.execute("DELETE FROM events WHERE date < ?", (cutoff_date.strftime("%Y-%m-%d"),))
    conn.commit()
    conn.close()

# ================= RUN BOT =================
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
