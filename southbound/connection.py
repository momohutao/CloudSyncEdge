from typing import Dict,Any
class ConnectionManager:
    def __init__(self):
        #存储映射：ecu_id->websocket_connection
        self._active_connections:Dict[str,Any]={}

    async def add(self,ecu_id:str,ws):
        self._active_connections[ecu_id]=ws
        print(f"🔌 [Southbound] Device connected: {ecu_id}")
    async def remove(self,ecu_id:str):
        if ecu_id in self._active_connections:
            del self._active_connections[ecu_id]
            print(f"❌ [Southbound] Device disconnected: {ecu_id}")
    def get_ws(self,ecu_id:str):
        return self._active_connections.get(ecu_id)

    def get_all_devices(self):
        return list(self._active_connections.keys())

manager=ConnectionManager()

