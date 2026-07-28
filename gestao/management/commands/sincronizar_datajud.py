"""Atualiza as movimentações DataJud dos processos em andamento de um usuário."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestao.models import Processo
from gestao.services.datajud import DataJudError, sincronizar
from gestao.services.notificacoes import criar as criar_notificacao


class Command(BaseCommand):
    help = 'Sincroniza o DataJud para todos os processos em andamento do usuário informado.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True, help='Nome de usuário local do JURI-AI.')

        parser.add_argument('--limite', type=int, default=0, help='Quantidade maxima de processos por ciclo (0 = todos).')

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário não encontrado.') from exc

        processos = Processo.objects.filter(user=user, status='ANDAMENTO').exclude(numero='').order_by(
            'ultima_sincronizacao_datajud', 'id'
        )
        limite = max(0, int(options.get('limite', 0)))
        if limite:
            processos = processos[:limite]
        total = processos.count()
        sucessos = falhas = novas_total = 0
        alterados = []
        for processo in processos:
            try:
                novas = sincronizar(processo)
            except DataJudError as exc:
                falhas += 1
                self.stderr.write(f'{processo.numero}: {exc}')
                continue
            sucessos += 1
            novas_total += novas
            if novas:
                alterados.append((processo.numero, novas))
            self.stdout.write(f'{processo.numero}: {novas} movimentação(ões) nova(s).')

        if alterados:
            detalhe = '\n'.join(f'{numero}: {novas} nova(s)' for numero, novas in alterados[:20])
            if len(alterados) > 20:
                detalhe += f'\n... e mais {len(alterados) - 20} processo(s).'
            criar_notificacao(
                user, 'SISTEMA', 'Atualização processual DataJud',
                f'{len(alterados)} processo(s) tiveram {novas_total} movimentação(ões) nova(s).\n{detalhe}',
                prioridade='ALTA', link='/processos/',
                dados={'fonte': 'datajud', 'processos_alterados': len(alterados), 'movimentacoes_novas': novas_total},
            )
        self.stdout.write(self.style.SUCCESS(
            f'DataJud concluído: {sucessos}/{total} processos sincronizados; '
            f'{novas_total} movimentação(ões) nova(s); {falhas} falha(s).'
        ))
