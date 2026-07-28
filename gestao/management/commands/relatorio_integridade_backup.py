import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestao.services.notificacoes import criar


class Command(BaseCommand):
    help = 'Envia ao responsável um relatório da última integridade de backup local.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True)
        parser.add_argument('--dir', default='/app/backups')

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['usuario'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Usuário local não encontrado.') from exc
        arquivos = sorted(Path(options['dir']).glob('integridade-*.json'), key=lambda item: item.stat().st_mtime, reverse=True)
        if not arquivos:
            raise CommandError('Nenhum relatório de integridade de backup foi encontrado.')
        dados = json.loads(arquivos[0].read_text(encoding='utf-8'))
        restauracao = dados.get('restauracao', 'desconhecida')
        prioridade = 'ALTA' if restauracao == 'falhou' else 'NORMAL'
        mensagem = (
            f"Backup: {dados.get('backup', 'desconhecido')}. "
            f"Restauração isolada: {restauracao}. Arquivo: {dados.get('arquivo', '')}."
        )
        alerta = criar(
            user, 'SISTEMA', 'Relatório de integridade do backup', mensagem,
            prioridade=prioridade, link='/notificacoes/',
            dados={'dedup_key': f"backup-integridade:{arquivos[0].stem}", 'backup': dados},
        )
        self.stdout.write(self.style.SUCCESS(f'Relatório enviado: notificação {alerta.id if alerta else "consolidada"}.'))
