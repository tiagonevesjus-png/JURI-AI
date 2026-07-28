from django.core.management.base import BaseCommand, CommandError

from gestao.services.google_workspace import GoogleWorkspaceError, iniciar_autorizacao


class Command(BaseCommand):
    help = 'Inicia autorização local OAuth PKCE para Gmail e Google Agenda em modo somente leitura.'

    def add_arguments(self, parser):
        parser.add_argument('--porta', type=int, default=8765)
        parser.add_argument('--nao-abrir-navegador', action='store_true')

    def handle(self, *args, **options):
        try:
            iniciar_autorizacao(
                port=options['porta'],
                abrir_navegador=not options['nao_abrir_navegador'],
            )
        except GoogleWorkspaceError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            'Solicitação Google criada. Conclua o consentimento no navegador; o retorno será tratado pelo sistema local.'
        ))
