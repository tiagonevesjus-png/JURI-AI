"""Agenda a sincronização automática dos processos com o PJe (DataJud).

Registra (de forma idempotente) um agendamento do django-q que executa
``gestao.tasks.sincronizar_monitorados`` periodicamente. O agendamento só é
*disparado* quando há um ``qcluster`` rodando (serviço ``worker`` do
docker-compose). Em ambientes sem worker (ex.: Render no modo ``Q_SYNC``),
use um cron externo chamando ``manage.py sincronizar_pje``.

Exemplos:
    # Diariamente às 06:00 (padrão):
    python manage.py agendar_pje

    # Diariamente em outro horário:
    python manage.py agendar_pje --hora 7 --minuto 30

    # A cada N minutos (ex.: de hora em hora):
    python manage.py agendar_pje --minutos 60

    # Remover o agendamento:
    python manage.py agendar_pje --desativar

Sem argumentos, lê os padrões do ambiente:
    PJE_SYNC_MINUTOS  (se definido, agenda por intervalo de minutos)
    PJE_SYNC_HORA     (hora do agendamento diário; padrão 6)
"""

import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

NOME_AGENDAMENTO = 'pje:sincronizacao'
FUNCAO = 'gestao.tasks.sincronizar_monitorados'


class Command(BaseCommand):
    help = 'Registra/atualiza o agendamento automático de sincronização com o PJe.'

    def add_arguments(self, parser):
        parser.add_argument('--minutos', type=int,
                            help='Executa a cada N minutos (sobrepõe o modo diário).')
        parser.add_argument('--hora', type=int, help='Hora do agendamento diário (0-23).')
        parser.add_argument('--minuto', type=int, default=0,
                            help='Minuto do agendamento diário (0-59).')
        parser.add_argument('--desativar', action='store_true',
                            help='Remove o agendamento existente.')

    def handle(self, *args, **options):
        try:
            from django_q.models import Schedule
        except Exception as exc:  # django-q ausente
            raise CommandError(f'django-q indisponível: {exc}')

        if options.get('desativar'):
            apagados, _ = Schedule.objects.filter(name=NOME_AGENDAMENTO).delete()
            if apagados:
                self.stdout.write(self.style.SUCCESS('Agendamento do PJe removido.'))
            else:
                self.stdout.write(self.style.WARNING('Nenhum agendamento do PJe encontrado.'))
            return

        minutos = options.get('minutos')
        if minutos is None and os.environ.get('PJE_SYNC_MINUTOS'):
            try:
                minutos = int(os.environ['PJE_SYNC_MINUTOS'])
            except ValueError:
                minutos = None

        if minutos:
            defaults = {
                'func': FUNCAO,
                'schedule_type': Schedule.MINUTES,
                'minutes': minutos,
                'repeats': -1,
                'next_run': timezone.now() + timedelta(minutes=minutos),
            }
            descricao = f'a cada {minutos} minuto(s)'
        else:
            hora = options.get('hora')
            if hora is None:
                hora = int(os.environ.get('PJE_SYNC_HORA', '6'))
            minuto = options.get('minuto') or 0
            agora = timezone.localtime()
            alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if alvo <= agora:
                alvo += timedelta(days=1)
            defaults = {
                'func': FUNCAO,
                'schedule_type': Schedule.DAILY,
                'minutes': None,
                'repeats': -1,
                'next_run': alvo,
            }
            descricao = f'diariamente às {hora:02d}:{minuto:02d}'

        _, criado = Schedule.objects.update_or_create(
            name=NOME_AGENDAMENTO, defaults=defaults)
        acao = 'criado' if criado else 'atualizado'
        self.stdout.write(self.style.SUCCESS(
            f'Agendamento do PJe {acao}: sincroniza os processos monitorados {descricao}.'))
