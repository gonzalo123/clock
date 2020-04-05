from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from ws.redis import redis


@login_required
def index(request):
    return render(request, 'index.html')


def health(request):
    return JsonResponse({'status': 'ok'})


@login_required
def initial_state(request):
    return JsonResponse({'current': redis.get('time')})
