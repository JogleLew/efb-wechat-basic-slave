# coding: utf-8
import logging
import os
from typing import Optional, Dict, Any
import yaml
from ehforwarderbot import EFBChannel, ChannelType, EFBMsg, EFBStatus, EFBChat, MsgType
from ehforwarderbot import utils as efb_utils
from pkg_resources import resource_filename
from . import __version__ as version

from .Helper import Helper


class WechatMessengerChannel(EFBChannel):
    channel_name: str = "Wechat Message"
    channel_emoji: str = "🍏"
    channel_id = "jogle.wechat"
    channel_type: ChannelType = ChannelType.Slave

    __version__ = version.__version__

    supported_message_types = {MsgType.Text, MsgType.Sticker, MsgType.Image,
                               MsgType.Link, MsgType.Audio}

    config = dict()
    Helper: Helper
    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, instance_id: str = None):
        super().__init__(instance_id)
        """
        Load Config
        """
        self.hostname = "127.0.0.1"
        self.port = 52700
        self.load_config()

    def load_config(self):
        """
        Load configuration from path specified by the framework.

        Configuration file is in YAML format.
        """
        config_path = efb_utils.get_config_path(self.channel_id)
        if not os.path.exists(config_path):
            return
        with open(config_path) as f:
            self.config: Dict[str, Any] = yaml.load(f)
        if "hostname" in self.config:
            self.hostname = self.config["hostname"]
        if "port" in self.config:
            self.port = self.config["port"]

    def init_client_manager(self):
        self.Helper = Helper(self, efb_utils.get_data_path(self.channel_id),self.hostname, self.port)
        self.Helper.start_polling()

    def poll(self):
        """
        Init ClientMgr
        """
        # not sure how it works
        self.init_client_manager()
        pass

    def send_message(self, msg: 'EFBMsg'):
        return self.Helper.send_efb_message(msg)

    def send_status(self, status: 'EFBStatus'):
        raise EFBOperationNotSupported()

    def get_chat_picture(self, chat: 'EFBChat'):
        pass

    def get_chats(self):
        return self.Helper.get_efb_chats()

    def get_chat(self, chat_uid: str, member_uid: Optional[str] = None):
        return self.Helper.get_efb_chat(chat_uid)

    def stop_polling(self):
        # not sure how it works
        pass

    def get_extra_functions(self):
        pass
