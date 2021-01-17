import datetime
import dateutil.tz
import discord
import discord.ext.commands
import os
from sqlite3 import IntegrityError
from typing import Union
from .scheduler import Scheduler
from .database import get_setting, set_setting, get_schedule, add_guild_meme, get_guild_meme, mark_guild_meme, add_global_meme


bot = discord.ext.commands.Bot(command_prefix=discord.ext.commands.when_mentioned)


def check_guild(ctx):
    if not ctx.guild:
        raise discord.ext.commands.CommandError('This command may only be used in a channel.')
    return True

def check_guild_admin(ctx):
    if not ctx.guild:
        raise discord.ext.commands.CommandError('This command may only be used in a channel.')
    elif ctx.author.id == int(os.environ['DISCORD_SUPER_ADMIN']):
        return True
    elif ctx.author.guild_permissions.administrator:
        return True
    else:
        role_id = int(get_setting(ctx.guild.id, 'admin_role', '0'))
        for role in ctx.author.roles:
            print(role)
            if role.id == role_id:
                return True
        if role_id == 0:
            raise discord.ext.commands.CommandError('This command may only be used by a server admin.')
        else:
            role = discord.utils.get(ctx.guild.roles, id=role_id)
            raise discord.ext.commands.CommandError('This command may only be used by ' + role.name)

def check_guild_submitter(ctx):
    if not ctx.guild:
        raise discord.ext.commands.CommandError('This command may only be used in a channel.')
    elif ctx.author.id == int(os.environ['DISCORD_SUPER_ADMIN']):
        return True
    elif ctx.author.guild_permissions.administrator:
        return True
    else:
        submitter_role_id = int(get_setting(ctx.guild.id, 'submitter_role', '0'))
        submitter_role = discord.utils.get(ctx.guild.roles, id=submitter_role_id)
        if not submitter_role:
            submitter_role = ctx.guild.default_role
        for role in ctx.author.roles:
            print(role)
            if role.id == submitter_role.id:
                return True
        raise discord.ext.commands.CommandError('This command may only be used by ' + submitter_role.name)

def check_super_admin(ctx):
    return ctx.author.id == int(os.environ['DISCORD_SUPER_ADMIN'])

@bot.event
async def on_ready():
    print('Invite: ', generate_invite_link())
    bot.scheduler = Scheduler()
    for guild in bot.guilds:
        reschedule(guild.id)
        #bot.scheduler.schedule(datetime.datetime.now(tz=datetime.timezone.utc), do_post, guild.id)
    bot.loop.create_task(bot.scheduler.run())

@bot.event
async def on_guild_join(guild):
    print(guild)

@bot.event
async def on_guild_remove(guild):
    print(guild)

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(str(error))

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def settings(ctx):
    """Show current settings"""
    em = discord.Embed(title='Settings')
    em.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
    em.add_field(name='Mode', value=get_setting(ctx.guild.id, 'mode', 'Classic'))
    em.add_field(name='Channel', value=get_setting(ctx.guild.id, 'channel', 'Not set'))
    ts = get_schedule(ctx.guild.id)
    em.add_field(name='Schedule', value=ts.strftime('%I:%M %p %Z'))
    emoji_name = get_setting(ctx.guild.id, 'emoji', 'wednesday')
    emoji = discord.utils.get(ctx.guild.emojis, name=emoji_name)
    if not emoji:
        if emoji_name.encode('utf-8')[0] >= 128:
            emoji = emoji_name
        else:
            emoji = '🐸'
    em.add_field(name='Emoji', value=emoji)
    admin_role_id = int(get_setting(ctx.guild.id, 'admin_role', '0'))
    admin_role = discord.utils.get(ctx.guild.roles, id=admin_role_id)
    if admin_role:
        admin_role_name = admin_role.name
    else:
        admin_role_name = 'admins only'
    em.add_field(name='Admin Role', value=admin_role_name)
    submitter_role_id = int(get_setting(ctx.guild.id, 'submitter_role', '0'))
    submitter_role = discord.utils.get(ctx.guild.roles, id=submitter_role_id)
    if not submitter_role:
        submitter_role = ctx.guild.default_role
    em.add_field(name='Submitter Role', value=submitter_role.name)
    await ctx.send(embed=em)

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def schedule(ctx, time: str, timezone: str = None):
    """Set posting schedule and timezone"""
    if timezone:
        tz = dateutil.tz.gettz(timezone)
        if not tz:
            await ctx.send('Unknown timezone')
            raise ValueError('unknown timezone')
        set_setting(ctx.guild.id, 'timezone', timezone)
    parsed_time = datetime.time.fromisoformat(time)
    set_setting(ctx.guild.id, 'time', time)
    ts = get_schedule(ctx.guild.id)
    print(ts)
    await ctx.send('Schedule set to ' + ts.strftime('%I:%M %p %Z'))
    reschedule(ctx.guild.id)

