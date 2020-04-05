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
