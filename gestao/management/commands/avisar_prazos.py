from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from gestao.services.prazos import emitir_avisos


class Command(BaseCommand):
    help = 'Emite lembretes para marcos de prazos confirmados manualmente.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True)

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário não encontrado.') from exc
        self.stdout.write(self.style.SUCCESS(f'{emitir_avisos(user)} aviso(s) de prazo emitido(s).'))
