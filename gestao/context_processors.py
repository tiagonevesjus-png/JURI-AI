"""Disponibiliza dados de perfil/permissão para o menu lateral em todos os templates."""


def sidebar(request):
    if not request.user.is_authenticated:
        return {}
    perfil = getattr(request.user, 'perfil', None)
    is_admin = request.user.is_superuser or (perfil is not None and perfil.cargo == 'ADMIN')
    return {'perfil_atual': perfil, 'is_admin': is_admin}
