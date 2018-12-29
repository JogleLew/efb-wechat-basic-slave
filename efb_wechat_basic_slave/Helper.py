import os
import re
import json
import time
import copy
import magic
import logging
import requests
import tempfile
import threading
from PIL import Image
from datetime import datetime
import urllib.request
from urllib.error import URLError, HTTPError, ContentTooShortError
from ehforwarderbot import EFBMsg, MsgType, EFBChat, coordinator, EFBStatus, ChatType

user_url = "http://%s:%s/wechat-plugin/user"
chat_url = "http://%s:%s/wechat-plugin/chatlog?userId=%s&count=%d"
send_url = "http://%s:%s/wechat-plugin/send-message"
subtitle_pattern = r"(from: (.*)   )?(Yesterday |Mon |Tue |Wed |Thu |Fri |Sat |Sun )?(\d{2}-\d{2}-\d{2} )?((\d{2}:\d{2}:\d{2})|(\d{5,}))"


def clean_msg(msg1, cur_date):
    if not "subTitle" in msg1:
        msg1["subTitle"] = "00-00-00 00:00:00"
        return msg1
    t1 = msg1["subTitle"]
    m = re.match(subtitle_pattern, t1)
    if not m:
        msg1["subTitle"] = "00-00-00 00:00:00"
        return msg1
    # if contains "from: xxxx"
    if m.group(1) and m.group(2):
        msg1["from"] = m.group(2)
    # get date
    if m.group(4):
        msg_date = m.group(4).strip()
    else:
        msg_date = cur_date
    # get time
    if m.group(6):
        msg_time = m.group(6).strip()
    else:
        msg_time = "00:00:00"
    t1 = msg_date + " " + msg_time
    msg1["subTitle"] = t1
    return msg1


def newer_msg(msg1, msg2, cur_date, is_latest=False):
    t1 = msg1["subTitle"]
    m = re.match(subtitle_pattern, t1)
    if not m:
        return False
    # if contains "from: xxxx"
    if m.group(1):
        msg1["from"] = m.group(2)
    # if contains "yesterday, ..."
    if m.group(3):
        return False
    # get date
    if m.group(4):
        msg_date = m.group(4).strip()
    else:
        msg_date = cur_date
    # get time
    if m.group(6):
        msg_time = m.group(6).strip()
    else:
        if not is_latest:
            return False
        msg_time = "00:00:00"
    t1 = msg_date + " " + msg_time
    msg1["subTitle"] = t1

    # Check whether msg2 is {} 
    if not "subTitle" in msg2:
        return True
    t2 = msg2["subTitle"]
    m = re.match(subtitle_pattern, t2)
    if not m:
        return True
    # if contains "from: xxxx"
    if m.group(1):
        msg1["from"] = m.group(2)
    # get date
    if m.group(4):
        msg_date = m.group(4).strip()
    else:
        msg_date = cur_date
    # get time
    if m.group(6):
        msg_time = m.group(6).strip()
    else:
        msg_time = "00:00:00"
    t2 = msg_date + " " + msg_time
    msg2["subTitle"] = t2

    #print("t1: ", t1)
    #print("t2: ", t2)
    if is_latest:
        if msg1["title"] == msg2["title"]:
            return False
        return True
    return t1 > t2


def async_send_messages_to_master(msg):
    coordinator.send_message(msg)
    if msg.file:
        msg.file.close()


