import discord
import logging
import sqlite3
import datetime
import matplotlib.pyplot as plt
import numpy as np 
import os
from collections import defaultdict
from discord.ext import tasks

intents = discord.Intents.default() 
intents.members = True
client = discord.Client(intents=intents)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
tree = discord.app_commands.CommandTree(client)

user_messages = {}

connection = sqlite3.connect('bot.db')
cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_messages (
        guild_id INTEGER,
        user_id INTEGER,
        date TEXT,
        messages INTEGER DEFAULT 0,

        PRIMARY KEY (guild_id, user_id, date)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS scanned_guilds (
        guild_id INTEGER 
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_channel (
        guild_id INTEGER,
        channel_id INTEGER
    )
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_user_messages_guild_date
    ON user_messages (guild_id, date)
""")

@client.event
async def on_ready():
    synced = await tree.sync() 

    print(f'We have logged in as {client.user}')

    # channel = client.get_channel(929251085808459807)
    # async for message in channel.history(limit=20):
    #     print(message.author.name)

    # guild = client.get_guild(929250943642505277)
    # for channel in guild.text_channels :
    #     async for message in channel.history(limit=1000):

    #         date = message.created_at.date().isoformat()
    #         id = message.author.id 
            
    #         if id not in user_messages:
    #             user_messages[id] = {}

    #         if date not in user_messages[id]:
    #             user_messages[id][date] = 0
    #         user_messages[id][date] += 1
    # print(user_messages)

    for guild in client.guilds: 
        guild_id = guild.id

        cursor.execute("""
            SELECT guild_id
            FROM scanned_guilds
            WHERE guild_id = ?
        """,
        (guild_id,))

        if cursor.fetchone(): pass

        else: 
            await scan_history(guild=guild)
            cursor.execute("""
                INSERT INTO scanned_guilds (guild_id)
                VALUES (?)
            """, 
            (guild_id,))
            connection.commit()

    if not daily_report.is_running():
        daily_report.start()

async def scan_history(guild):
    upsert_sql = """
        INSERT INTO user_messages (guild_id, user_id, date, messages)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (guild_id, user_id, date)
        DO UPDATE SET messages = messages + excluded.messages
    """
    for channel in guild.text_channels:
        counts = defaultdict(int)
        try:
            async for message in channel.history(limit=None):
                if message.author.bot:
                    continue
                date = message.created_at.date().isoformat()
                counts[(guild.id, message.author.id, date)] += 1
        except (discord.Forbidden, discord.HTTPException):
            continue

        if counts:
            batch_data = [
                (g_id, u_id, d, cnt)
                for (g_id, u_id, d), cnt in counts.items()
            ]
            cursor.executemany(upsert_sql, batch_data)
            connection.commit()

@client.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = message.guild.id
    user_id = message.author.id
    date = message.created_at.date().isoformat()

    cursor.execute("""
        INSERT INTO user_messages 
        (guild_id, user_id, date, messages)

        VALUES (?, ?, ?, 1)

        ON CONFLICT (guild_id, user_id, date)
        DO UPDATE SET messages = messages + 1
    """,
    (guild_id, user_id, date,))

    connection.commit()

def yapshare_fig(interaction:None, start_date, end_date, x, y, ax1:None, ax2:None, guild:None):
    aspect = [16, 9]
    fig = None
    if ax1 is None and ax2 is None: 
        fig, (ax1, ax2) = plt.subplots(x, y, figsize=(aspect[x-1], aspect[y-1]), facecolor='#1E1F22', layout='constrained')
        fig.set_constrained_layout_pads(w_pad=0.3) 
    ax1.set_ylabel(f"total message share", color='#DBDEE1') 
    ax2.set_ylabel(f"total message share", color='#DBDEE1')  

    if guild == None:
        guild = interaction.guild
        guild_id = guild.id 
    else: guild_id = guild.id

    cursor.execute("""
        SELECT user_id, SUM(messages) as total
        FROM user_messages
        WHERE guild_id = ?
          AND date BETWEEN ? AND ?
        GROUP BY user_id
        HAVING total > 0
        ORDER BY total DESC
    """, (guild_id, start_date, end_date))
    rows = cursor.fetchall()

    member_totals = []
    member_names = []
    for user_id, total in rows:
        member = guild.get_member(user_id) if guild else None
        name = member.name if member else f"User {user_id}"
        member_names.append(name)
        member_totals.append(total)

    def format_autotext(pct):
        count = int(round(pct / 100 * sum(member_totals)))
        return f"{count}/{pct:.1f}%"

    if sum(member_totals) == 0:
        ax2.text(0.5, 0.5, "No messages in this period",
             ha="center", va="center", color="white", fontsize = 20) 
        wedges, texts, autotexts = None, None, None
    else:
        wedges, texts, autotexts = ax2.pie(member_totals, labels=member_names, 
                                            autopct=format_autotext)
        ax2.set_anchor("S")

    for ax in (ax1, ax2):
        ax.set_facecolor('#1E1F22')
        ax.tick_params(axis='x', labelrotation=40.0)
        ax.tick_params(axis='both', colors='#DBDEE1')
        ax.grid(True, color="#6A6D70")   
        ax.set_frame_on(True)
        for spine in ax.spines.values():
            spine.set_color("#DBDEE1") 
            spine.set_visible(True)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")
        if wedges: 
            colors = [wedge.get_facecolor() for wedge in wedges]
        else: 
            colors = ['lightblue']
        if texts == None: continue
        for text in texts:
            text.set_color("white")
            text.set_fontsize(10)
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")

    ax2.set_aspect('equal', adjustable='datalim')
    ax1.bar(member_names, member_totals, color=colors)
 
    if fig is not None:
        return fig
    else:
        return ax1, ax2 

def yapall_fig(interaction:None, start_date, end_date, x, y, ax1:None, ax2:None, guild:None):
    aspect = [16, 9]
    fig = None
    if ax1 is None and ax2 is None: 
        fig, (ax1, ax2) = plt.subplots(x, y, figsize=(aspect[x-1], aspect[y-1]), facecolor='#1E1F22', layout='constrained')
    ax1.set_ylabel("message counts", color='#DBDEE1')
    ax2.set_ylabel("message increments", color='#DBDEE1') 

    if guild == None:
        guild = interaction.guild
        guild_id = guild.id 
    else: guild_id = guild.id

    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)

    cursor.execute("""
        SELECT user_id, date, messages
        FROM user_messages
        WHERE guild_id = ?
          AND date BETWEEN ? AND ?
        ORDER BY date ASC
    """, (guild_id, start_date, end_date))
    rows = cursor.fetchall()

    date_list = []
    temp = start
    while temp <= end:
        date_list.append(temp.isoformat())
        temp += datetime.timedelta(days=1)

    time_end = (end + datetime.timedelta(days=1)).isoformat()
    time = np.arange(start_date, time_end, dtype='datetime64[D]')

    user_counts = defaultdict(dict)
    for u_id, d_str, count in rows:
        user_counts[u_id][d_str] = count

    has_data = False
    for u_id, counts in user_counts.items():
        total = 0
        total_msgs = []
        msg_increments = []
        for d_str in date_list:
            msgs = counts.get(d_str, 0)
            total += msgs
            total_msgs.append(total)
            msg_increments.append(msgs)

        if total > 0:
            has_data = True
            member = guild.get_member(u_id) if guild else None
            label = member.display_name if member else f"User {u_id}"
            ax1.plot(time, total_msgs, label=label)
            ax2.plot(time, msg_increments, label=label)

    if not has_data:
        ax1.text(0.5, 0.5, "No messages in this period", ha="center", va="center", color="white", fontsize=14)
        ax2.text(0.5, 0.5, "No messages in this period", ha="center", va="center", color="white", fontsize=14)

    for ax in (ax1, ax2):
        ax.set_facecolor('#1E1F22')
        ax.tick_params(axis='x', labelrotation=40.0)
        ax.tick_params(axis='both', colors='#DBDEE1')
        ax.set_xlabel("Dates", color='#DBDEE1')   
        ax.grid(True, color="#6A6D70") 
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            legend = ax.legend()
            legend.get_frame().set_facecolor("#1E1F22") 
            legend.get_frame().set_edgecolor("#DBDEE1")
            for text in legend.get_texts():
                text.set_color("#DBDEE1")
        for spine in ax.spines.values():
            spine.set_color("#DBDEE1") 
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")

    if fig is not None:
        return fig
    else:
        return ax1, ax2

@tree.command(
    name="yapone",
    description="Show the message count of an user over time. Dates should be YYYY-MM-DD"
)
async def yapone(interaction:discord.Interaction, member:discord.Member, start_date:str, end_date:str):
    await interaction.response.defer()

    guild_id = interaction.guild.id 
    user_id = member.id

    try:
        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
    except ValueError:
        await interaction.followup.send(f"Wrong dates, {interaction.user.name}! Type them out in YYYY-MM-DD format.")
        return

    data = {}
    cursor.execute("""
        SELECT date, messages
        FROM user_messages
        WHERE guild_id = ?
        AND user_id = ?
        AND date BETWEEN ? AND ?
    """,
    (guild_id, user_id, start_date, end_date))
    dates = cursor.fetchall()

    tempstart = start
    while tempstart <= end:
        data[tempstart] = 0
        tempstart += datetime.timedelta(days=1)

    total = 0 
    total_msgs = []
    msg_increments = []

    tempdates = list(data.keys())
    for date in dates:
        dateobj = datetime.date.fromisoformat(date[0])
        if dateobj in tempdates:
            data[dateobj] = date[1] 
    
    for date in tempdates:
        messages = data[date]
        total += messages 
        total_msgs.append(total)
        msg_increments.append(messages)

    time_end = (end + datetime.timedelta(days=1)).isoformat()
    time = np.arange(start_date, time_end, dtype='datetime64[D]') 

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 9), facecolor='#1E1F22', layout='constrained')
    ax1.set_facecolor('#1E1F22')
    ax2.set_facecolor('#1E1F22')

    ax1.set_ylabel(f"{member.display_name}'s message count", color='#DBDEE1')
    ax1.plot(time, total_msgs) 
    ax2.set_ylabel(f"{member.display_name}'s message increments", color='#DBDEE1')
    ax2.plot(time, msg_increments) 

    for ax in (ax1, ax2):
        ax.tick_params(axis='x', labelrotation=40.0)
        ax.tick_params(axis='both', colors='#DBDEE1')
        ax.set_xlabel("Dates", color='#DBDEE1')   
        ax.grid(True, color="#6A6D70")
        for spine in ax.spines.values():
            spine.set_color("#DBDEE1") 
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")

    fig.savefig("yapometer.png", dpi=300)
    file = discord.File("yapometer.png")
    embed = discord.Embed(title="Results",
                          description=f"{member.mention}'s yapping data ({start_date} to {end_date})")
    embed.set_image(url="attachment://yapometer.png")
    await interaction.followup.send(embed=embed, file=file)
    return

@tree.command(
    name="yapall",
    description="Show the message count of all users over time. Dates should be YYYY-MM-DD"
)
async def yapall(interaction:discord.Interaction, start_date:str, end_date:str):
    await interaction.response.defer()

    try:
        fig = yapall_fig(interaction, start_date, end_date, 1, 2)
    except ValueError:
        await interaction.followup.send(f"Wrong dates, {interaction.user.name}! Type them out in YYYY-MM-DD format.")
        return

    fig.savefig("yapometer.png", dpi=300)
    file = discord.File("yapometer.png")
    embed = discord.Embed(title="Results",
                          description=f"yapping data ({start_date} to {end_date})")
    embed.set_image(url="attachment://yapometer.png")
    await interaction.followup.send(embed=embed, file=file)
    return

@tree.command(
    name="yapshare",
    description="Shows a bar and pie chart of the share of the total " \
    "messages sent by each member"
)
async def yapshare(interaction:discord.Interaction, start_date:str, end_date:str):
    await interaction.response.defer()
    
    try:
        fig = yapshare_fig(interaction, start_date, end_date, 1, 2)
    except ValueError:
        await interaction.followup.send(f"Wrong dates, {interaction.user.name}! Type them out in YYYY-MM-DD format.")
        return

    fig.savefig("yapometer.png", dpi=300)
    file = discord.File("yapometer.png")
    embed = discord.Embed(title="Results",
                            description=f"yapping shares ({start_date} to {end_date})")
    embed.set_image(url="attachment://yapometer.png")
    await interaction.followup.send(embed=embed, file=file)
    return
 
@tree.command(
    name="yapstats",
    description="Shows a dashboard with graphs from all other commands combined"
)
async def yapstats(interaction:discord.Interaction, start_date:str, end_date:str):
    await interaction.response.defer()
    date = datetime.date.today()
    datestr = date.isoformat()

    fig, axes = plt.subplots(2, 3, facecolor='#1E1F22', figsize=(16, 9))
    fig.subplots_adjust(
        left=0.04,
        right=0.99,
        bottom=0.10,
        top=0.98,
        wspace=0.2,
        hspace=0.29
    )
    
    try:
        temp = yapall_fig(interaction, start_date, end_date, 1, 2, axes[0, 0], axes[1, 0])
        temp = yapshare_fig(interaction, start_date, end_date, 1, 2, axes[0, 1], axes[1, 1])
        temp = yapshare_fig(interaction, datestr, datestr, 1, 2, axes[0, 2], axes[1, 2])
    except ValueError:
        await interaction.followup.send(f"Wrong dates, {interaction.user.name}! Type them out in YYYY-MM-DD format.")
        return
    
    fig.savefig("yapometer.png", dpi=300)
    file = discord.File("yapometer.png")
    embed = discord.Embed(title="Results",
                            description=f"yapping shares ({datestr})")
    embed.set_image(url="attachment://yapometer.png")
    await interaction.followup.send(embed=embed, file=file)
    return

@tree.command(
    name="yapdaily",
    description="Configure a text channel to receive daily yapshare reports"
)
async def yapdaily(interaction:discord.Interaction, channel:discord.TextChannel):
    guild_id = interaction.guild.id 
    channel_id = channel.id 

    cursor.execute("""
        INSERT INTO report_channel
        (guild_id, channel_id)
        VALUES (?, ?)
    """,
    (guild_id, channel_id)) 

    connection.commit()

    interaction.response.send_message("Done! The selected channel will receive reports from tomorrow.")

@tasks.loop(hours=24)
async def daily_report():
    cursor.execute("""
        SELECT guild_id, channel_id
        FROM report_channel
    """)
    data = cursor.fetchall() # guild id and channel id nested tuples

    for entry in data:
        guild = client.get_guild(entry[0]) 
        if guild == None: continue
        channel = guild.get_channel(entry[1]) 
        if channel == None: continue

        date = datetime.date.today()
        datestr = date.isoformat()
        fig = yapshare_fig(None, datestr, datestr, 1, 2, None, None, guild)

        fig.savefig("yapometer.png", dpi=300)
        file = discord.File("yapometer.png")
        embed = discord.Embed(title="Results",
                                description=f"yapping shares ({datestr})")
        embed.set_image(url="attachment://yapometer.png")
        await channel.send(embed=embed, file=file)
        return
    
if __name__ == "__main__":
    client.run(os.environ["DISCORD_TOKEN"])