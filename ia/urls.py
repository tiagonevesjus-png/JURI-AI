from django.urls import path

from . import views

urlpatterns = [
    path('assistente/', views.assistente, name='assistente'),
]
