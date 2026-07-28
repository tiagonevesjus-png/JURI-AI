"""Copia, de forma idempotente, eventos lidos do Google para a agenda interna.

O comando jamais cria, altera ou remove eventos no Google Calendar. Ele apenas
espelha os itens que já foram obtidos pela integração OAuth de leitura.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gestao.models import Compromisso, ItemGoogle


class Command(BaseCommand):
    help = 'Importa eventos do Google Agenda para a agenda interna do JURI-AI.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True, help='Nome de usuário local do JURI-AI.')
        parser.add_argument(
            '--incluir-passados', action='store_true',
            help='Também importa eventos que já ocorreram.',
        )

    def handle(self, *args, **options):
        try:
            usuario = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário local não encontrado.') from exc

        itens = ItemGoogle.objects.filter(user=usuario, fonte='AGENDA').exclude(ocorrido_em__isnull=True)
        if not options['incluir_passados']:
            itens = itens.filter(ocorrido_em__gte=timezone.now())

        criados = atualizados = ignorados = 0
        for item in itens:
            # Eventos cancelados ficam apenas no histórico Google; não entram
            # na agenda operacional do escritório.
            if item.dados.get('status') == 'cancelled':
                ignorados += 1
                continue

            marcador = f'[google_agenda_id:{item.identificador_externo}]'
            descricao = f'{marcador}\nOrigem: Google Agenda (somente leitura).\n{item.resumo}'.strip()
            compromisso = Compromisso.objects.filter(
                user=usuario, descricao__contains=marcador,
            ).first()
            if compromisso:
                compromisso.titulo = item.titulo[:255]
                compromisso.inicio = item.ocorrido_em
                compromisso.fim = None
                compromisso.local = item.link[:255]
                compromisso.descricao = descricao
                compromisso.save(update_fields=['titulo', 'inicio', 'fim', 'local', 'descricao'])
                atualizados += 1
            else:
                Compromisso.objects.create(
                    user=usuario,
                    titulo=item.titulo[:255],
                    tipo='OUTRO',
                    inicio=item.ocorrido_em,
                    fim=None,
                    local=item.link[:255],
                    descricao=descricao,
                )
                criados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Agenda interna atualizada: {criados} criado(s), {atualizados} atualizado(s), {ignorados} cancelado(s) ignorado(s).'
        ))
