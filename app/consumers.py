from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Trip
from channels.db import database_sync_to_async


@database_sync_to_async
def _get_user_group(self, user):
    return user.groups.first().name


@database_sync_to_async
def _get_trip_ids(self, user):
    user_groups = user.groups.values_list('name', flat=True)
    if 'driver' in user_groups:
        trip_ids = user.trips_as_driver.exclude(
            status=Trip.COMPLETED
        ).only('id').values_list('id', flat=True)
    else:
        trip_ids = user.trips_as_rider.exclude(
            status=Trip.COMPLETED
        ).only('id').values_list('id', flat=True)
    return map(str, trip_ids)


class TaxiConsumer(AsyncWebsocketConsumer):
    """
    Taxi consumer
    A Channels consumer is like a Django view with extra steps to support the WebSocket protocol. Whereas a Django view
    can only process an incoming request, a Channels consumer can send and receive messages to the WebSocket
    connection being opened and closed.
    """

    async def connect(self):
        """
        connect with web socket
        :return:
        """
        user = self.scope['user']
        if user.is_anonymous:
            await self.close()
        else:
            """
            Add user in driver group
            """
            user_group = await _get_user_group(user)
            if user_group == 'driver':
                await self.channel_layer.group_add(
                    group="drivers",
                    channel=self.channel_name
                )
            for trip_id in await _get_trip_ids(user):
                await self.channel_layer.group_add(
                    group=trip_id,
                    channel=self.channel_name
                )
            await self.accept()

    async def echo_message(self, message):
        await self.send_json({
            'type': message.get('type'),
            'data': message.get('data'),
        })

    async def disconnect(self, code):
        """
        disconnect with web socket
        :param code:
        :return:
        """
        user = self.scope['user']
        user_group = await _get_user_group(user)
        if user_group == 'driver':
            await self.channel_layer.group_discard(
                group='drivers',
                channel=self.channel_name
            )

        # new
        for trip_id in await _get_trip_ids(user):
            await self.channel_layer.group_discard(
                group=trip_id,
                channel=self.channel_name
            )

        await super().disconnect(code)

    async def receive_json(self, content, **kwargs):
        """
        The receive_json() function is responsible for processing all messages that come to the server. Our message is
        an object with a type and a data payload.
        Passing a type is a Channels convention that serves two purposes. First, it helps differentiate incoming
        messages and tells the server how to process them. Second, the type maps directly to a consumer function when
        sent from another channel layer.
        :param content:
        :param kwargs:
        :return:
        """
        message_type = content.get("type")
        if message_type == "echo.message":
            await self.send_json({
                "type": message_type,
                "data": content.get("data")
            })
