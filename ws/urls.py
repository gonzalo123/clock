from django.urls import path

from ws import views

urlpatterns = [
    path('initial_state', views.initial_state, name='initial_state'),
]
