# -*- coding: utf-8 -*-
import os
import requests
import threading
import json
import logging
import sys

from config import appname
import tkinter as tk
from tkinter import ttk
import myNotebook as nb
from config import config
from typing import Optional
from ttkHyperlinkLabel import HyperlinkLabel

# GPLv3, wrote by a31 aka norohind aka CMDR Aleksey31
# contact: a31#6403 (discord), a31@demb.design (email)


VERSION = "0.0.6-post"
force_beta = False  # override Plugin_settings.SEND_IN_BETA

DEFAULT_WEBHOOK_NAME_OVERRIDING = '{carrier.name} | {cmdr}'

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f'{appname}.{plugin_name}')

this = sys.modules[__name__]  # For holding module globals, thanks to edsm.py


class FSSSignals_cache:
    def __init__(self):
        self.cache = list()
        self.limit = 101  # 101 just because
        self.block = False

    def add_signal(self, signal_entry, system):

        if self.block:
            return

        if '-' in signal_entry.get('SignalName')[-7:]:  # it's FC, probably
            self.cache.append(dict(callsign=signal_entry['SignalName'][-7:],
                                   system=system))

            if len(self.cache) >= self.limit:  # Don't let it become huge
                self.cache.pop()

    def fc_lookup(self, callsign):
        # logger.debug(f'lookup for {callsign}')
        for signal in self.cache:

            if signal['callsign'] == callsign:

                self.block = True
                self.cache = list()

                # logger.debug(f'lookup for {callsign} successful: {signal["system"]}')
                return signal['system']

        return None


class Dockings_cache:
    def __init__(self):
        self.cache = list()
        self.limit = 101
        self.block = False

    def add_docking(self, entry):

        if self.block:
            return

        event = entry['event']

        if event == 'StartUp' and entry['Docked'] and entry.get('StationType') == 'FleetCarrier':
            self.cache.append(dict(system=entry['StarSystem'], callsign=entry['StationName']))

        if event == 'Location' and entry['Docked'] is True and entry.get('StationType') == 'FleetCarrier':
            self.cache.append(dict(system=entry['StarSystem'], callsign=entry['StationName']))

        if event == 'Docked' and entry['StationType'] == 'FleetCarrier':
            self.cache.append(dict(system=entry['StarSystem'], callsign=entry['StationName']))

        if len(self.cache) >= self.limit:  # Don't let it become huge
            self.cache.pop()

    def fc_lookup(self, callsign):
        # logger.debug(f'lookup for {callsign}')
        for signal in self.cache:

            if signal['callsign'] == callsign:
                self.block = True
                self.cache = list()
                # logger.debug(f'lookup for {callsign} successful: {signal["system"]}')
                return signal['system']

        return None


class Messages:
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
    TEXT_JUMP_FROM = " из системы {from_system}"
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


class Carrier:
    def __init__(self):
        self.name = None
        self.callsign = None
        self.location = None
        self.cID = None  # CarrierID (aka MarketID)
        self.docking_permission = None
        self.allow_notorius = None
        self.owner = None


fsssignals_cache = FSSSignals_cache()
docks_cache = Dockings_cache()
carrier = Carrier()


class Embed:
    """Building completed and ready for send embed message for discord. Requires json lib"""

    def __init__(self, **kwargs):  # color, title, description, username
        self.items = list()

        if kwargs.get('username') is not None:  # we can pass only username
            self.username = kwargs.get('username')
            kwargs.pop('username')
        else:
            self.username = None

        if len(kwargs) == 0:  # we can create new object without creating an item, just do not pass anything (
            # exception is 'username') to constructor
            return

        self.add_item(**kwargs)

    def add_item(self, **kwargs):
        """Add item to the embed"""

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
        """Will override current webhook username, for reset, call this func with None"""
        self.username = username

    def set_footer(self, text, icon_url=None, item=0):
        """Set footer to single embed"""
        self.items[item].update(footer=dict(text=text, icon_url=icon_url))


