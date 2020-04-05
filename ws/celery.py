from __future__ import absolute_import, unicode_literals
import os
from ws.consumers import WsConsumer
from asgiref.sync import async_to_sync
import channels.layers
from celery import Celery
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from ws.redis import redis

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(0.5, ws_beat.s(), name='beat every 0.5 seconds')


@app.task
def ws_beat(group=WsConsumer.GROUP, event='tic_message'):
    current_time = time.strftime('%X')
    redis.set('time', current_time)
    message = {'time': current_time}
    channel_layer = channels.layers.get_channel_layer()
    async_to_sync(channel_layer.group_send)(group, {'type': event, 'message': message})
