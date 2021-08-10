import logging, plug
import os, requests, threading, json, time
from config import appname

#GPLv3, wrote by a31 aka norohind aka CMDR Aleksey31


VERSION="0.0.3"

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

class Carrier():
	def __init__(self):
		self.name = None
		self.current_location = None
		self.cID = None #CarrierID (aka MarketID)
		self.docking_permission = None
		self.allow_notorius = None

class Messages():

	#take color in HEX and turn it into decimal
	JUMP_REQUEST_COLOR="1127128" 
	JUMP_CANCELLED_COLOR="14177041"
	JUMP_COLOR="130816"
	PERMISSION_CHANGE_COLOR="5261068"

	EMBEDS_TEMPLATE = '{"embeds":[{"title": null,"color": null,"description": null}]}'

	TITLE_JUMP_REQUEST = "Запланирован прыжок"
	TITLE_JUMP_COMPLETE = "Прыжок совершён"
	TITLE_JUMP_CANCELLED = "Прыжок отменён"
	TITLE_CHANGE_DOCKING_PERMISSION = "Изменение разрешения на стыковку"

	TEXT_JUMP_REQUEST_BODY_DIFF = " к телу {body}"
	TEXT_JUMP_REQUEST = "Запланирован прыжок носителя {name} в систему {system}"
	TEXT_JUMP_COMPLETE = "Носитель {name} совершил прыжок в систему {system}"
	TEXT_JUMP_CANCELLED = "Прыжок носителя {name} отменён"
	TEXT_PERMISSION_CHANGE = "Носитель {name} сменил разрешение на стыковку с {old_permission} на {new_permission}\nСтыковка для преступников была {old_doc_for_crime}, сейчас {new_doc_for_crime}"

	DOC_PERMISSION_ALL = "Для всех"
	DOC_PERMISSION_NONE = "Никто"
	DOC_PERMISSION_FRIENDS = "Только друзья"
	DOC_PERMISSION_SQUADRON = "Только члены эскадрильи"
	DOC_PERMISSION_FRIENDS_SQUADRON = "Только друзья и члены эскадрильи"
	DOC_PERMISSION_ALLOW_NOTORIUS = "Разрешена"
	DOC_PERMISSION_DISALLOW_NOTORIUS = "Запрещена"

class Messages_sender(threading.Thread):
	def __init__(self, message, url, embeds=True):
		threading.Thread.__init__(self)
		self.message = message
		self.url = url
		self.embeds = embeds

	
	def run(self):
		if self.url == None or len(url) == 0:
			logger.error("No url, you must set at least one url")
			time.sleep(2)
			plug.show_error("You must set at least one url")
			return
		if len(self.message) == 0:
			logger.error("empty message")
			time.sleep(2)
			plug.show_error("empty message")

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
			logger.error(f'unknown url type {type(self.url)}')

	def send(self):
		r = requests.post(self.single_url, data=self.message.encode('utf-8'), headers=self.headers)
		if r.status_code != 204:
			logger.error(f"status code: {r.status_code}!") 
			logger.error(r.text)

def docking_permission2text(permission):
	"""convert one of all/none/friends/squadron/squadronfriends to normal text for user friendly messages"""
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
	"""as docking_permission2text but for notorius"""
	if notorius == True:
		return Messages.DOC_PERMISSION_ALLOW_NOTORIUS
	elif notorius == False:
		return Messages.DOC_PERMISSION_DISALLOW_NOTORIUS

def plugin_start3(plugin_dir):
	logger.info(f"Plugin version: {VERSION}")
	return 'FC dispatcher'

def journal_entry(cmdr, is_beta, system, station, entry, state):
	event = entry["event"]
	
	if event == "CarrierStats":
		carrier.name = entry["Name"]
		carrier.cID = entry["CarrierID"]
		carrier.docking_permission = entry["DockingAccess"]
		carrier.allow_notorius = entry["AllowNotorious"]
		return

	if event in ["CarrierJumpRequest", "CarrierJumpCancelled", "CarrierJump", "CarrierDockingPermission"]:
		message = json.loads(Messages.EMBEDS_TEMPLATE)
		

		if event == "CarrierJumpRequest":
			destination_system = entry["SystemName"]

			message["embeds"][0]["title"] = Messages.TITLE_JUMP_REQUEST
			message["embeds"][0]["color"] = Messages.JUMP_REQUEST_COLOR
			message["embeds"][0]["description"] = Messages.TEXT_JUMP_REQUEST.format(name=carrier.name, system=destination_system)

			try:
				destination_body = entry["Body"]
				message["embeds"][0]["description"] += Messages.TEXT_JUMP_REQUEST_BODY_DIFF.format(body=destination_body)
			except KeyError:
				pass

		if event == "CarrierJumpCancelled":

			message["embeds"][0]["title"] = Messages.TITLE_JUMP_CANCELLED
			message["embeds"][0]["color"] = Messages.JUMP_CANCELLED_COLOR
			message["embeds"][0]["description"] = Messages.TEXT_JUMP_CANCELLED.format(name=carrier.name)

		
		if event == "CarrierJump":
			destination_system = entry["StarSystem"]

			message["embeds"][0]["title"] = Messages.TITLE_JUMP_COMPLETE
			message["embeds"][0]["color"] = Messages.JUMP_COLOR
			message["embeds"][0]["description"] = Messages.TEXT_JUMP_COMPLETE.format(system=destination_system, name=carrier.name)

		if event == "CarrierDockingPermission":
			new_permission = entry["DockingAccess"]
			new_doc_for_crime = entry["AllowNotorious"]

			message["embeds"][0]["title"] = Messages.TITLE_CHANGE_DOCKING_PERMISSION
			message["embeds"][0]["color"] = Messages.PERMISSION_CHANGE_COLOR
			message["embeds"][0]["description"] = Messages.TEXT_PERMISSION_CHANGE.format(name=carrier.name, old_permission=docking_permission2text(carrier.docking_permission), new_permission=docking_permission2text(new_permission),
			 old_doc_for_crime=docking_permission4notorius2text(carrier.allow_notorius), new_doc_for_crime=docking_permission4notorius2text(new_doc_for_crime))
			carrier.docking_permission = new_permission
			carrier.allow_notorius = new_doc_for_crime

		Messages_sender(json.dumps(message), url).start() #one Messages_sender instance per message

carrier = Carrier()
