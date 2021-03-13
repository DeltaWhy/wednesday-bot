import datetime
import dateutil.tz
import discord
import discord.ext.commands
import logging
import os
import traceback
from sqlite3 import IntegrityError
from typing import Union
from .scheduler import Scheduler
from .database import get_setting, set_setting, get_schedule, add_guild_meme, get_guild_meme, mark_guild_meme, add_global_meme, log_event


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
            logging.debug(role)
            if role.id == role_id:
                return True
        if role_id == 0:
            raise discord.ext.commands.CommandError('This command may only be used by a server admin.')
        else:
            role = discord.utils.get(ctx.guild.roles, id=role_id)
            raise discord.ext.commands.CommandError('This command may only be used by ' + role.name)

def check_guild_permissions(ctx):
    if not ctx.guild:
        raise discord.ext.commands.CommandError('This command may only be used in a channel.')
    else:
        perms = ctx.guild.me.guild_permissions
        if perms.manage_messages:
            return True
        raise discord.ext.commands.CommandError('The bot needs the "manage messages" permission for this command.')

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
            logging.debug(role)
            if role.id == submitter_role.id:
                return True
        raise discord.ext.commands.CommandError('This command may only be used by ' + submitter_role.name)

def check_super_admin(ctx):
    return ctx.author.id == int(os.environ['DISCORD_SUPER_ADMIN'])

@bot.event
async def on_ready():
    logging.info('%s %s', 'Invite: ', generate_invite_link())
    bot.scheduler = Scheduler()
    if 'RESUME_TIME' in os.environ:
        resume_time = datetime.datetime.fromisoformat(os.environ['RESUME_TIME'])
    else:
        resume_time = None
    for guild in bot.guilds:
        log_event('guild_ready', {'guild_id': guild.id, 'name': guild.name, 'description': guild.description,
            'member_count': guild.member_count, 'region': str(guild.region), 'text_channel_count': len(guild.text_channels),
            'voice_channel_count': len(guild.voice_channels)})
        reschedule(guild.id, resume_time)
        try:
            await create_wednesday_emoji(guild)
        except:
            traceback.print_exc()
    bot.loop.create_task(bot.scheduler.run())
    log_event('start', {'resume_time': resume_time})

@bot.event
async def on_guild_join(guild):
    log_event('guild_join', {'guild_id': guild.id, 'name': guild.name, 'description': guild.description,
        'member_count': guild.member_count, 'region': str(guild.region), 'text_channel_count': len(guild.text_channels),
        'voice_channel_count': len(guild.voice_channels)})
    logging.debug(guild)
    reschedule(guild.id)
    try:
        await create_wednesday_emoji(guild)
    except discord.Forbidden:
        pass

@bot.event
async def on_guild_remove(guild):
    log_event('guild_remove', {'guild_id': guild.id})
    logging.debug(guild)

@bot.event
async def on_command_error(ctx, error):
    log_event('command_error', {'error': str(error)})
    await ctx.send(str(error))

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def settings(ctx):
    """Show current settings"""
    log_event('command_settings', {'guild_id': ctx.guild.id})
    if not ctx.guild.me.guild_permissions.embed_links:
        await ctx.send('This bot needs the "embed links" permission.')
        return
    em = discord.Embed(title='Settings')
    em.set_author(name=bot.user.name, icon_url=bot.user.avatar_url)
    em.add_field(name='Mode', value=get_effective_mode(ctx.guild.id))
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
    log_event('command_settings_success', {'guild_id': ctx.guild.id})

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def schedule(ctx, time: str, timezone: str = None):
    """Set posting schedule and timezone"""
    log_event('command_schedule', {'guild_id': ctx.guild.id})
    if timezone:
        tz = dateutil.tz.gettz(timezone)
        if not tz:
            await ctx.send('Unknown timezone')
            raise ValueError('unknown timezone')
        set_setting(ctx.guild.id, 'timezone', timezone)
    parsed_time = datetime.time.fromisoformat(time)
    set_setting(ctx.guild.id, 'time', time)
    ts = get_schedule(ctx.guild.id)
    logging.debug(ts)
    await ctx.send('Schedule set to ' + ts.strftime('%I:%M %p %Z'))
    reschedule(ctx.guild.id)
    log_event('command_schedule_success', {'guild_id': ctx.guild.id})

@schedule.error
async def schedule_error(ctx, error):
    log_event('command_schedule_error', {'guild_id': ctx.guild.id, 'error': str(error)})
    logging.warning(error)
    await ctx.send('Usage: schedule HH:MM [timezone]')

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def channel(ctx, channel: discord.TextChannel):
    """Set channel to post in"""
    log_event('command_channel', {'guild_id': ctx.guild.id})
    set_setting(ctx.guild.id, 'channel', channel.name)
    await ctx.send('Channel set to ' + channel.mention)
    log_event('command_channel_success', {'guild_id': ctx.guild.id, 'channel': channel.name})

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def emoji(ctx, emoji: Union[discord.Emoji, str]):
    """Set the Wednesday emoji"""
    log_event('command_emoji', {'guild_id': ctx.guild.id})
    logging.debug(emoji)
    if isinstance(emoji, discord.Emoji):
        set_setting(ctx.guild.id, 'emoji', emoji.name)
    else:
        set_setting(ctx.guild.id, 'emoji', emoji)
    await ctx.send('Emoji set to ' + str(emoji))
    log_event('command_emoji_success', {'guild_id': ctx.guild.id, 'emoji': str(emoji)})

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def mode(ctx, mode: str):
    """Set classic, variety, or text mode"""
    log_event('command_mode', {'guild_id': ctx.guild.id})
    if not ctx.guild.me.guild_permissions.embed_links:
        await ctx.send('The bot needs the "embed links" permission to use modes besides text.')
        return
    logging.debug(mode)
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
    log_event('command_mode_success', {'guild_id': ctx.guild.id, 'mode': mode})

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def admin_role(ctx, role: discord.Role):
    """Set admin role"""
    log_event('command_admin_role', {'guild_id': ctx.guild.id})
    set_setting(ctx.guild.id, 'admin_role', role.id)
    await ctx.send('Admin role set to ' + role.name)
    log_event('command_admin_role_success', {'guild_id': ctx.guild.id, 'role': role.name})

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def submitter_role(ctx, role: discord.Role):
    """Set submitter role"""
    log_event('command_submitter_role', {'guild_id': ctx.guild.id})
    set_setting(ctx.guild.id, 'submitter_role', role.id)
    await ctx.send('Submitter role set to ' + role.name)
    log_event('command_submitter_role_success', {'guild_id': ctx.guild.id, 'role': role.name})

