from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestao.services.google_workspace import GoogleWorkspaceError, sincronizar


class Command(BaseCommand):
    help = 'Lê Gmail e Google Agenda autorizados localmente, sem criar ou alterar itens no Google.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True)

    def handle(self, *args, **options):
        try:
            usuario = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário local não encontrado.') from exc
        try:
            novos_gmail, novos_agenda, total_gmail, total_agenda = sincronizar(usuario)
        except GoogleWorkspaceError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'Google sincronizado: Gmail {novos_gmail}/{total_gmail}; Agenda {novos_agenda}/{total_agenda}.'
        ))
