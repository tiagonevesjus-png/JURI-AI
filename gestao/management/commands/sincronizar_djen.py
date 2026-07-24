from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gestao.services.djen import DJENError, sincronizar


class Command(BaseCommand):
    help = 'Importa comunicações públicas do DJEN para um usuário local.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True, help='Nome de usuário local que receberá as publicações.')
        parser.add_argument('--dias', type=int, default=1, help='Quantidade de dias anteriores a consultar (padrão: 1).')

    def handle(self, *args, **options):
        dias = options['dias']
        if dias < 0 or dias > 7:
            raise CommandError('Informe entre 0 e 7 dias para evitar consultas excessivas ao DJEN.')
        try:
            usuario = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário local não encontrado.') from exc
        hoje = timezone.localdate()
        try:
            novas, encontradas = sincronizar(usuario, hoje - timedelta(days=dias), hoje)
        except DJENError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'DJEN sincronizado: {novas} nova(s) publicação(ões); {encontradas} encontrada(s).'
        ))
