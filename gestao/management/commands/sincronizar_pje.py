"""Sincroniza processos com a API Pública do DataJud (PJe).

Exemplos de uso:

    # Todos os processos marcados para monitoramento:
    python manage.py sincronizar_pje

    # Um processo específico (pelo id):
    python manage.py sincronizar_pje --processo 12

    # Por número CNJ (mascarado ou só dígitos):
    python manage.py sincronizar_pje --numero 0000832-35.2018.4.01.3202

Pode ser agendado (cron, django-q Schedule) para manter as movimentações
sempre atualizadas.
"""

from django.core.management.base import BaseCommand, CommandError

from gestao import pje
from gestao.models import Processo
from gestao.tasks import sincronizar_processo_pje


class Command(BaseCommand):
    help = 'Sincroniza as movimentações dos processos com a API do DataJud (PJe).'

    def add_arguments(self, parser):
        parser.add_argument('--processo', type=int, help='ID de um processo específico.')
        parser.add_argument('--numero', type=str, help='Número CNJ de um processo específico.')
        parser.add_argument('--todos', action='store_true',
                            help='Inclui processos não marcados como monitorados.')

    def handle(self, *args, **options):
        qs = Processo.objects.all()

        if options.get('processo'):
            qs = qs.filter(id=options['processo'])
        elif options.get('numero'):
            digitos = pje.limpar_numero(options['numero'])
            qs = qs.filter(numero__contains=digitos) if digitos else qs.none()
        else:
            qs = qs.exclude(numero='')
            if not options.get('todos'):
                qs = qs.filter(monitorar_pje=True)

        processos = list(qs)
        if not processos:
            raise CommandError('Nenhum processo encontrado para sincronizar.')

        total_importadas = 0
        for processo in processos:
            if not pje.numero_valido(processo.numero):
                self.stdout.write(self.style.WARNING(
                    f'• {processo} — número CNJ inválido, pulando.'))
                continue

            res = sincronizar_processo_pje(processo.id)
            total_importadas += res.get('importadas', 0)
            estilo = self.style.SUCCESS if res.get('ok') else self.style.ERROR
            self.stdout.write(estilo(f'• {processo} — {res.get("mensagem")}'))

        self.stdout.write(self.style.SUCCESS(
            f'Concluído. {total_importadas} movimentação(ões) nova(s) no total.'))
