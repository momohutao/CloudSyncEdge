import sys
import os
from pathlib import Path
from CloudSyncEdge.src.protocol.message_types import MessageTypes
from CloudSyncEdge.ecu_lib.interfaces.ecu_interface import ECUInterface
class SouthboundWebSocketServer:
    def __init__(self):
        # 引用成员A的接口
        self.ecu_interface = ECUInterface()

        # 引用成员D的协议
        self.message_types = MessageTypes

        # 本地设备管理
        self.active_devices = {}