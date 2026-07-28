from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestao.services.google_workspace import GoogleWorkspaceError, sincronizar_drive_clientes


class Command(BaseCommand):
    help = 'Cataloga os metadados da pasta Clientes do Google Drive, sem baixar ou alterar arquivos.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True)

    def handle(self, *args, **options):
        try:
            usuario = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário local não encontrado.') from exc
        try:
            novos, alterados, total, raiz = sincronizar_drive_clientes(usuario)
        except GoogleWorkspaceError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'Drive sincronizado: {novos} novo(s), {alterados} alterado(s), {total} arquivo(s); raiz {raiz.get("name", "Clientes")}.'
        ))
