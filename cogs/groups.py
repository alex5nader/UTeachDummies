from asyncio import TimeoutError
from typing import Optional, List, Dict

import discord
import firebase_admin
from discord.ext import commands
from discord.ext.commands import guild_only
from dotenv import load_dotenv
from firebase_admin import firestore
from google.cloud import firestore


async def prompt_yes_no(author_id: int, bot: commands.Bot, dest: discord.abc.Messageable, prompt: str) -> Optional[
	bool]:
	confirmation = await dest.send(prompt)
	await confirmation.add_reaction('\u2705')
	await confirmation.add_reaction('\u274c')

	def valid_reaction(reaction, user):
		return user.id == author_id and str(reaction.emoji) in {'\u2705', '\u274c'}

	try:
		reaction, user = await bot.wait_for('reaction_add', check=valid_reaction, timeout=60.0)
		if str(reaction.emoji) == '\u2705':
			return True
		else:
			return False
	except TimeoutError:
		return None


class CleanUpWrapper(discord.abc.Messageable):
	def __init__(self, wrapped: discord.abc.Messageable, store):
		self.wrapped = wrapped
		self.store = store

	async def _get_channel(self):
		return await self.wrapped._get_channel()

	async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None,
				   allowed_mentions=None, reference=None, mention_author=None):
		msg = await self.wrapped.send(content=content, tts=tts, embed=embed, file=file, files=files,
									  delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions,
									  reference=reference, mention_author=mention_author)
		self.store.append(msg)
		return msg

	async def trigger_typing(self):
		return await self.wrapped.trigger_typing()

	def typing(self):
		return self.wrapped.typing()

	async def fetch_message(self, id):
		return await self.wrapped.fetch_message(id)

	async def pins(self):
		return await self.wrapped.pins()

	def history(self, *, limit=100, before=None, after=None, around=None, oldest_first=None):
		return self.wrapped.history(limit=limit, before=before, after=after, around=around, oldest_first=oldest_first)


class Groups(commands.Cog):
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

		guild = self.bot.get_guild(payload.guild_id)
		member = await guild.fetch_member(payload.user_id)

		subscription_msg = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)

		emoji = str(payload.emoji)
		if emoji not in self.role_cache[payload.message_id]:
			if rebuilt:
				await subscription_msg.remove_reaction(payload.emoji, member)
				return
			else:
				self.rebuild_role_cache()
				if emoji not in self.role_cache[payload.message_id]:
					await subscription_msg.remove_reaction(payload.emoji, member)
					return

		role = guild.get_role(self.role_cache[payload.message_id][emoji])

		if role in member.roles:
			await member.remove_roles(role)
		else:
			await member.add_roles(role)

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
	async def groups(self, ctx: commands.Context):
		if ctx.invoked_subcommand is None:
			# TODO roles help message
			await ctx.send('this should be a help message')

	@groups.command()
	async def create(self, ctx: commands.Context, *, category_name: Optional[str]):
		to_clean_up = [ctx.message]

		try:
			def same_author_and_channel(message):
				return message.author == ctx.author and message.channel == ctx.channel

			if category_name is None:
				to_clean_up.append(await ctx.send('What should the channel group be called?'))
				try:
					msg = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout=60.0)
					to_clean_up.append(msg)

					category_name = msg.content
				except TimeoutError:
					to_clean_up.append(await ctx.send('One minute has passed without a reply, cancelling setup.'))
					return

			names = []

			to_clean_up.append(
				await ctx.send('Send the name of each group you want (type "done" to confirm, or "cancel" to cancel):'))
			while True:
				try:
					msg = await ctx.bot.wait_for('message', check=same_author_and_channel, timeout=60.0)
					to_clean_up.append(msg)

					if msg.content == "cancel":
						return
					elif msg.content == "done":
						break

					names.append(msg.content)
					await msg.add_reaction('\u2705')  # green checkbox
				except TimeoutError:
					await ctx.send('One minute has passed without a reply, cancelling setup.')
					return

			mentionable = await prompt_yes_no(
				ctx.author.id,
				ctx.bot,
				CleanUpWrapper(ctx, to_clean_up),
				'Do you want to allow anyone to @ these groups?',
			)
			if mentionable is None:
				await ctx.send('One minute has passed without a reply. Cancelling setup.')
				return

			subscription_channel = ctx.channel

			await self.perform_create(ctx, category_name, names, mentionable, subscription_channel)

			await ctx.send('Setup complete!')
		finally:
			for msg in to_clean_up:
				await msg.delete()

	async def perform_create(self, ctx: commands.Context, category_name: str, names: List[str], mentionable: bool,
							 subscription_channel: discord.TextChannel):
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
				'channel': str(channel.id),
				'emoji': emoji,
			})

			subscription_embed.add_field(name=f'{emoji} {name}', value='\u200b')

		subscription_msg = await subscription_channel.send(embed=subscription_embed)

		for i in range(len(names)):
			await subscription_msg.add_reaction(f'{i}\uFE0F\u20E3')

		self.role_cache[subscription_msg.id] = category_cache

		category_ref.set({
			'sub_msg': str(subscription_msg.id),
			'sub_channel': str(subscription_channel.id),
		})

	@groups.command()
	async def delete(self, ctx: commands.Context, *, category: discord.CategoryChannel):
		category_ref = self.firestore.collection('categories').document(str(category.id))
		category_snap = category_ref.get()
		if not category_snap.exists:
			await ctx.send(f"Either there aren't any groups named {category.name}, or I didn't create those groups. "
						   "If there I did create a group with that name, try using its ID instead.")
			return

		confirmation = await prompt_yes_no(
			ctx.author.id,
			ctx.bot,
			ctx,
			f'Are you sure you want to delete {category.name}, including all roles and channels?',
		)
		if confirmation is None:
			await ctx.send('One minute has passed without a reply. Not Deleting.')
			return
		elif confirmation:
			await self.perform_delete(ctx, category, category_ref, category_snap)

			await ctx.send(f'Deleted {category.name}.')
		else:
			await ctx.send('Not deleting.')

	async def perform_delete(self, ctx: commands.Context, category: discord.CategoryChannel, category_ref,
							 category_snap):
		for role_snap in category_ref.collection('roles').get():
			role = ctx.guild.get_role(int(role_snap.id))
			if role:
				await role.delete()
			channel = ctx.guild.get_channel(int(role_snap.get('channel')))
			if channel:
				await channel.delete()

			role_snap.reference.delete()

		subscription_msg_channel = ctx.guild.get_channel(int(category_snap.get('sub_channel')))
		subscription_msg = await subscription_msg_channel.fetch_message(int(category_snap.get('sub_msg')))
		del self.role_cache[subscription_msg.id]
		await subscription_msg.delete()

		await category.delete()
		category_ref.delete()


def setup(bot: commands.Bot):
	load_dotenv()

	try:
		firebase = firebase_admin.initialize_app()
	except ValueError:
		firebase = firebase_admin.get_app()

	bot.add_cog(Groups(bot, firebase))
