## Building real time Python applications with Django Channels, Docker and Kubernetes

Three years ago I wrote an article about Websockets (https://gonzalo123.com/2017/01/02/playing-with-docker-silex-python-node-and-Websockets/). In fact I've written several articles about Websockets (Websockets and real time communications is something that I'm really passionate about), but today I would like to pick up this article. Nowadays I'm involved with several Django projects so I want to create a similar working prototype with Django. Let's start:

In the past I normally worked with libraries such as socket.io to ensure browser compatibility with Websockets but nowadays, at least in my world, we can assume that our users are using a modern browser with websocket support, so we're going to use plain Websockets instead external libraries. Django has a great support to Websockets with Django Channels. It allows us to to handle Websockets (and any other async protocols) thanks to Python's ASGI's specifications. In fact is pretty straightforward to build applications with real time applications with shared authentication (something that I have done in the past with a lot of effort. I'm getting old and now I like simple things :)

The application that I want to build is the following one: One Web application that shows the current time. Ok it's very simple to do it with a couple of javascript lines but this time I want to create a worker that emits an event via Websockets with the current time. My web application will show that real time update. This kind of architecture always have the same problem: The initial state. In this example we can ignore it. When the user opens the browser it must show the current time. As I said before in this example we can ignore this situation. We can wait until the next event to update the initial blank information but if the event arrives each 10 seconds our user'll have a blank screen until the next event arrives. In our example we're going to take into account this situation. Each time our user connect to the Websocket it will ask to the server for the initial state. 

Our initial state route will return the current time (using Redis). We can authorize our route using the standard Django's protected routes

```python
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ws.redis import redis

@login_required
def initial_state(request):
    return JsonResponse({'current': redis.get('time')})
```

We need to configure our channels and define a our event:

```python
from django.urls import re_path

from ws import consumers

websocket_urlpatterns = [
    re_path(r'time/tic/$', consumers.WsConsumer),
]
```

As we can see here we can reuse the authentication middleware in channel's consumers also
```python
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
```

 We're going to need a worker that each second triggers the current time (to avoid problems we're going to trigger our event each 0.5 seconds). To perform those kind of actions Django has a great tool called Celery. We can create workers and scheduled task with Celery (exactly what we need in our example). To avoid the "initial state" situation our worker will persists the initial state into a Redis storage
 
 ```python
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
```

Finally we need a javascript client to consume our Websockets

```javascript
let getWsUri = () => {
  return window.location.protocol === "https:" ? "wss" : "ws" +
    '://' + window.location.host +
    "/time/tic/"
}

let render = value => {
  document.querySelector('#display').innerHTML = value
}

let ws = new ReconnectingWebSocket(getWsUri())

ws.onmessage = e => {
  const data = JSON.parse(e.data);
  render(data.message.time)
}

ws.onopen = async () => {
  let response = await axios.get("/api/initial_state")
  render(response.data.current)
}
```
Basically that's the source code (plus Django the stuff).

## Application architecture
The architecture of the application is the following one:

### Frontend
The Django application. We can run this application in development with 
> python manage.py runserver 

And in production using a asgi server (uvicorn in this case)
> uvicorn config.asgi:application --port 8000 --host 0.0.0.0 --workers 1

### Celery worker
In development mode:
> celery -A ws worker -l debug

And in production 
> celery -A ws worker --uid=nobody --gid=nogroup

### Celery scheduler
We need this scheduler to emit our event (each 0.5 seconds)
> celery -A ws beat

### Message Server for Celery
In this case we're going to use Redis

## Docker
With this application we can use the same dockerfile for frontend, worker and scheduler using different entrypoints

Dockerfile:
```dockerfile
FROM python:3.8

ENV TZ 'Europe/Madrid'
RUN echo $TZ > /etc/timezone && \
apt-get update && apt-get install -y tzdata && \
rm /etc/localtime && \
ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
dpkg-reconfigure -f noninteractive tzdata && \
apt-get clean

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ADD . /src
WORKDIR /src

RUN pip install -r requirements.txt

RUN mkdir -p /var/run/celery /var/log/celery
RUN chown -R nobody:nogroup /var/run/celery /var/log/celery
```

