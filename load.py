# -*- coding: utf-8 -*-
import os, requests, threading, json, logging
from config import appname

'''
#GPLv3, wrote by a31 aka norohind aka CMDR Aleksey31
Patch note:
Add support for carrier name change event
Add possibility to disable sending any type of events (checkout class Plugin_settings from 35 line)
Add support for beta
Change way to build message for discord
Add body to jump message if we have it
'''

VERSION="0.0.4"
force_beta=False
'''
for use you must set an url
url can be str or list of strs
for example, single hook:
url="https://discord.com/api/webhooks/1" 
or we can use multiple hooks like:
url1="https://discord.com/api/webhooks/1"
url2="https://discord.com/api/webhooks/2"
url= [ url1, url2 ]
and also we can do it in one line
url = ["https://discord.com/api/webhooks/1", "https://discord.com/api/webhooks/2"]
'''
url="" #set your url(s)

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f'{appname}.{plugin_name}')

#some settings
class Plugin_settings():
	SEND_IN_BETA = False #do send messages when play in beta?
	SEND_JUMP_REQUESTS = True
	SEND_JUMPS = True
	SEND_JUMP_CANCELING = True
	SEND_CHANGES_DOCKING_PERMISSIONS = True
	SEND_CHANGES_NAME = True

class Messages():

	#take color in HEX and turn it into decimal
	COLOR_JUMP_REQUEST = "1127128" 
	COLOR_JUMP_CANCELLED = "14177041"
	COLOR_JUMP = "130816"
	COLOR_PERMISSION_CHANGE = "5261068"
	COLOR_CHANGE_NAME = "9355388"

	TITLE_JUMP_REQUEST = "Запланирован прыжок"
	TITLE_JUMP = "Прыжок совершён"
	TITLE_JUMP_CANCELLED = "Прыжок отменён"
	TITLE_CHANGE_DOCKING_PERMISSION = "Изменение разрешения на стыковку"
	TITLE_IN_BETA= "Бета версия игры"
	TITLE_CHANGE_NAME = "Изменение имени носителя"

	TEXT_JUMP_REQUEST_BODY_DIFF = " к телу {body}"
	TEXT_JUMP_REQUEST = "Запланирован прыжок носителя {name} в систему {system}"
	TEXT_JUMP = "Носитель {name} совершил прыжок в систему {system}"
	TEXT_JUMP_CANCELLED = "Прыжок носителя {name} отменён"
	TEXT_PERMISSION_CHANGE = "Носитель {name} сменил разрешение на стыковку с {old_permission} на {new_permission}\nСтыковка для преступников была {old_doc_for_crime}, сейчас {new_doc_for_crime}"
	TEXT_IN_BETA = "Внимание, данное сообщение относится только к бета версии игры!"
	TEXT_CHANGE_NAME = "Имя носителя изменилось с {old_name} на {new_name}"

	DOC_PERMISSION_ALL = "Для всех"
	DOC_PERMISSION_NONE = "Никто"
	DOC_PERMISSION_FRIENDS = "Только друзья"
	DOC_PERMISSION_SQUADRON = "Только члены эскадрильи"
	DOC_PERMISSION_FRIENDS_SQUADRON = "Только друзья и члены эскадрильи"
	DOC_PERMISSION_ALLOW_NOTORIUS = "Разрешена"
	DOC_PERMISSION_DISALLOW_NOTORIUS = "Запрещена"

class Carrier():
	def __init__(self):
		self.name = None
		self.current_location = None
		self.cID = None #CarrierID (aka MarketID)
		self.docking_permission = None
		self.allow_notorius = None

class embed():
	"""Building completed and ready for send embed message for discord. Requeries json lib"""
	def __init__(self, **kwargs): # color, title, description, postponed
		self.items = list()
		if len(kwargs) == 0: #we can create new object without creating an item of list, just do not pass anything to constructor
			return
		self.add_item(**kwargs)

	def add_item(self, **kwargs):
		color = str(kwargs.get('color'))
		title = str(kwargs.get('title'))
		description = str(kwargs.get('description'))
		self.items.append(dict(title=title, color=color, description=description))

	def get_message(self):
		return json.dumps(dict(embeds=self.items))

	def __str__(self):
		return str(self.get_message())

	def update_item(self, item, key, new_value): #item number, key, new value
		self.items[item][key] = new_value


class Messages_sender(threading.Thread):
	"""Sending message to discord asynchronously, support embeds and content= ways"""
	def __init__(self, message, url, embeds=True):
		threading.Thread.__init__(self)
		self.message = message
		self.url = url
		self.embeds = embeds


	def run(self):
		if not self.embeds:
			self.message=f"content={self.message}"
			self.headers={'Content-Type':'application/x-www-form-urlencoded'}
		else:
			self.headers={'Content-Type':'application/json'}

		if isinstance(self.url, str):
			self.single_url = self.url
			self.send()
			
		elif isinstance(self.url, list):
			for self.single_url in self.url:
				self.send()
		else:
			logger.error(f'Unknown url type {type(self.url)}')

	def send(self):
		r = requests.post(self.single_url, data=self.message.encode('utf-8'), headers=self.headers)
		if r.status_code != 204:
			logger.error(f"Status code: {r.status_code}!") 
			logger.error(r.text)

