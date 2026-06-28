"""Prepara o sistema para o primeiro uso do escritório.

Cria (de forma idempotente) o usuário administrador a partir de variáveis de
ambiente e garante que o perfil dele esteja como ADMIN ativo. Pensado para
rodar automaticamente no deploy (ver docker/entrypoint.sh).

Variáveis de ambiente lidas:
    ADMIN_USERNAME   (padrão: 'admin')
    ADMIN_PASSWORD   (obrigatória para criar/atualizar a senha)
    ADMIN_EMAIL      (opcional)
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Cria/atualiza o usuário administrador do escritório a partir do ambiente.'

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        senha = os.environ.get('ADMIN_PASSWORD', '')
        email = os.environ.get('ADMIN_EMAIL', '')

        if not senha:
            self.stdout.write(self.style.WARNING(
                'ADMIN_PASSWORD não definida; pulando criação do administrador.'
            ))
            return

        user, criado = User.objects.get_or_create(username=username, defaults={'email': email})
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(senha)
        user.save()

        # O signal cria o Perfil; aqui garantimos cargo ADMIN e acesso ativo.
        perfil = getattr(user, 'perfil', None)
        if perfil is not None:
            perfil.cargo = 'ADMIN'
            perfil.ativo = True
            if not perfil.nome_completo:
                perfil.nome_completo = username
            perfil.save()

        acao = 'criado' if criado else 'atualizado'
        self.stdout.write(self.style.SUCCESS(f"Administrador '{username}' {acao} com sucesso."))
