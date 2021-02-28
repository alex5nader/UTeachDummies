#Built-in Modules
import os

#Packages from pip install
import discord
from dotenv import load_dotenv
from discord.ext import commands


def main():
	# Bot initialization
	client = commands.Bot('UTD')
	client.remove_command("help")

	# Help command: Update as needed
	@client.command()
	async def help(ctx):
		help = discord.Embed(
			color=4359413,
			title='Help',
			description='THE place for managing your UTD courses. Below is a list of commands.'
		)
		help.add_field(name = "search + <filename>", value = "Finds all files and folders with the inputted name.", inline = False)
		help.add_field(name = "createcourse + <Course Name>", value = "Creates a new course folder.", inline = False)
		help.add_field(name = "createprofessor + <Course Name>, <Professor Name>", value = "Creates a professor inside an existing course.", inline = False)
		help.add_field(name = "upload + <Course Name>, <Professor Name", value = "Uploads a compatible file under 8MB to the desired professor.", inline = False)
		help.add_field(name = "download + <Course Name>, <Professor Name>, <filename>", value = "Downloads desired file.", inline = False)
		help.add_field(name = "delete + <Course Name>, <Professor Name>, <filename>", value = "Deletes desired file. Note: users cannot delete folders.", inline = False)
		help.set_footer(text = "Note: filename includes the extension (e.g. '.txt', '.jpeg')", icon_url = help.Empty)
		await ctx.send(embed=help)

	# Loads commands from other python files
	@client.command('load')
	async def load_extension(ctx, file):
		client.load_extension(f"cogs.{file}")

	# Removes commands from other python files
	@client.command('unload')
	async def unload_extension(ctx, file):
		client.unload_extension(f"cogs.{file}")

	@client.command('reload')
	async def reload_extension(ctx, file):
		await unload_extension(ctx, file)
		await load_extension(ctx, file)

	# Reads and creates commands from files listed in the cogs folder
	for file in os.listdir("./cogs"):
		if file.endswith(".py"):
			try:
				client.load_extension(f"cogs.{file[:-3]}")
			except:
				print(f'failed to load cog {file}')

	# Load environment variable (Token)
	load_dotenv()
	TOKEN = os.getenv("CLIENT_TOKEN")

	# Run bot
	client.run(TOKEN)

if __name__ == "__main__":
	main()
