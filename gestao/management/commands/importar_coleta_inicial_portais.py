"""Importa o conjunto já observado em leitura nos portais abertos.

Não coleta documentos, não consulta autos sigilosos e não executa atos. Cada
registro é mantido como fonte auditável; processos já existentes recebem apenas
um vínculo. Os não vinculados permanecem em "Coletas para conferência".
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from gestao.models import Processo, ProcessoColetado


COLETAS = (
    # Acervo visível PJe TRT16 (leitura de 26/07/2026)
    ('PJE_TRT16', '0017413-45.2019.5.16.0016', 'TRT16'),
    ('PJE_TRT16', '0016141-82.2024.5.16.0002', 'TRT16'),
    ('PJE_TRT16', '0016697-72.2024.5.16.0006', 'TRT16'),
    ('PJE_TRT16', '0017203-68.2022.5.16.0022', 'TRT16'),
    ('PJE_TRT16', '0017269-76.2020.5.16.0003', 'TRT16'),
    ('PJE_TRT16', '0017380-18.2024.5.16.0004', 'TRT16'),
    ('PJE_TRT16', '0017442-58.2024.5.16.0004', 'TRT16'),
    ('PJE_TRT16', '0017607-80.2025.5.16.0001', 'TRT16'),
    ('PJE_TRT16', '0016068-39.2026.5.16.0003', 'TRT16'),
    ('PJE_TRT16', '0016102-14.2026.5.16.0003', 'TRT16'),
    # Distribuições visíveis no eLaw, sem atribuir cliente por inferência.
    ('ELAW', '0018830-86.2026.5.16.0016', 'TRT16'),
    ('ELAW', '0859778-35.2025.8.10.0001', 'TJMA'),
    ('ELAW', '0833567-25.2026.8.10.0001', 'TJMA'),
)


def somente_digitos(numero):
    return ''.join(ch for ch in numero if ch.isdigit())


class Command(BaseCommand):
    help = 'Importa os processos já coletados em leitura de eLaw e TRT16.'

    def add_arguments(self, parser):
        parser.add_argument('--user', required=True, help='E-mail ou usuário local do JURI-AI')

    def handle(self, *args, **opts):
        User = get_user_model()
        user = User.objects.filter(username=opts['user']).first() or User.objects.filter(email=opts['user']).first()
        if not user:
            raise CommandError('Usuário do JURI-AI não encontrado.')
        existentes = {
            somente_digitos(p.numero): p
            for p in Processo.objects.filter(user=user).only('id', 'numero')
            if somente_digitos(p.numero)
        }
        criados = vinculados = pendentes = 0
        for fonte, numero, tribunal in COLETAS:
            processo = existentes.get(somente_digitos(numero))
            _, criado = ProcessoColetado.objects.update_or_create(
                user=user, fonte=fonte, numero=numero,
                defaults={
                    'tribunal': tribunal,
                    'processo': processo,
                    'status': 'VINCULADO' if processo else 'PENDENTE',
                    'dados': {'modo': 'leitura', 'origem': 'coleta_portais_2026_07_26'},
                },
            )
            criados += int(criado)
            vinculados += int(processo is not None)
            pendentes += int(processo is None)
        self.stdout.write(self.style.SUCCESS(
            f'Coleta concluída: {criados} novo(s), {vinculados} vinculado(s), {pendentes} aguardando conferência.'
        ))
