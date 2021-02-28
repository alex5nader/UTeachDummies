from collections import namedtuple
from dotenv import load_dotenv
import os

load_dotenv()
PATH = os.getenv("FILE_PATH")

fileType = namedtuple("fileType", "Type Mime")
allTypes = []

file = open(PATH + "Filetypes.txt", "r")
lines = file.readlines()
for line in lines:
	data = line.split("\t")
	type = data[0].strip()
	mime = data[1].strip()
	m = fileType(type, mime)
	allTypes.append(m)
file.close()

def whatFile(filename): 
	filename = filename.strip()
	temp = filename.split(".")[1]
	extension = temp.lower()


	for i in range(len(allTypes)):
		if allTypes[i].Type.strip() == extension.strip():
			return allTypes[i].Mime.strip()
	return "None"



