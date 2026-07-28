"""Registra uma coleta manual/assistida feita em portais externos.

Uso (sem dados sensíveis):
  python manage.py registrar_coleta_portais --user email@exemplo.com --fonte PJE_TRT16 --numero 0000000-00.0000.5.00.0000 --tribunal TRT16

O comando deduplica por fonte e número CNJ. Quando encontra um processo já
cadastrado, apenas cria o vínculo auditável; não altera cliente, status ou
dados processuais existentes.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestao.models import Processo, ProcessoColetado


class Command(BaseCommand):
    help = 'Registra processo encontrado em eLaw ou PJe sem importação insegura.'

    def add_arguments(self, parser):
        parser.add_argument('--user', required=True)
        parser.add_argument('--fonte', choices=[c[0] for c in ProcessoColetado.FONTE_CHOICES], required=True)
        parser.add_argument('--numero', required=True)
        parser.add_argument('--tribunal', default='')
        parser.add_argument('--titulo', default='')
        parser.add_argument('--autor', default='')
        parser.add_argument('--reu', default='')

    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            user = User.objects.get(username=opts['user'])
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=opts['user'])
            except User.DoesNotExist as exc:
                raise CommandError('Usuário do JURI-AI não encontrado.') from exc
        numero = ''.join(ch for ch in opts['numero'] if ch.isdigit())
        if len(numero) != 20:
            raise CommandError('Informe um número CNJ com 20 dígitos.')
        formato = f'{numero[:7]}-{numero[7:9]}.{numero[9:13]}.{numero[13]}.{numero[14:16]}.{numero[16:]}'
        processo = next(
            (p for p in Processo.objects.filter(user=user).only('id', 'numero')
             if ''.join(ch for ch in (p.numero or '') if ch.isdigit()) == numero),
            None,
        )
        item, criado = ProcessoColetado.objects.update_or_create(
            user=user, fonte=opts['fonte'], numero=formato,
            defaults={
                'tribunal': opts['tribunal'], 'titulo': opts['titulo'],
                'parte_autora': opts['autor'], 'parte_re': opts['reu'],
                'processo': processo,
                'status': 'VINCULADO' if processo else 'PENDENTE',
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'Atualizado' if not criado else 'Registrado'}: {item.numero} — {item.get_status_display()}"
        ))
