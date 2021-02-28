import discord
from discord.ext import commands
from asyncio import TimeoutError

class Announce (commands.Cog):
    
    def __init__ (self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Bot is online.')

    @commands.command()
    async def announce(self, ctx):
        def same_author_and_channel(message):
            return message.author == ctx.author and message.channel == ctx.channel
        msgChannel = ''
        await ctx.send ('Type the announcement that you want to schedule')
        msg = await ctx.bot.wait_for('message', check=same_author_and_channel)
        while msgChannel == '':
            await ctx.send('What channel would you like the announcement to be sent in?')
            try:
                tempChannel = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout = 60.0)
                await ctx.send(tempChannel.raw_channel_mentions)
            except TimeoutError:
                await ctx.send('One minute has passed without a reply, cancelling setup.')
                return
            if len(tempChannel.raw_channel_mentions) == 0:
               await ctx.send('You did not enter a valid channel name. Please try again.')
            else:
                msgChannel = tempChannel.raw_channel_mentions[0]
        await ctx.send(f'Your announcement will be sent in <#{msgChannel}>. What time would you like to send it?')


def setup(client):
    client.add_cog(Announce(client))