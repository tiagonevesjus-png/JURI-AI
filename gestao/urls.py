from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Processos
    path('processos/', views.processos, name='processos'),
    path('processos/novo/', views.processo_novo, name='processo_novo'),
    path('processos/<int:id>/', views.processo_detalhe, name='processo_detalhe'),

    # Agenda
    path('agenda/', views.agenda, name='agenda'),

    # Prazos
    path('prazos/', views.prazos, name='prazos'),
    path('prazos/<int:id>/concluir/', views.prazo_concluir, name='prazo_concluir'),

    # Audiências
    path('audiencias/', views.audiencias, name='audiencias'),

    # Tarefas
    path('tarefas/', views.tarefas, name='tarefas'),
    path('tarefas/<int:id>/status/<str:status>/', views.tarefa_status, name='tarefa_status'),

    # Financeiro
    path('financeiro/', views.financeiro, name='financeiro'),

    # Relatórios e acessos
    path('relatorios/', views.relatorios, name='relatorios'),
    path('acessos/', views.acessos, name='acessos'),
]
