#Built-in Modules
import os
from collections import namedtuple

#Packages from pip install
from dotenv import load_dotenv

#Loads file path of the Filetypes.txt
load_dotenv()
PATH = os.getenv("FILE_PATH")

#Struct to store fileType
fileType = namedtuple("fileType", "Type Mime")

#Array to store all the fileTypes
allTypes = []

#Opens and reads lines from Filetypes.txt
file = open(PATH + "Filetypes.txt", "r")
lines = file.readlines()

#Creates struct from file and appends to the array
for line in lines:
	data = line.split("\t")
	type = data[0].strip()
	mime = data[1].strip()
	m = fileType(type, mime)
	allTypes.append(m)

#Close file
file.close()

#Returns mimeType of a given filename
def whatFile(filename): 
	#Removes trailing whitespace/newlines/tabs
	filename = filename.strip()

	#Gets the extension part of the file
	temp = filename.split(".")[1]
	extension = temp.lower()

	#Tries to find a matching mimeType
	for i in range(len(allTypes)):

		#If compatible mimeType is found
		if allTypes[i].Type.strip() == extension.strip():
			return allTypes[i].Mime.strip()

	#If file type is incompatible
	return "None"
