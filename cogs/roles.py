from asyncio import TimeoutError
from typing import Optional, List, Dict

import discord
import firebase_admin
from discord.ext import commands
from discord.ext.commands import guild_only
from dotenv import load_dotenv
from firebase_admin import firestore
from google.cloud import firestore


class Roles(commands.Cog):
	def __init__(self, bot: commands.Bot, firebase: firebase_admin.App):
		self.bot = bot

		self.firebase = firebase
		self.firestore: firestore.Client = firebase_admin.firestore.client(self.firebase)

		self.subscription_message_id_to_category: Dict[int, int] = dict()

		# message ID -> emoji -> role ID
		self.role_cache: Dict[int, Dict[str, int]] = dict()

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
		if payload.user_id == self.bot.user.id:
			return

		if payload.message_id not in self.role_cache:
			self.rebuild_role_cache()
			if payload.message_id not in self.role_cache:
				return
			rebuilt = True
		else:
			rebuilt = False

		emoji = str(payload.emoji)

		if emoji not in self.role_cache[payload.message_id]:
			if rebuilt:
				return
			else:
				self.rebuild_role_cache()
				if emoji not in self.role_cache[payload.message_id]:
					return

		guild = self.bot.get_guild(payload.guild_id)
		member = await guild.fetch_member(payload.user_id)

		role = guild.get_role(self.role_cache[payload.message_id][emoji])

		if role in member.roles:
			await member.remove_roles(role)
		else:
			await member.add_roles(role)

		subscription_msg = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
		await subscription_msg.remove_reaction(payload.emoji, member)

	def rebuild_role_cache(self):
		self.role_cache = dict()
		for category_snap in self.firestore.collection('categories').get():
			category_cache = dict()

			for role_snap in category_snap.reference.collection('roles').get():
				category_cache[role_snap.get('emoji')] = int(role_snap.id)

			self.role_cache[int(category_snap.get('sub_msg'))] = category_cache

	@commands.group()
	@guild_only()
	async def roles(self, ctx: commands.Context):
		if ctx.invoked_subcommand is None:
			# TODO roles help message
			await ctx.send('this should be a help message')

	@roles.command()
	async def create(self, ctx: commands.Context, *, category_name: Optional[str]):
		def same_author_and_channel(message):
			return message.author == ctx.author and message.channel == ctx.channel

		if category_name is None:
			await ctx.send('What should the channel group be called?')
			try:
				msg = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout=60.0)

				category_name = msg.content
			except TimeoutError:
				await ctx.send('One minute has passed without a reply, cancelling setup.')
				return

		names = []

		await ctx.send('Send the name of each role you want (type "done" to confirm, or "cancel" to cancel):')
		while True:
			try:
				msg = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout=60.0)

				if msg.content == "cancel":
					return
				elif msg.content == "done":
					break

				names.append(msg.content)
				await msg.add_reaction('\u2705')  # green checkbox
			except TimeoutError:
				await ctx.send('One minute has passed without a reply, cancelling setup.')
				return

		await ctx.send('Do you want to allow anyone to @ these roles? (y/n)')
		try:
			msg = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout=60.0)

			if msg.content == 'n':
				mentionable = False
			else:
				mentionable = True
		except TimeoutError:
			await ctx.send('One minute has passed without a reply, cancelling setup.')
			return

		await self.perform_create(ctx, category_name, names, mentionable)

	async def perform_create(self, ctx: commands.Context, category_name: str, names: List[str], mentionable: bool):
		reason = f'Role setup by {ctx.author.id}'

		category = await ctx.guild.create_category(
			name=category_name,
			reason=reason,
		)

		category_ref = self.firestore.collection('categories').document(str(category.id))

		subscription_embed = discord.Embed(
			title=f'Roles for {category_name}',
			description='Click the emoji below this message to join or leave its corresponding chat!',
		)
		subscription_embed.set_footer(text='\U0001F53D click below \U0001F53D')

		category_cache = dict()

		for i, name in enumerate(names):
			role = await ctx.guild.create_role(
				name=name,
				mentionable=mentionable,
				reason=reason,
			)

			channel = await ctx.guild.create_text_channel(
				name=name,
				category=category,
				overwrites={
					ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
					role: discord.PermissionOverwrite(read_messages=True),
				},
				reason=reason,
			)

			emoji = f'{i}\uFE0F\u20E3'

			category_cache[emoji] = role.id

			category_ref.collection('roles').document(str(role.id)).set({
				'channel': channel.id,
				'emoji': emoji,
			})

			subscription_embed.add_field(name=f'{emoji} {name}', value='\u200b')

		subscription_msg = await ctx.send(embed=subscription_embed)

		for i in range(len(names)):
			await subscription_msg.add_reaction(f'{i}\uFE0F\u20E3')

		self.role_cache[subscription_msg.id] = category_cache

		category_ref.set({'sub_msg': subscription_msg.id})

		await ctx.send('Setup complete!')

	@roles.command()
	async def delete(self, ctx: commands.Context, *, category: discord.CategoryChannel):
		confirmation = await ctx.send(f'Are you sure you want to delete {category.name}, including all roles and channels?')
		await confirmation.add_reaction('\u2705')
		await confirmation.add_reaction('\u274c')

		def valid_reaction(reaction, user):
			return user == ctx.author and str(reaction.emoji) in {'\u2705', '\u274c'}

		try:
			reaction, user = await ctx.bot.wait_for('reaction_add', check=valid_reaction, timeout=60.0)
			if str(reaction.emoji) == '\u2705':
				await self.perform_delete(ctx, category)
			else:
				await ctx.send('Not deleting.')
		except TimeoutError:
			await ctx.send('One minute has passed without a reply, cancelling setup.')
			return

	async def perform_delete(self, ctx: commands.Context, category: discord.CategoryChannel):
		category_ref = self.firestore.collection('categories').document(str(category.id))

		for role_snap in category_ref.collection('roles').get():
			role = ctx.guild.get_role(int(role_snap.id))
			if role:
				print(role.name)
				await role.delete()
			channel = ctx.guild.get_channel(int(role_snap.get('channel')))
			if channel:
				await channel.delete()
			role_snap.reference.delete()

		await category.delete()
		category_ref.delete()


def setup(bot: commands.Bot):
	load_dotenv()

	try:
		firebase = firebase_admin.initialize_app()
	except ValueError:
		firebase = firebase_admin.get_app()

	bot.add_cog(Roles(bot, firebase))
