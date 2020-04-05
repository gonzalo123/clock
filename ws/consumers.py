import json
from channels.generic.websocket import AsyncWebsocketConsumer


class WsConsumer(AsyncWebsocketConsumer):
    GROUP = 'time'

    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
        else:
            await self.channel_layer.group_add(
                self.GROUP,
                self.channel_name
            )
            await self.accept()

    async def tic_message(self, event):
        if not self.scope["user"].is_anonymous:
            message = event['message']

            await self.send(text_data=json.dumps({
                'message': message
            }))
