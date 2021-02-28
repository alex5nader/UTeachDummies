import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import io
import asyncio
import time
from cogs.Utility_Files.goog import Create_Service
from cogs.Utility_Files.filetype import whatFile
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from collections import namedtuple

#Import environment variables
load_dotenv()
DOWNLOAD_PATH = os.getenv('DOWNLOAD_PATH')
FILE_DESTINATION = os.getenv('FILE_DESTINATION')

#Imports Client Secrets and creates the call to the API
CLIENT_SECRET = "./cogs/Client_Secret.json"
API_NAME = "drive"
API_VERSION = "v3"
SCOPE = ["https://www.googleapis.com/auth/drive"]
call = Create_Service(CLIENT_SECRET, API_NAME, API_VERSION, SCOPE)

#Stores file properties
fileInfo = namedtuple("fileInfo", "Name ID WebViewLink Parents")

#Seaches for all filenames
def search(filename, isFolder):
	#List of results
	results = []
	
	#Placeholder variable for the first instance of a match
	page_token = None

	#Loops through the entire drive
	while True:
		#If what we are searching for is a folder
		if isFolder == True:
			response = call.files().list(spaces='drive', fields='nextPageToken, files(id, name)', pageToken=page_token, q = f"mimeType = 'application/vnd.google-apps.folder' and name = '{filename}' and trashed = False").execute()
		else:
			response = call.files().list(q = f"name contains '{filename}' and trashed = False", fields='nextPageToken, files(id, name, webViewLink, parents)', pageToken=page_token).execute()
		
		#Appending results to the results array
		for file in response.get('files', []):
			results.append(file)
		
		#Moving to next instance
		page_token = response.get('nextPageToken', None)
		
		#Once the search ends
		if page_token is None:
			break

	#Return list of results
	return results

#Searches for a name given file ID
def searchByID(file_id):
	page_token = None

	while True:
		response = call.files().list(q = f"trashed = False", fields='nextPageToken, files(id, name, webViewLink, parents)', pageToken=page_token).execute()
		for file in response.get('files', []):
			if file.get('id') == file_id:
				id = file.get('id')
				name = file.get('name')
				web = file.get('webViewLink')
				parent = file.get('parents')
				m = fileInfo(name, id, web, parent)
				return m
		
		#Moving to next instance
		page_token = response.get('nextPageToken', None)
		
		#Once the search ends
		if page_token is None:
			break

#Seaches for professor of a given course
def searchSection(parent, foldername):
	#Array to return
	toReturn = []

	#Course name to be found
	results = search(parent, True)

	#If the course was the only instance
	if len(results) == 1:
		#Getting parent ID
		parentID = results[0].get('id')
		page_token = None

		#Searches for every instance of the professor name
		while True:
			response = call.files().list(q = f"name = '{foldername.capitalize()}' and '{parentID}' in parents and trashed = False", fields = 'nextPageToken, files(id, name)', pageToken = page_token).execute()
			for file in response.get('files', []):
				toReturn.append(file)

			page_token = response.get('nextPageToken', None)

			if page_token is None:
				break
	#Returns results
	return toReturn

def searchFile(parent, filename):
	#Array to return
	toReturn = []

	#Course name to be found
	results = search(parent, True)

	#If the course was the only instance
	if len(results) == 1:
		#Getting parent ID
		parentID = results[0].get('id')
		page_token = None

		#Searches for every instance of the professor name
		while True:
			response = call.files().list(q = f"name = '{filename}' and '{parentID}' in parents and trashed = False and mimeType != 'application/vnd.google-apps.folder'", fields = 'nextPageToken, files(id, name, webViewLink)', pageToken = page_token).execute()
			for file in response.get('files', []):
				toReturn.append(file)

			page_token = response.get('nextPageToken', None)

			if page_token is None:
				break
	#Returns results
	return toReturn