@bot.command()
async def invite(ctx):
    """Get an invite link to add the bot to your server"""
    log_event('command_invite')
    await ctx.send(generate_invite_link())

@bot.command()
@discord.ext.commands.check(check_guild_permissions)
@discord.ext.commands.check(check_guild_submitter)
async def submit(ctx, url):
    """Submit a Wednesday meme"""
    log_event('command_submit', {'guild_id': ctx.guild.id})
    await ctx.message.delete()
    try:
        add_guild_meme(ctx.guild.id, url, ctx.author.id)
        await ctx.send('*' + ctx.author.name + ' submitted a meme.*')
    except IntegrityError:
        await ctx.send(ctx.author.mention + ' I already have that meme.')
    log_event('command_submit_success', {'guild_id': ctx.guild.id, 'url': url})

@bot.command()
@discord.ext.commands.check(check_super_admin)
async def add_global(ctx, url):
    log_event('command_add_global')
    try:
        add_global_meme(url, approved=True, submitter=ctx.author.id)
        await ctx.send('Accepted')
    except IntegrityError:
        await ctx.send('I already have that meme.')

@bot.command()
@discord.ext.commands.check(check_guild_admin)
async def test_post(ctx):
    log_event('command_test_post', {'guild_id': ctx.guild.id})
    chan_name = get_setting(ctx.guild.id, 'channel')
    if not chan_name:
        await ctx.send('No channel is set.')
        return
    channel = discord.utils.get(ctx.guild.channels, name=chan_name)
    if not channel:
        await ctx.send('Channel ' + chan_name + ' not found.')
        return
    await do_post(ctx.guild.id)
    log_event('command_test_post_success', {'guild_id': ctx.guild.id})

async def do_post(guild_id):
    log_event('do_post', {'guild_id': guild_id})
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
        logging.warning('No channel is set.')
        reschedule(guild_id)
        return
    channel = discord.utils.get(guild.channels, name=chan_name)
    if not channel:
        logging.warning('Channel ' + chan_name + ' not found.')
        reschedule(guild_id)
        return
    mode = get_effective_mode(guild_id)
    if mode == 'Classic':
        embed = discord.Embed()
        embed.set_image(url='https://i.kym-cdn.com/photos/images/original/001/091/264/665.jpg')
        msg = await channel.send(embed=embed)
        try:
            await msg.add_reaction(emoji)
        except discord.Forbidden:
            pass
    elif mode == 'Text':
        msg = await channel.send(str(emoji) + ' It is Wednesday, my dudes.')
        try:
            await msg.add_reaction(emoji)
        except discord.Forbidden:
            pass
    elif mode == 'Variety':
        url = get_guild_meme(guild_id)
        if not url:
            url = 'https://i.kym-cdn.com/photos/images/original/001/091/264/665.jpg'
        embed = discord.Embed()
        embed.set_image(url=url)
        msg = await channel.send(embed=embed)
        try:
            await msg.add_reaction(emoji)
        except discord.Forbidden:
            pass
        mark_guild_meme(guild_id, url)
    reschedule(guild_id)
    log_event('do_post_success', {'guild_id': guild_id, 'mode': mode, 'channel': chan_name, 'emoji': emoji})

def reschedule(guild_id, from_dt = None):
    logging.debug(bot.scheduler.heap)
    bot.scheduler.heap = [x for x in bot.scheduler.heap if x.args != (guild_id,)]
    logging.debug(bot.scheduler.heap)
    bot.scheduler.schedule(get_schedule(guild_id, from_dt), do_post, guild_id)

def generate_invite_link():
    perms = discord.Permissions()
    perms.add_reactions = True
    perms.embed_links = True
    perms.manage_emojis = True
    perms.send_messages = True
    perms.manage_messages = True
    return discord.utils.oauth_url(os.environ['DISCORD_CLIENT_ID'], perms)

async def create_wednesday_emoji(guild):
    emoji = discord.utils.get(guild.emojis, name='wednesday')
    if emoji:
        return
    log_event('create_wednesday_emoji', {'guild_id': guild.id})
    with open(os.path.join(os.path.dirname(__file__), 'wednesday.png'), 'rb') as f:
        image = f.read()
    await guild.create_custom_emoji(name='wednesday', image=image)
    log_event('create_wednesday_emoji_success', {'guild_id': guild.id})

def get_effective_mode(guild_id):
    guild = discord.utils.get(bot.guilds, id=guild_id)
    if not guild.me.guild_permissions.embed_links:
        return 'Text'
    else:
        return get_setting(guild_id, 'mode', 'Classic')