class Messages_sender(threading.Thread):
    """Sending embed message to discord "asynchronously" """

    def __init__(self, embed, urls):
        threading.Thread.__init__(self)
        self.message = embed
        self.urls = urls
        self.start()

    def run(self):

        if isinstance(self.urls, list):

            for url in self.urls:

                if isinstance(url, str):

                    if url.startswith('https://'):
                        self.send(url)
                    else:
                        logger.debug(f'Skipping {url}')
                else:
                    logger.warning(f'Unknown url type {type(url)}, {url}')
        else:
            logger.warning(f'Unknown urls type {type(self.urls)}, {self.urls}')

    def send(self, single_url):
        headers = {'Content-Type': 'application/json'}
        try:
            r = requests.post(single_url, data=self.message.encode('utf-8'), headers=headers)
            if r.status_code != 204:
                logger.warning(f"Status code: {r.status_code}!")
                logger.warning(r.text)

        except Exception as e:
            logger.warning(f'An exception occurred when sending message to {single_url}; {e}')


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
    logger.info(f"Plugin version: {VERSION}, enabled status: {config.get_bool('FCT_ENABLE_PLUGIN', default=True)}")
    return 'FC tracker'


def journal_entry(cmdr, is_beta, system, station, entry, state):

    event = entry["event"]

    if event == 'FSSSignalDiscovered':
        fsssignals_cache.add_signal(entry, system)
        return

    if event in ['Location', 'StartUp', 'Docking']:
        docks_cache.add_docking(entry)
        return

    if not config.get_bool('FCT_ENABLE_PLUGIN', default=True):
        return

    if force_beta:
        is_beta = True

    if is_beta and not config.get_bool('FCT_SEND_IN_BETA', default=False):
        return

    if state["Role"] is not None:  # we don't work while you are multicrew passenger
        logger.debug(f"Returning because multicrew, role: {state['Role']}")
        return

    if event == "CarrierStats" and carrier.name is None:
        carrier.name = entry["Name"]
        carrier.cID = entry["CarrierID"]
        carrier.docking_permission = entry["DockingAccess"]
        carrier.allow_notorius = entry["AllowNotorious"]
        carrier.callsign = entry["Callsign"]

    if carrier.callsign is not None and carrier.location is None:
        if (location := fsssignals_cache.fc_lookup(carrier.callsign)) is not None:
            carrier.location = location
            logger.debug(f'Updating FC location according to fss cache: "{carrier.location}"')

        elif (location := docks_cache.fc_lookup(carrier.callsign)) is not None:
            carrier.location = location
            logger.debug(f'Updating FC location according to docks cache: "{carrier.location}"')

        else:
            carrier.location = None

    if event in [
        "CarrierJumpRequest",
        "CarrierJumpCancelled",
        "CarrierJump",
        "CarrierDockingPermission",
        "CarrierNameChange"
    ]:

        if carrier.name is None:  # In case edmc was opened when user already has opened Carrier Management window
            logger.debug('carrier.name is None, reopen Carrier Management')
            return

        message = Embed()

        if config.get_bool('FCT_OVERRIDE_WEBHOOKS_NAMES', default=False):
            username = config.get_str('FCT_WEBHOOKS_OVERRIDED_NAME', default=DEFAULT_WEBHOOK_NAME_OVERRIDING)
            username = username.format(carrier=carrier, cmdr=cmdr)
            message.set_username(username=username)

        if event == "CarrierJumpRequest" and config.get_bool('FCT_SEND_JUMP_REQUESTS', default=True):
            destination_system = entry["SystemName"]
            message.add_item(color=Messages.COLOR_JUMP_REQUEST, title=Messages.TITLE_JUMP_REQUEST)

            try:
                destination_body = entry["Body"]

                if destination_system == destination_body:
                    raise KeyError

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

            if carrier.location is not None and config.get_bool('FCT_GUESS_FC_LOCATION', default=False):
                message.concatenate_item(item=0,
                                         key='description',
                                         new_value=Messages.TEXT_JUMP_FROM.format(from_system=carrier.location))

        if event == "CarrierJumpCancelled" and config.get_bool('FCT_SEND_JUMP_CANCELING', default=True):
            message.add_item(
                color=Messages.COLOR_JUMP_CANCELLED,
                title=Messages.TITLE_JUMP_CANCELLED,
                description=Messages.TEXT_JUMP_CANCELLED.format(name=carrier.name))

        if event == "CarrierJump" and config.get_bool('FCT_SEND_JUMPS', default=True):
            if carrier.callsign != station:
                # for case when you have your own carrier but now jumping on someone else's one
                return

            destination_system = entry["StarSystem"]

            message.add_item(color=Messages.COLOR_JUMP, title=Messages.TITLE_JUMP)

            try:
                destination_body = entry["Body"]

                if destination_system == destination_body:
                    raise KeyError

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

            if carrier.location is not None and config.get_bool('FCT_GUESS_FC_LOCATION', default=False):
                message.concatenate_item(item=0,
                                         key='description',
                                         new_value=Messages.TEXT_JUMP_FROM.format(from_system=carrier.location))

            logger.debug(f'Updating FC location according to jump event {carrier.location} -> {destination_system}')
            carrier.location = destination_system  # Update carrier.location by carrier jump

        if event == "CarrierDockingPermission" and \
                config.get_bool('FCT_SEND_CHANGES_DOCKING_PERMISSIONS', default=True):
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

        if event == "CarrierNameChange" and config.get_bool('FCT_SEND_CHANGES_NAME', default=True):
            new_name = entry["Name"]
            message.add_item(
                title=Messages.TITLE_CHANGE_NAME,
                description=Messages.TEXT_CHANGE_NAME.format(
                    old_name=carrier.name,
                    new_name=new_name),
                color=Messages.COLOR_CHANGE_NAME)
            carrier.name = new_name

        if is_beta:
            message.add_item(title=Messages.TITLE_IN_BETA, description=Messages.TEXT_IN_BETA)

        # one Messages_sender instance per message
        Messages_sender(message.get_message(), config.get_list('FCT_DISCORD_WEBHOOK_URLS', default=None))