And our whole application within a docker-compose file
```yaml
version: '3.4'

services:
  redis:
    image: redis
  web:
    image: clock:latest
    command: /bin/bash ./docker-entrypoint.sh
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 1m30s
      timeout: 10s
      retries: 3
      start_period: 40s
    depends_on:
      - "redis"
    ports:
      - 8000:8000
    environment:
      ENVIRONMENT: prod
      REDIS_HOST: redis
  celery:
    image: clock:latest
    command: celery -A ws worker --uid=nobody --gid=nogroup
    depends_on:
      - "redis"
    environment:
      ENVIRONMENT: prod
      REDIS_HOST: redis
  cron:
    image: clock:latest
    command: celery -A ws beat
    depends_on:
      - "redis"
    environment:
      ENVIRONMENT: prod
      REDIS_HOST: redis
``` 

## Kubernetes
If we want to deploy our application in a K8s cluster we need to migrate our docker-compose file into a k8s yaml files. I assume that we've deployed our docker containers into a container registry (such as ECR)
 
### Frontend:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clock-web-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: clock-web-api
      project: clock
  template:
    metadata:
      labels:
        app: clock-web-api
        project: clock
    spec:
      containers:
        - name: web-api
          image: my-ecr-path/clock:latest
          args: ["uvicorn", "config.asgi:application", "--port", "8000", "--host", "0.0.0.0", "--workers", "1"]
          ports:
            - containerPort: 8000
          env:
            - name: REDIS_HOST
              valueFrom:
                configMapKeyRef:
                  name: clock-app-config
                  key: redis.host
---
apiVersion: v1
kind: Service
metadata:
  name: clock-web-api
spec:
  type: LoadBalancer
  selector:
    app: clock-web-api
    project: clock
  ports:
    - protocol: TCP
      port: 8000 # port exposed internally in the cluster
      targetPort: 8000 # the container port to send requests to
```

### Celery worker
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clock-web-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: clock-web-api
      project: clock
  template:
    metadata:
      labels:
        app: clock-web-api
        project: clock
    spec:
      containers:
        - name: web-api
          image: my-ecr-path/clock:latest
          args: ["uvicorn", "config.asgi:application", "--port", "8000", "--host", "0.0.0.0", "--workers", "1"]
          ports:
            - containerPort: 8000
          env:
            - name: REDIS_HOST
              valueFrom:
                configMapKeyRef:
                  name: clock-app-config
                  key: redis.host
---
apiVersion: v1
kind: Service
metadata:
  name: clock-web-api
spec:
  type: LoadBalancer
  selector:
    app: clock-web-api
    project: clock
  ports:
    - protocol: TCP
      port: 8000 # port exposed internally in the cluster
      targetPort: 8000 # the container port to send requests to
```

### Celery scheduler
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clock-cron
spec:
  replicas: 1
  selector:
    matchLabels:
      app: clock-cron
      project: clock
  template:
    metadata:
      labels:
        app: clock-cron
        project: clock
    spec:
      containers:
        - name: clock-cron
          image: my-ecr-path/clock:latest
          args: ["celery", "-A", "ws", "beat"]
          env:
            - name: REDIS_HOST
              valueFrom:
                configMapKeyRef:
                  name: clock-app-config
                  key: redis.host
```

### Redis
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clock-redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: clock-redis
      project: clock
  template:
    metadata:
      labels:
        app: clock-redis
        project: clock
    spec:
      containers:
        - name: clock-redis
          image: redis
          ports:
            - containerPort: 6379
              name: clock-redis
---
apiVersion: v1
kind: Service
metadata:
  name: clock-redis
spec:
  type: ClusterIP
  ports:
    - port: 6379
      targetPort: 6379
  selector:
    app: clock-redis
```

### Shared configuration
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: clock-app-config
data:
  redis.host: "clock-redis"
```

We can deploy or application to our k8s cluster 
> kubectl apply -f .k8s/

And see it running inside the cluster locally with a port forward
> kubectl port-forward deployment/clock-web-api 8000:8000

And that's all. Our Django application with Websockets using Django Channels up and running with docker and also using k8s. 

