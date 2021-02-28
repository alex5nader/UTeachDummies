import discord
from discord.ext import commands
from asyncio import TimeoutError
import datetime

class Announce (commands.Cog):
    
    def __init__ (self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Bot is online.') 

    @commands.command()
    async def announce(self, ctx):
        # check to make sure that the message being stored is from the person who initiated the command
        def same_author_and_channel(message):
            return message.author == ctx.author and message.channel == ctx.channel

        msgChannel = ''
        # store the message to be sent
        await ctx.send ('Type the announcement that you want to schedule')
        msg = await ctx.bot.wait_for('message', check=same_author_and_channel)
        while msgChannel == '':
        # designate the channel where the message is sent
            await ctx.send('What channel would you like the announcement to be sent in?')
            try:
                tempChannel = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout = 60.0)
            # make sure that the user doesn't take too much time, so they don't accidentally activate this command later
            except TimeoutError:
                await ctx.send('One minute has passed without a reply, cancelling setup.')
                return
            # if the length of this is 0, it means that the user did not mention a channel.
            if len(tempChannel.raw_channel_mentions) == 0:
               await ctx.send('You did not enter a valid channel name. Please try again.')
            # save the channel once it is confirmed to be valid input
            else:
                msgChannel = tempChannel.raw_channel_mentions[0]
        # set the date where the automated announcement is sent
        await ctx.send(f'Your announcement will be sent in <#{msgChannel}>. What day would you like to send it? Please enter in YYYY-MM-DD format.')
        date_entry = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout = 60.0)
        date_string = date_entry.content
        year, month, day = map(int, date_string.split('-'))
        dateToMsg = datetime.date(year, month, day)
        dateToMsg = dateToMsg.strftime("%m/%d/%y") # format the date for readability
        # set the time where the automated announcement is sent
        await ctx.send(f'Your announcement will be sent on {dateToMsg}. What time would you like to send it? Please enter in 24-hour HH:MM format')
        time_entry = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout = 60.0)
        time_string = time_entry.content
        hour, minute = map(int, time_string.split(':'))
        timeToMsg = datetime.time(hour, minute)
        timeToMsg = timeToMsg.strftime("%H:%M") # format the time for readability
        await ctx.send(f'Your announcement will be sent in <#{msgChannel}> at {timeToMsg} on {dateToMsg}.')

def setup(client):
    client.add_cog(Announce(client))