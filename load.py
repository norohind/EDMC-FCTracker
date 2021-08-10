# -*- coding: utf-8 -*-
import os
import requests
import threading
import json
import logging

from config import appname

# GPLv3, wrote by a31 aka norohind aka CMDR Aleksey31
# contact: a31#6403 (discord)


VERSION = "0.0.5"
force_beta = False  # override Plugin_settings.SEND_IN_BETA

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class Plugin_settings():
    SEND_IN_BETA = False  # do send messages when play in beta?
    SEND_JUMP_REQUESTS = True
    SEND_JUMPS = True
    SEND_JUMP_CANCELING = True
    SEND_CHANGES_DOCKING_PERMISSIONS = True
    SEND_CHANGES_NAME = True
    SEND_JUMPS_NOT_MY_OWN_CARRIER = True


class Messages():
    """Class that contains all using messages text"""

    # take color in HEX and turn it into decimal
    COLOR_JUMP_REQUEST = "1127128"
    COLOR_JUMP_CANCELLED = "14177041"
    COLOR_JUMP = "130816"
    COLOR_PERMISSION_CHANGE = "5261068"
    COLOR_CHANGE_NAME = "9355388"

    TITLE_JUMP_REQUEST = "Запланирован прыжок"
    TITLE_JUMP = "Прыжок совершён"
    TITLE_JUMP_CANCELLED = "Прыжок отменён"
    TITLE_CHANGE_DOCKING_PERMISSION = "Изменение разрешения на стыковку"
    TITLE_IN_BETA = "Бета версия игры"
    TITLE_CHANGE_NAME = "Изменение имени носителя"

    TEXT_JUMP_REQUEST_BODY_DIFF = " к телу {body}"
    TEXT_JUMP_REQUEST = "Запланирован прыжок носителя {name} в систему {system}"
    TEXT_JUMP = "Носитель {name} совершил прыжок в систему {system}"
    TEXT_JUMP_CANCELLED = "Прыжок носителя {name} отменён"
    TEXT_PERMISSION_CHANGE = """Носитель {name} сменил разрешение на стыковку с {old_permission} на {new_permission}
        Стыковка для преступников была {old_doc_for_crime}, сейчас {new_doc_for_crime}"""
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
        self.callsign = None
        self.location = None
        self.cID = None  # CarrierID (aka MarketID)
        self.docking_permission = None
        self.allow_notorius = None
        self.owner = None
        self.store_key = None


class Embed():
    """Building completed and ready for send embed message for discord. Requeries json lib"""
    def __init__(self, **kwargs):  # color, title, description, username
        self.items = list()

        if kwargs.get('username') is not None:  # we can pass only username
            self.username = kwargs.get('username')
            kwargs.pop('username')
        else:
            self.username = None

        if len(kwargs) == 0:  # we can create new object without creating an item, just do not pass anything (exception is 'username') to constructor
            return

        self.add_item(**kwargs)

    def add_item(self, **kwargs):
        color = kwargs.get('color')
        title = kwargs.get('title')
        description = kwargs.get('description')
        self.items.append(dict(title=title, color=color, description=description))
        return len(self.items) - 1  # index of added item

    def get_message(self):
        """Get full and ready for sending message"""

        if self.username is not None:
            return json.dumps(dict(username=self.username, embeds=self.items))
        else:
            return json.dumps(dict(embeds=self.items))

    def __str__(self):
        return str(self.get_message())

    def update_item(self, item, key, new_value):
        """Replace value under 'key' in 'item'"""
        self.items[item][key] = new_value

    def concatenate_item(self, item, key, new_value):
        """Add to existing value new part"""
        self.items[item][key] = self.items[item][key] + new_value

    def set_username(self, username):
        """Will override current webhook username, for reset call this func with None"""
        self.username = username


class Messages_sender(threading.Thread):
    """Sending message to discord asynchronously, support embeds and content= ways"""
    def __init__(self, message, url, embeds=True):
        threading.Thread.__init__(self)
        self.message = message
        self.url = url
        self.embeds = embeds
        self.start()

    def run(self):
        self.message = str(self.message)
        if not self.embeds:
            self.message = f"content={self.message}"
            self.headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        else:
            self.headers = {'Content-Type': 'application/json'}

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
    options = {
        "all": Messages.DOC_PERMISSION_ALL,
        "none": Messages.DOC_PERMISSION_NONE,
        "friends": Messages.DOC_PERMISSION_FRIENDS,
        "squadron": Messages.DOC_PERMISSION_SQUADRON,
        "squadronfriends": Messages.DOC_PERMISSION_FRIENDS_SQUADRON
    }

    return options.get(permission)  # if key isn't valid then return None


def docking_permission4notorius2text(notorius):
    """As docking_permission2text() but for notorius (crime persons)"""
    # in python True = 1, False = 0. So in our case False = docking disallow, True = docking allow
    return (Messages.DOC_PERMISSION_DISALLOW_NOTORIUS, Messages.DOC_PERMISSION_ALLOW_NOTORIUS)[notorius]


