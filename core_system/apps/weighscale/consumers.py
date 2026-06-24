import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from . import serial_manager

logger = logging.getLogger(__name__)

_auto_connect_lock_value = False


class WeighscaleConsumer(AsyncWebsocketConsumer):
    GROUP_NAME = "weighscale_live"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        if serial_manager.is_connected():
            await self.send(text_data=json.dumps({
                "event": "status",
                "connected": True,
                "port": serial_manager.get_active_port(),
            }))
        elif getattr(settings, "SCALE_ENABLED", True):
            await self._attempt_auto_connect()
        else:
            await self.send(text_data=json.dumps({
                "event": "status",
                "connected": False,
                "error": "Scale integration is disabled.",
            }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def weighscale_message(self, event):
        payload = {k: v for k, v in event.items() if k != "type"}
        await self.send(text_data=json.dumps(payload))

    async def _attempt_auto_connect(self):
        port_setting = getattr(settings, "SERIAL_PORT", "AUTO")
        baud_rate = getattr(settings, "SERIAL_BAUD_RATE", 9600)

        auto_fn = sync_to_async(serial_manager.auto_connect, thread_sensitive=False)
        try:
            ok, error = await auto_fn(port_setting, baud_rate)
        except Exception as exc:
            logger.warning("Auto-connect failed: %s", exc)
            ok, error = False, str(exc)

        if ok:
            logger.info("Auto-connected to %s", serial_manager.get_active_port())
            await self.send(text_data=json.dumps({
                "event": "status",
                "connected": True,
                "port": serial_manager.get_active_port(),
            }))
        else:
            await self.send(text_data=json.dumps({
                "event": "status",
                "connected": False,
                "error": error or "Could not open serial port.",
            }))
