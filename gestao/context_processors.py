"""Disponibiliza dados de perfil/permissão e identidade do escritório para os templates."""

from django.conf import settings
from gestao.models import Notificacao


def sidebar(request):
    contexto = {'escritorio_nome': getattr(settings, 'ESCRITORIO_NOME', 'Juri-AI')}
    if not request.user.is_authenticated:
        return contexto
    perfil = getattr(request.user, 'perfil', None)
    is_admin = request.user.is_superuser or (perfil is not None and perfil.cargo == 'ADMIN')
    contexto.update({'perfil_atual': perfil, 'is_admin': is_admin})
    contexto['notificacoes_nao_lidas'] = Notificacao.objects.filter(user=request.user, lida_em__isnull=True).count()
    return contexto
