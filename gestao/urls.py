from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('hoje/', views.hoje, name='hoje'),
    path('notificacoes/', views.notificacoes, name='notificacoes'),
    path('notificacoes/feed/', views.notificacoes_feed, name='notificacoes_feed'),
    path('notificacoes/<int:id>/ler/', views.notificacao_ler, name='notificacao_ler'),
    path('notificacoes/push/config/', views.push_config, name='push_config'),
    path('notificacoes/push/subscribe/', views.push_subscribe, name='push_subscribe'),
    path('notificacoes/push/unsubscribe/', views.push_unsubscribe, name='push_unsubscribe'),
    path('assinaturas/', views.assinaturas, name='assinaturas'),
    path('assinaturas/<uuid:uid>/original/', views.assinatura_baixar_original, name='assinatura_baixar_original'),
    path('assinaturas/<uuid:uid>/p7s/', views.assinatura_enviar_p7s, name='assinatura_enviar_p7s'),

    # Processos
    path('processos/', views.processos, name='processos'),
    path('processos/coletados/', views.processos_coletados, name='processos_coletados'),
    path('processos/coletados/<int:id>/importar/', views.processo_coletado_importar, name='processo_coletado_importar'),
    path('processos/novo/', views.processo_novo, name='processo_novo'),
    path('processos/<int:id>/', views.processo_detalhe, name='processo_detalhe'),
    path('processos/<int:id>/sincronizar-datajud/', views.processo_sincronizar_datajud,
         name='processo_sincronizar_datajud'),
    path('publicacoes/', views.publicacoes_djen, name='publicacoes_djen'),

    # Agenda
    path('agenda/', views.agenda, name='agenda'),

    # Prazos
    path('prazos/', views.prazos, name='prazos'),
    path('prazos/feriados/', views.feriados_forenses, name='feriados_forenses'),
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
    path('relatorios/processos/<str:formato>/download/', views.relatorio_processos_download,
         name='relatorio_processos_download'),
    path('relatorios/<str:tipo>/<str:formato>/download/', views.relatorio_download,
         name='relatorio_download'),
    path('conhecimento/', views.base_conhecimento, name='base_conhecimento'),
    path('acessos/', views.acessos, name='acessos'),
]
