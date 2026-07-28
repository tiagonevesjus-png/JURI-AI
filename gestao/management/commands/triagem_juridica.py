from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestao.services.triagem import executar


class Command(BaseCommand):
    help = 'Classifica eventos recentes e emite um alerta consolidado por processo.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True, help='Nome de usuário local do JURI-AI.')
        parser.add_argument('--dias', type=int, default=1, help='Janela de leitura em dias (padrão: 1).')
        parser.add_argument('--limite', type=int, default=50, help='Máximo de novos eventos por execução.')

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário não encontrado.') from exc
        triagens, alertas, pendentes = executar(user, dias=options['dias'], limite=options['limite'])
        self.stdout.write(self.style.SUCCESS(
            f'Triagem concluída: {triagens} novo(s) evento(s), {alertas} alerta(s) consolidado(s), '
            f'{pendentes} pendente(s) encontrado(s).'
        ))
