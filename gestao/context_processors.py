"""Disponibiliza dados de perfil/permissão e identidade do escritório para os templates."""

from django.conf import settings


def sidebar(request):
    contexto = {'escritorio_nome': getattr(settings, 'ESCRITORIO_NOME', 'Juri-AI')}
    if not request.user.is_authenticated:
        return contexto
    perfil = getattr(request.user, 'perfil', None)
    is_admin = request.user.is_superuser or (perfil is not None and perfil.cargo == 'ADMIN')
    contexto.update({'perfil_atual': perfil, 'is_admin': is_admin})
    return contexto