@schedule.error
async def schedule_error(ctx, error):
    print(error)
    await ctx.send('Usage: schedule HH:MM [timezone]')

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def channel(ctx, channel: discord.TextChannel):
    """Set channel to post in"""
    set_setting(ctx.guild.id, 'channel', channel.name)
    await ctx.send('Channel set to ' + channel.mention)

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def emoji(ctx, emoji: Union[discord.Emoji, str]):
    """Set the Wednesday emoji"""
    print(emoji)
    if isinstance(emoji, discord.Emoji):
        set_setting(ctx.guild.id, 'emoji', emoji.name)
    else:
        set_setting(ctx.guild.id, 'emoji', emoji)
    await ctx.send('Emoji set to ' + str(emoji))

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def mode(ctx, mode: str):
    """Set classic, variety, or text mode"""
    print(mode)
    if mode.lower() == 'classic':
        set_setting(ctx.guild.id, 'mode', 'Classic')
        await ctx.send('Mode set to Classic')
    elif mode.lower() == 'variety':
        set_setting(ctx.guild.id, 'mode', 'Variety')
        await ctx.send('Mode set to Variety')
    elif mode.lower() == 'text':
        set_setting(ctx.guild.id, 'mode', 'Text')
        await ctx.send('Mode set to Text')
    else:
        await ctx.send('Unknown mode.\nUsage: mode classic|variety|text')

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def admin_role(ctx, role: discord.Role):
    """Set admin role"""
    set_setting(ctx.guild.id, 'admin_role', role.id)
    await ctx.send('Admin role set to ' + role.name)

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def submitter_role(ctx, role: discord.Role):
    """Set submitter role"""
    set_setting(ctx.guild.id, 'submitter_role', role.id)
    await ctx.send('Submitter role set to ' + role.name)

@bot.command()
async def invite(ctx):
    """Get an invite link to add the bot to your server"""
    await ctx.send(generate_invite_link())

@bot.command()
@discord.ext.commands.check(check_guild_submitter)
async def submit(ctx, url):
    """Submit a Wednesday meme"""
    await ctx.message.delete()
    try:
        add_guild_meme(ctx.guild.id, url, ctx.author.id)
        await ctx.send('*' + ctx.author.name + ' submitted a meme.*')
    except IntegrityError:
        await ctx.send(ctx.author.mention + ' I already have that meme.')

@bot.command()
@discord.ext.commands.check(check_super_admin)
async def add_global(ctx, url):
    try:
        add_global_meme(url, approved=True, submitter=ctx.author.id)
        await ctx.send('Accepted')
    except IntegrityError:
        await ctx.send('I already have that meme.')

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def test_post(ctx):
    chan_name = get_setting(ctx.guild.id, 'channel')
    if not chan_name:
        await ctx.send('No channel is set.')
        return
    channel = discord.utils.get(ctx.guild.channels, name=chan_name)
    if not channel:
        await ctx.send('Channel ' + chan_name + ' not found.')
        return
    await do_post(ctx.guild.id)

async def do_post(guild_id):
    guild = discord.utils.get(bot.guilds, id=guild_id)
    emoji_name = get_setting(guild_id, 'emoji', 'wednesday')
    emoji = discord.utils.get(guild.emojis, name=emoji_name)
    if not emoji:
        if emoji_name.encode('utf-8')[0] >= 128:
            emoji = emoji_name
        else:
            emoji = '🐸'
    chan_name = get_setting(guild_id, 'channel')
    if not chan_name:
        print('No channel is set.')
        reschedule(guild_id)
        return
    channel = discord.utils.get(guild.channels, name=chan_name)
    if not channel:
        print('Channel ' + chan_name + ' not found.')
        reschedule(guild_id)
        return
    mode = get_setting(guild_id, 'mode', 'Classic')
    if mode == 'Classic':
        embed = discord.Embed()
        embed.set_image(url='https://i.kym-cdn.com/photos/images/original/001/091/264/665.jpg')
        msg = await channel.send(embed=embed)
        await msg.add_reaction(emoji)
    elif mode == 'Text':
        msg = await channel.send(str(emoji) + ' It is Wednesday, my dudes.')
        await msg.add_reaction(emoji)
    elif mode == 'Variety':
        url = get_guild_meme(guild_id)
        if not url:
            url = 'https://i.kym-cdn.com/photos/images/original/001/091/264/665.jpg'
        embed = discord.Embed()
        embed.set_image(url=url)
        msg = await channel.send(embed=embed)
        await msg.add_reaction(emoji)
        mark_guild_meme(guild_id, url)
    reschedule(guild_id)

def reschedule(guild_id):
    print(bot.scheduler.heap)
    bot.scheduler.heap = [x for x in bot.scheduler.heap if x.args != (guild_id,)]
    print(bot.scheduler.heap)
    bot.scheduler.schedule(get_schedule(guild_id), do_post, guild_id)

def generate_invite_link():
    perms = discord.Permissions()
    perms.add_reactions = True
    perms.attach_files = True
    perms.embed_links = True
    perms.manage_emojis = True
    perms.send_messages = True
    perms.manage_messages = True
    return discord.utils.oauth_url(os.environ['DISCORD_CLIENT_ID'], perms)