def plugin_start3(plugin_dir):
    logger.info(f"Plugin version: {VERSION}")
    return 'FC dispatcher'


def journal_entry(cmdr, is_beta, system, station, entry, state):
    if is_beta and not Plugin_settings.SEND_IN_BETA:
        return

    if state["Role"] is not None:  # we don't work while you are multicrew passenger
        logger.debug(f"returning because multicrew, role: {state['Role']}")
        return

    event = entry["event"]

    if event == "CarrierStats" and carrier.name is None:
        carrier.name = entry["Name"]
        carrier.cID = entry["CarrierID"]
        carrier.docking_permission = entry["DockingAccess"]
        carrier.allow_notorius = entry["AllowNotorious"]
        carrier.callsign = entry["Callsign"]
        return

    if event in [
            "CarrierJumpRequest",
            "CarrierJumpCancelled",
            "CarrierJump",
            "CarrierDockingPermission",
            "CarrierNameChange"]:

        message = Embed()

        if event == "CarrierJumpRequest" and Plugin_settings.SEND_JUMP_REQUESTS:
            destination_system = entry["SystemName"]
            message.add_item(color=Messages.COLOR_JUMP_REQUEST, title=Messages.TITLE_JUMP_REQUEST)

            try:
                destination_body = entry["Body"]
                message.update_item(
                    item=0,
                    key="description",
                    new_value=Messages.TEXT_JUMP_REQUEST.format(
                        name=carrier.name,
                        system=destination_system) + Messages.TEXT_JUMP_REQUEST_BODY_DIFF.format(body=destination_body))

            except KeyError:
                message.update_item(
                    item=0,
                    key="description",
                    new_value=Messages.TEXT_JUMP_REQUEST.format(
                        name=carrier.name,
                        system=destination_system))

        if event == "CarrierJumpCancelled" and Plugin_settings.SEND_JUMP_CANCELING:
            message.add_item(
                color=Messages.COLOR_JUMP_CANCELLED,
                title=Messages.TITLE_JUMP_CANCELLED,
                description=Messages.TEXT_JUMP_CANCELLED.format(name=carrier.name))

        if event == "CarrierJump" and Plugin_settings.SEND_JUMPS:
            # jump on not your own carrier case
            if carrier.callsign != station:
                # for case when you have your own carrier but now jumping on another one
                if Plugin_settings.SEND_JUMPS_NOT_MY_OWN_CARRIER:
                    remember_carrier_name = carrier.name
                    carrier.name = station
                else:
                    return

            destination_system = entry["StarSystem"]

            message.add_item(color=Messages.COLOR_JUMP, title=Messages.TITLE_JUMP)

            try:
                destination_body = entry["Body"]
                message.update_item(
                    item=0,
                    key="description",
                    new_value=Messages.TEXT_JUMP.format(
                        system=destination_system,
                        name=carrier.name) + Messages.TEXT_JUMP_REQUEST_BODY_DIFF.format(body=destination_body))

            except KeyError:

                message.update_item(
                    item=0,
                    key="description",
                    new_value=Messages.TEXT_JUMP.format(
                        system=destination_system,
                        name=carrier.name))

            if Plugin_settings.SEND_JUMPS_NOT_MY_OWN_CARRIER and carrier.callsign != station:
                carrier.name = remember_carrier_name

        if event == "CarrierDockingPermission" and Plugin_settings.SEND_CHANGES_DOCKING_PERMISSIONS:
            new_permission = entry["DockingAccess"]
            new_doc_for_crime = entry["AllowNotorious"]

            message.add_item(
                title=Messages.TITLE_CHANGE_DOCKING_PERMISSION,
                color=Messages.COLOR_PERMISSION_CHANGE,
                description=Messages.TEXT_PERMISSION_CHANGE.format(
                    name=carrier.name,
                    old_permission=docking_permission2text(carrier.docking_permission),
                    new_permission=docking_permission2text(new_permission),
                    old_doc_for_crime=docking_permission4notorius2text(carrier.allow_notorius),
                    new_doc_for_crime=docking_permission4notorius2text(new_doc_for_crime)))

            carrier.docking_permission = new_permission
            carrier.allow_notorius = new_doc_for_crime

        if event == "CarrierNameChange" and Plugin_settings.SEND_CHANGES_NAME:
            new_name = entry["Name"]
            message.add_item(
                title=Messages.TITLE_CHANGE_NAME,
                description=Messages.TEXT_CHANGE_NAME.format(
                    old_name=carrier.name,
                    new_name=new_name),
                color=Messages.COLOR_CHANGE_NAME)
            carrier.name = new_name

        if is_beta or force_beta:
            message.add_item(title=Messages.TITLE_IN_BETA, description=Messages.TEXT_IN_BETA)

        Messages_sender(message.get_message(), url)  #one Messages_sender instance per message


carrier = Carrier()
