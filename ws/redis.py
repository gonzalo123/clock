from redis import Redis
from django.conf import settings

redis = Redis(host=settings.REDIS_HOST,
              port=settings.REDIS_PORT,
              decode_responses=True)