def docking_permission2text(permission):
	"""Convert one of all/none/friends/squadron/squadronfriends to user friendly message"""
	if permission == "all":
		return Messages.DOC_PERMISSION_ALL
	elif permission == "none":
		return Messages.DOC_PERMISSION_NONE
	elif permission == "friends":
		return Messages.DOC_PERMISSION_FRIENDS
	elif permission == "squadron":
		return Messages.DOC_PERMISSION_SQUADRON
	elif permission == "squadronfriends":
		return Messages.DOC_PERMISSION_FRIENDS_SQUADRON

def docking_permission4notorius2text(notorius):
	"""As docking_permission2text() but for notorius (crime persons)"""
	if notorius == True:
		return Messages.DOC_PERMISSION_ALLOW_NOTORIUS
	elif notorius == False:
		return Messages.DOC_PERMISSION_DISALLOW_NOTORIUS

def plugin_start3(plugin_dir):
	logger.info(f"Plugin version: {VERSION}")
	return 'FC dispatcher'

def journal_entry(cmdr, is_beta, system, station, entry, state):
	if is_beta and not Plugin_settings.SEND_IN_BETA:
		return

	event = entry["event"]
	
	if event == "CarrierStats":
		carrier.name = entry["Name"]
		carrier.cID = entry["CarrierID"]
		carrier.docking_permission = entry["DockingAccess"]
		carrier.allow_notorius = entry["AllowNotorious"]
		return

	if event in ["CarrierJumpRequest", "CarrierJumpCancelled", "CarrierJump", "CarrierDockingPermission", "CarrierNameChanged"]:
		message = embed()

		if event == "CarrierJumpRequest" and Plugin_settings.SEND_JUMP_REQUESTS:
			destination_system = entry["SystemName"]
			message.add_item(color=Messages.COLOR_JUMP_REQUEST, title=Messages.TITLE_JUMP_REQUEST)

			try:
				destination_body = entry["Body"]
				message.update_item(item=0, key="description", new_value=Messages.TEXT_JUMP_REQUEST.format(name=carrier.name, system=destination_system) + Messages.TEXT_JUMP_REQUEST_BODY_DIFF.format(body=destination_body))
			except KeyError:
				message.update_item(item=0, key="description", new_value=TEXT_JUMP_REQUEST.format(name=carrier.name, system=destination_system))

		if event == "CarrierJumpCancelled" and Plugin_settings.SEND_JUMP_CANCELING:
			message.add_item(color=Messages.COLOR_JUMP_CANCELLED, title=Messages.TITLE_JUMP_CANCELLED, description=Messages.TEXT_JUMP_CANCELLED.format(name=carrier.name))


		if event == "CarrierJump" and Plugin_settings.SEND_JUMPS:
			destination_system = entry["StarSystem"]

			message.add_item(color=Messages.COLOR_JUMP, title=Messages.TITLE_JUMP)

			
			try:
				destination_body = entry["Body"]
				message.update_item(item=0, key="description", new_value=Messages.TEXT_JUMP.format(system=destination_system, name=carrier.name) + Messages.TEXT_JUMP_REQUEST_BODY_DIFF.format(body=destination_body))
			except KeyError:
				message.update_item(item=0, key="description", new_value=Messages.TEXT_JUMP.format(system=destination_system, name=carrier.name))


		if event == "CarrierDockingPermission" and Plugin_settings.SEND_CHANGES_DOCKING_PERMISSIONS:
			new_permission = entry["DockingAccess"]
			new_doc_for_crime = entry["AllowNotorious"]

			message.add_item(title=Messages.TITLE_CHANGE_DOCKING_PERMISSION, color=Messages.COLOR_PERMISSION_CHANGE, description=Messages.TEXT_PERMISSION_CHANGE.format(
				name=carrier.name, old_permission=docking_permission2text(carrier.docking_permission), new_permission=docking_permission2text(new_permission),
			 	old_doc_for_crime=docking_permission4notorius2text(carrier.allow_notorius), new_doc_for_crime=docking_permission4notorius2text(new_doc_for_crime)))
			carrier.docking_permission = new_permission
			carrier.allow_notorius = new_doc_for_crime

		if event == "CarrierNameChanged" and Plugin_settings.SEND_CHANGES_NAME:
			new_name = entry["Name"]
			message.add_item(title=Messages.TITLE_CHANGE_NAME, description=Messages.TEXT_CHANGE_NAME.format(old_name=carrier.name, new_name=new_name), color=COLOR_CHANGE_NAME)
			carrier.name = new_name

		if is_beta or force_beta:
			message.add_item(title=Messages.TITLE_IN_BETA, description=Messages.TEXT_IN_BETA)

		Messages_sender(message.get_message(), url).start() #one Messages_sender instance per message

carrier = Carrier()