#Creates folder
def createFolder(folderName, parent):
	#If we are creating a course
	if parent == None:
		#Creates Folder
		file_metadata = {
			'name': folderName.upper(),
			'mimeType': 'application/vnd.google-apps.folder'
		}

		#Inserts folder into root of the Drive
		file = call.files().create(body=file_metadata, fields = 'webViewLink, id').execute()

		#Setting permissions
		perms = {
			"role": "reader",
			"type": "anyone"
		}

		#Makes the folder a public one
		call.permissions().create(fileId = file.get('id'), body = perms).execute()
		return file.get("webViewLink")
	else:
		#Finds parent
		allResults = search(parent, True)

		#If there is exactly 1 result, section is created
		if len(allResults) == 1:
			file_metadata = {
				'name': folderName.capitalize(),
				'parents': [allResults[0].get('id')],
				'mimeType': 'application/vnd.google-apps.folder'
			}

			#Makes folder
			file = call.files().create(body=file_metadata,fields = 'webViewLink, id').execute()

			#Setting permissions
			perms = {
				"role": "reader",
				"type": "anyone"
			}

			#Makes folder a public one
			call.permissions().create(fileId = file.get('id'), body = perms).execute()
			return file.get("webViewLink")

#File management class
class filemanagement(commands.Cog):
	#Initializes commands
	def __init__(self, client):
		self.client = client

	#Search for a specific file in the entire Drive
	@commands.command(aliases = ["sf"])
	async def searchfile(self, ctx, *, filename):
		matches = search(filename.strip(), False)

		#If nothing was found
		if len(matches) == 0:
			await ctx.send("No files or folders found")
		#If one match was found
		elif len(matches) == 1:
			path = ""
			p = matches[0].get('parents')
			Prof = searchByID(p[0])
			if Prof != None:
				path += Prof.Name
				Course = searchByID(Prof.Parents[0])
				if Course != None:
					path = Course.Name + " -> " + path
					exact = discord.Embed(
						colour = discord.Colour(15454004),
						title = Prof.Name,
						description = f"Path: {path}"
					)
					exact.add_field(name = "Link", value = Course.WebViewLink, inline = False)
				else:
					exact = discord.Embed(
						colour = discord.Colour(15454004),
						title = Prof.Name,
						description = f"Path: {path}"
					)
					exact.add_field(name = "Link", value = Prof.WebViewLink, inline = False)
			else:
				exact = discord.Embed(
					colour = discord.Colour(15454004),
					title = matches[0].get("name"),
					description = "Course Folder"
				)
				exact.add_field(name = "Link", value = matches[0].get('webViewLink'),inline = False)

			await ctx.send(embed = exact)
		else:
			#Embed created
			result = discord.Embed(
				colour= discord.Colour(15454004),
				title = "Matches",
			)

			#Depending upon the file type, different fields will be added
			for item in matches:
				p = item.get('parents')
				if p != None:
					Prof = searchByID(p[0])
					if Prof != None:
						Course = searchByID(Prof.Parents[0])
						if Course != None:
							result.add_field(name = Course.Name + " - " + Prof.Name, value = f'{item.get("name")} link: {item.get("webViewLink")}', inline = False)
						else:
							result.add_field(name = Prof.Name, value = f'{item.get("name")} link: {item.get("webViewLink")}', inline = False)
					else:
						result.add_field(name = "Course Name and Link:", value = f'{item.get("name")} link: {item.get("webViewLink")}', inline = False)

			await ctx.send(embed = result)

	@commands.command(aliases = ["cp"])
	async def createprofessor(self, ctx, *, foldername):
		path = foldername.split(",")
		if len(path) == 2:
			list = searchSection(path[0].strip(), path[1].strip())
			if len(list) >= 1:
				await ctx.send("Professor already created")
			else:
				link = createFolder(path[1].strip(), path[0].strip())
				if link == None:
					await ctx.send("Professor addition failed. Perhaps the course hasn't been added yet?")
				else:
					success = discord.Embed(
						colour = discord.Colour(16743168),
						title = "Success",
						description = f"Link for your professor, {path[1].capitalize()}, is down below."
					)
					success.add_field(name = "Link:", value = link, inline = False)

					await ctx.send(embed = success)
		else:
			await ctx.send("Invalid format")

	@commands.command(aliases = ["cc"])
	async def createcourse(self, ctx, *, foldername):
		if "," in foldername:
			await ctx.send("Invalid format. Perhaps you meant to say UTDcreateprofessor?")
		else:
			ifDupe = search(foldername, True)
			if len(ifDupe) >= 1:
				await ctx.send("Course already created")
			else:
				link = createFolder(foldername, None)
				success = discord.Embed(
					colour = discord.Colour(16743168),
					title = "Success",
					description = f"Link for your course, {foldername.upper()}, is down below."
				)
				success.add_field(name = "Link:", value = link, inline = False)
				await ctx.send(embed = success)

	@commands.command(aliases = ["attach"])
	async def upload(self, ctx, *, path):
		if "," not in path:
			await ctx.send("Invalid path.")
		else:
			folders = path.split(",")
			if len(folders) != 2:
				await ctx.send("Invalid path.")
			else:
				toUpload = searchSection(folders[0].strip(), folders[1].strip())
				destination = toUpload[0].get('id')

				def check(m):
					return len(m.attachments) == 1 and m.author == ctx.author
				await ctx.send('Now attach a file.')
				try:
					msg = await ctx.bot.wait_for('message', timeout = 60.0, check = check)
					await msg.attachments[0].save(msg.attachments[0].filename)

					mime = whatFile(msg.attachments[0].filename)
					if mime != "None":
						file_metadata = {
							'name': msg.attachments[0].filename,
							'parents': [destination]
						}
						print(msg.attachments[0].filename)
						media = MediaFileUpload(msg.attachments[0].filename, mimetype = mime, resumable = True)
						file = call.files().create(body = file_metadata, media_body = media, fields = 'id, webViewLink, parents').execute()
						perms = {
							"role": "reader",
							"type": "anyone"
						}
						#Makes file a public one
						call.permissions().create(fileId = file.get('id'), body = perms).execute()
						await msg.add_reaction("✅")
					else:
						await ctx.send("Invalid file type.")

					await asyncio.sleep(10)
					os.remove(FILE_DESTINATION + f'/{msg.attachments[0].filename}')

				except TimeoutError:
					await ctx.send("Time's up!")

	@commands.command()
	async def download(self, ctx, *, path):
		if "," not in path:
			await ctx.send("Invalid path.")
		else:
			folders = path.split(",")
			if len(folders) != 3:
				await ctx.send("Invalid path.")
			else:
				toDownload = searchSection(folders[0].strip(), folders[1].strip())
				destination = toDownload[0].get('name')
				fileToGet = searchFile(destination, folders[2].strip())
				if len(fileToGet) == 0:
					await ctx.send("File not found.")
				else:
					request = call.files().get_media(fileId = fileToGet[0].get('id'))

					fh = io.BytesIO()
					downloader = MediaIoBaseDownload(fd = fh, request = request)

					done = False
					while not done:
						done = downloader.next_chunk()

					fh.seek(0)

					with open(os.path.join(fileToGet[0].get('name')), 'wb') as f:
						f.write(fh.read())
						f.close()
					try:
						file = discord.File(FILE_DESTINATION + fileToGet[0].get('name'),filename = fileToGet[0].get('name'))
						await ctx.send(file = file)
						file.close()

						await asyncio.sleep(10)
						os.remove(FILE_DESTINATION + fileToGet[0].get('name'))
					except:
						await ctx.send(f"File size is too big. You must manually download it here: {fileToGet[0].get('webViewLink')}")

	@commands.command(aliases = ["del"])
	async def delete(self, ctx, *,path):
		if "," not in path:
			await ctx.send("Invalid path.")
		else:
			folders = path.split(",")
			if len(folders) != 3:
				await ctx.send("Invalid path.")
			else:
				toDelete = searchSection(folders[0].strip(), folders[1].strip())
				destination = toDelete[0].get('name')
				fileToGet = searchFile(destination, folders[2].strip())
				if len(fileToGet) == 0:
					await ctx.send("File not found.")
				else:
					request = call.files().delete(fileId = fileToGet[0].get('id')).execute()
					await ctx.message.add_reaction("✅")


#PUT THIS AT THE END OF YOUR PYTHON FILE
def setup(client):
	client.add_cog(filemanagement(client))