def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> Optional[tk.Frame]:
    row = 0

    webhooks_urls = config.get_list('FCT_DISCORD_WEBHOOK_URLS', default=[None for i in range(0, 5)])
    enable_plugin = tk.IntVar(value=config.get_bool('FCT_ENABLE_PLUGIN', default=True))
    send_jumps = tk.IntVar(value=config.get_bool('FCT_SEND_JUMPS', default=True))
    send_in_beta = tk.IntVar(value=config.get_bool('FCT_SEND_IN_BETA', default=False))
    send_jump_requests = tk.IntVar(value=config.get_bool('FCT_SEND_JUMP_REQUESTS', default=True))
    send_jump_canceling = tk.IntVar(value=config.get_bool('FCT_SEND_JUMP_CANCELING', default=True))
    send_changes_docking_permissions = tk.IntVar(value=config.get_bool('FCT_SEND_CHANGES_DOCKING_PERMISSIONS',
                                                                       default=True))
    send_changes_name = tk.IntVar(value=config.get_bool('FCT_SEND_CHANGES_NAME', default=True))
    webhooks_names_overriding = tk.IntVar(value=config.get_bool('FCT_OVERRIDE_WEBHOOKS_NAMES', default=False))
    this.webhooks_overrided_name = tk.StringVar(value=config.get_str('FCT_WEBHOOKS_OVERRIDED_NAME',
                                                                     default=DEFAULT_WEBHOOK_NAME_OVERRIDING))
    guess_fc_location = tk.IntVar(value=config.get_bool('FCT_GUESS_FC_LOCATION', default=False))
    frame = nb.Frame(parent)

    nb.Checkbutton(
        frame,
        text="Enable plugin",
        variable=enable_plugin,
        command=lambda: config.set('FCT_ENABLE_PLUGIN', enable_plugin.get())).grid(
        row=row, padx=10, pady=(5, 0), sticky=tk.W)
    row += 1

    nb.Label(
        frame,
        text="Enter your discord webhooks urls here, you can enter up to 5 hooks:").grid(
        row=row, padx=10, pady=(5, 0), columnspan=2, sticky=tk.W)

    HyperlinkLabel(
        frame,
        text='How to get a webhook url',
        background=nb.Label().cget('background'),
        url='https://docs.gitlab.com/ee/user/project/integrations/discord_notifications.html#create-webhook',
        underline=True
    ).grid(row=row, padx=10, pady=(5, 0), column=2, sticky=tk.W)
    row += 1

    this.webhooks_urls = [tk.StringVar(value=one_url) for one_url in webhooks_urls]
    for i in range(0, 5):
        nb.Entry(
            frame,
            textvariable=this.webhooks_urls[i],
            width=115).grid(
            row=row, padx=10, pady=(0, 5), columnspan=4)
        nb.Label(
            frame,
            text=f'#{i + 1}').grid(
            row=row, column=4, sticky=tk.E
        )
        row += 1

    nb.Checkbutton(
        frame,
        text='Send jumps',
        variable=send_jumps,
        command=lambda: config.set('FCT_SEND_JUMPS', send_jumps.get())).grid(
        row=row, column=0, padx=10, pady=(5, 0), sticky=tk.W)

    nb.Checkbutton(
        frame,
        text='Send jump requests',
        variable=send_jump_requests,
        command=lambda: config.set('FCT_SEND_JUMP_REQUESTS', send_jump_requests.get())).grid(
        row=row, column=1, padx=10, pady=(5, 0), sticky=tk.W)

    nb.Checkbutton(
        frame,
        text='Send jump canceling',
        variable=send_jump_canceling,
        command=lambda: config.set('FCT_SEND_JUMP_CANCELING', send_jump_canceling.get())).grid(
        row=row, column=2, padx=10, pady=(5, 0), sticky=tk.W)
    row += 1

    nb.Checkbutton(
        frame,
        text='Send changes name',
        variable=send_changes_name,
        command=lambda: config.set('FCT_SEND_CHANGES_NAME', send_changes_name.get())).grid(
        row=row, column=0, padx=10, pady=(5, 0), sticky=tk.W)

    nb.Checkbutton(
        frame,
        text='Send changes docking permissions',
        variable=send_changes_docking_permissions,
        command=lambda: config.set('FCT_SEND_CHANGES_DOCKING_PERMISSIONS',
                                   send_changes_docking_permissions.get())).grid(
        row=row, column=1, padx=10, pady=(5, 0), sticky=tk.W)
    row += 1

    nb.Checkbutton(
        frame,
        text='Send in beta',
        variable=send_in_beta,
        command=lambda: config.set('FCT_SEND_IN_BETA', send_in_beta.get())).grid(
        row=row, padx=10, pady=(5, 0), sticky=tk.W)

    nb.Checkbutton(
        frame,
        text='Guess current FC location',
        variable=guess_fc_location,
        command=lambda: config.set('FCT_GUESS_FC_LOCATION', guess_fc_location.get())).grid(
        row=row, column=1, padx=10, pady=(5, 0), sticky=tk.W)

    nb.Label(
        frame,
        text=f'Current guess: {carrier.location}').grid(
        row=row, column=2, padx=10, pady=(5, 0), sticky=tk.W)
    row += 1

    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(padx=10, pady=(5, 5), columnspan=5, sticky=tk.EW, row=row)
    row += 1

    nb.Checkbutton(
        frame,
        text='Webhooks name overriding',
        variable=webhooks_names_overriding,
        command=lambda: config.set('FCT_OVERRIDE_WEBHOOKS_NAMES', webhooks_names_overriding.get())).grid(
        row=row, padx=10, pady=(5, 0), sticky=tk.W)
    row += 1

    nb.Entry(
        frame,
        textvariable=this.webhooks_overrided_name,
        width=35).grid(
        row=row, padx=10, pady=(5, 0), sticky=tk.W)

    nb.Button(
        frame,
        text='Reset',
        command=lambda: this.webhooks_overrided_name.set(DEFAULT_WEBHOOK_NAME_OVERRIDING)).grid(
        row=row, column=1, padx=10, pady=(5, 0), sticky=tk.W)
    row += 1

    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(padx=10, pady=(10, 0), columnspan=5, sticky=tk.EW, row=row)
    row += 1

    nb.Label(
        frame,
        text=f"Version: {VERSION}").grid(
        row=row, padx=10, pady=(10, 0), sticky=tk.W)
    row += 1

    return frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    config.set('FCT_DISCORD_WEBHOOK_URLS', [webhook_url.get() for webhook_url in this.webhooks_urls])  # type: ignore
    config.set('FCT_WEBHOOKS_OVERRIDED_NAME', this.webhooks_overrided_name.get())  # type: ignore

    try:
        del this.webhooks_urls  # type: ignore

    except NameError:
        pass

    config.save()


def cmdr_data(data, is_beta):

    if not config.get_bool('FCT_ENABLE_PLUGIN', default=True):
        return

    if force_beta:
        is_beta = True

    if is_beta and not config.get_bool('FCT_SEND_IN_BETA', default=False):
        return

    if carrier.callsign is not None:
        for ship_key in data['ships']:
            if data['ships'][ship_key]['station']['name'] == carrier.callsign:
                new_location = data['ships'][ship_key]['starsystem']['name']
                # logger.debug(f'Updating FC location according to cmdr_data: {carrier.location} -> {new_location}')
                carrier.location = new_location