class Helper:

    def __init__(self, channel: 'QQMessengerChannel', storage_path, hostname, port):
        self.channel: 'QQMessengerChannel' = channel
        self.storage_path = storage_path
        self.hostname = hostname
        self.port = str(port)
        self.logger: logging.Logger = logging.getLogger(__name__)

        self.MISSING_GROUP: EFBChat = EFBChat(self.channel)
        self.MISSING_GROUP.chat_uid = "__error__"
        self.MISSING_GROUP.chat_type = ChatType.Group
        self.MISSING_GROUP.chat_name = self.MISSING_GROUP.chat_alias = "Chat Missing"

        self.MISSING_USER: EFBChat = EFBChat(self.channel)
        self.MISSING_USER.chat_uid = "__error__"
        self.MISSING_USER.chat_type = ChatType.User
        self.MISSING_USER.chat_name = self.MISSING_USER.chat_alias = "Chat Missing"


    def get_efb_chats(self):
        chat_list = requests.get(user_url % (self.hostname, self.port)).json()
        result = []
        for chat_item in chat_list:
            efb_chat = EFBChat(self.channel)
            efb_chat.chat_uid = chat_item["userId"]
            title = chat_item["title"]
            if title.startswith("[Group] "):
                efb_chat.chat_name = title[8:]
                efb_chat.chat_type = ChatType.Group
            else:
                efb_chat.chat_name = title 
                efb_chat.chat_type = ChatType.User
            efb_chat.chat_alias = None
            efb_chat.is_chat = True
            efb_chat.vendor_specific = {'is_anonymous': False}
            result.append(efb_chat)
        return result


    def get_efb_chat(self, chat_uid):
        chat_list = requests.get(user_url % (self.hostname, self.port)).json()
        for chat_item in chat_list:
            if not chat_uid == chat_item["userId"]:
                continue
            efb_chat = EFBChat(self.channel)
            efb_chat.chat_uid = chat_item["userId"]
            title = chat_item["title"]
            if title.startswith("[Group] "):
                efb_chat.chat_name = title[8:]
                efb_chat.chat_type = ChatType.Group
            else:
                efb_chat.chat_name = title 
                efb_chat.chat_type = ChatType.User
            efb_chat.chat_alias = None
            efb_chat.is_chat = True
            efb_chat.vendor_specific = {'is_anonymous': False}
            return efb_chat
        return None

    
    def send_message(self, uid, content):
        r = requests.post(send_url % (self.hostname, self.port), data = {"userId": uid, "content": content})


    def send_efb_message(self, msg):
        chat_uid = msg.chat.chat_uid
        if msg.type in [MsgType.Text, MsgType.Link]:
            text = msg.text
            self.send_message(chat_uid, text)
        else:
            pass


    def send_message_wrapper(self, *args, **kwargs):
        threading.Thread(target=async_send_messages_to_master, args=args, kwargs=kwargs).start()
    

    def start_polling(self):
        threading.Thread(target=self.poll).start()


    def cq_get_image(self, image_link): 
        while not os.path.exists(image_link): 
            time.sleep(1)
        last_size = 0
        while not os.path.getsize(image_link) == last_size: 
            last_size = os.path.getsize(image_link)
            time.sleep(1)
        file = tempfile.NamedTemporaryFile()
        try:
            urllib.request.urlretrieve("file://" + image_link, file.name)
        except (URLError, HTTPError, ContentTooShortError):
            logging.getLogger(__name__).warning('Image download failed.')
            return None
        else:
            if file.seek(0, 2) <= 0:
                raise EOFError('File downloaded is Empty')
            file.seek(0)
            return file


    def send_msg_to_master(self, context):
        self.logger.debug(repr(context))
        msg = EFBMsg()
        efb_chat = EFBChat(self.channel).system()
        efb_chat.chat_type = ChatType.System
        efb_chat.chat_name = context['event_description']
        msg.chat = msg.author = efb_chat
        msg.deliver_to = coordinator.master
        msg.type = MsgType.Text
        msg.uid = "__{context[uid_prefix]}__.{uni_id}".format(context=context,
                                                              uni_id=str(int(time.time())))
        if 'message' in context:
            msg.text = context['message']
        if 'commands' in context:
            msg.commands = EFBMsgCommands(context['commands'])
        coordinator.send_message(msg)


    def poll(self):
        error_count = 0
        first_load = False
        last_msg_dict = {}
        path_pattern = os.path.join(self.storage_path, "last_msg.json")
        if os.path.isfile(path_pattern):
            with open(path_pattern, "r") as f:
                last_msg_dict = json.loads(f.read())
        else:
            first_load = True
        while True:
            try:
                chat_list = requests.get(user_url % (self.hostname, self.port)).json()

                # Check message update
                for chat_item in chat_list:
                    user_id = chat_item["userId"]
                    if user_id in ["weixin", "notifymessage"]:
                        continue
                    # Get current message list
                    msg_list = requests.get(chat_url % (self.hostname, self.port, user_id, 5)).json()[1:]
                    cur_date = '{0:%y-%m-%d}'.format(datetime.now())

                    # Get last message
                    last_msg = {}
                    if user_id in last_msg_dict:
                        last_msg = last_msg_dict[user_id]

                    # Record last message
                    if len(msg_list) > 0:
                        last_msg_dict[user_id] = clean_msg(msg_list[0], cur_date)
                    if first_load:
                        continue

                    # Get new message list
                    new_msg_list = []
                    for idx, msg in enumerate(msg_list):
                        if newer_msg(msg, last_msg, cur_date, is_latest=(idx==0)):
                            new_msg_list.append(clean_msg(msg, cur_date))
                        else:
                            break
                    new_msg_list.reverse()

                    # Handle message
                    for msg in new_msg_list:
                        sender = "Unknown"
                        content = msg["title"]
                        if "：" in msg["title"] and msg["userId"].endswith("@chatroom"):
                            segs = msg["title"].split("：")
                            sender = segs[0]
                            content = "：".join(segs[1:])
                        if "from" in msg:
                            sender = msg["from"]
                        #print("sender: %s\ncontent: %s\nurl: %s\ntime: %s\n" % (sender, content, msg["url"], msg["subTitle"]))

                        # default: text
                        efb_msg = EFBMsg()
                        efb_msg.type = MsgType.Text
                        efb_msg.text = content

                        if len(msg["url"]) > 0:
                            # Check picture
                            if msg["url"].endswith(".gif") or msg["url"].endswith(".jpg") or msg["url"].endswith(".jpeg") or msg["url"].endswith(".png"):
                                efb_msg.type = MsgType.Image
                                efb_msg.file = self.cq_get_image(msg["url"])
                                mime = magic.from_file(msg["url"], mime=True)
                                if isinstance(mime, bytes):
                                    mime = mime.decode()
                                efb_msg.path = msg["url"]
                                efb_msg.mime = mime
                            # Check video
                            elif msg["url"].endswith(".mp4"):
                                efb_msg.type = MsgType.Video
                                efb_msg.file = self.cq_get_image(msg["url"])
                                mime = magic.from_file(msg["url"], mime=True)
                                if isinstance(mime, bytes):
                                    mime = mime.decode()
                                efb_msg.path = msg["url"]
                                efb_msg.mime = mime
                            # Check document
                            elif msg["url"].startswith("/"):
                                efb_msg.type = MsgType.File
                                efb_msg.file = self.cq_get_image(msg["url"])
                                efb_msg.path = msg["url"]
                            # Add link to content
                            else:
                                efb_msg.type = MsgType.Text
                                if not msg["url"] in content:
                                    content += "\n(" + msg["url"] + ")"
                                efb_msg.text = content

                        efb_msg.uid = user_id
                        efb_msg.chat = self.get_efb_chat(user_id)
                        if efb_msg.chat.chat_type == ChatType.User:
                            efb_msg.text = sender + ":\n" + content
                            efb_msg.author = efb_msg.chat
                        else:
                            author = copy.deepcopy(efb_msg.chat)
                            author.chat_type = ChatType.User
                            author.chat_name = sender
                            efb_msg.author = author
                        efb_msg.deliver_to = coordinator.master
                        self.send_message_wrapper(efb_msg)

                path_pattern = os.path.join(self.storage_path, "last_msg.json")
                with open(path_pattern, "w") as f:
                    f.write(json.dumps(last_msg_dict))
                first_load = False

            except requests.exceptions.RequestException as e:
                print(e)
                error_count += 1
                if error_count >= 12:
                    context = {'message': 'Connection Failed', 'uid_prefix': 'alert', 'event_description': 'WeChat Alert'}
                    self.send_msg_to_master(context)
                    error_count = 0
            except json.decoder.JSONDecodeError as e:
                print(e)
                error_count += 1
                if error_count >= 12:
                    context = {'message': 'Connection Failed', 'uid_prefix': 'alert', 'event_description': 'WeChat Alert'}
                    self.send_msg_to_master(context)
                    error_count = 0
            except Exception as e:
                print(e)
            time.sleep(5)


