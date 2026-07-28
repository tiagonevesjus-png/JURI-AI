from datetime import date

from django.core.management.base import BaseCommand

from gestao.models import FeriadoForense


NACIONAIS_2026 = [
    (date(2026, 1, 1), 'Confraternização Universal'),
    (date(2026, 4, 21), 'Tiradentes'),
    (date(2026, 5, 1), 'Dia Mundial do Trabalho'),
    (date(2026, 9, 7), 'Independência do Brasil'),
    (date(2026, 10, 12), 'Nossa Senhora Aparecida'),
    (date(2026, 11, 2), 'Finados'),
    (date(2026, 11, 15), 'Proclamação da República'),
    (date(2026, 11, 20), 'Dia Nacional de Zumbi e da Consciência Negra'),
    (date(2026, 12, 25), 'Natal'),
]


class Command(BaseCommand):
    help = 'Carrega feriados nacionais e estaduais do Maranhão de 2026 como apoio à conferência de prazos.'

    def handle(self, *args, **options):
        fonte_nacional = 'https://legis.sigepe.gov.br/legis/detalhar/24765'
        criados = 0
        for data, descricao in NACIONAIS_2026:
            _, criado = FeriadoForense.objects.get_or_create(
                data=data, descricao=descricao, abrangencia='NACIONAL', tribunal='', comarca='',
                defaults={'fonte': fonte_nacional},
            )
            criados += int(criado)
        _, criado = FeriadoForense.objects.get_or_create(
            data=date(2026, 7, 28), descricao='Adesão do Maranhão à Independência',
            abrangencia='ESTADUAL_MA', tribunal='', comarca='',
            defaults={'fonte': 'https://diariooficial.pinheiro.ma.gov.br/publicacoes/decreto-no-001-2026-de-05-de-janeiro-de-2026/'},
        )
        criados += int(criado)
        self.stdout.write(self.style.SUCCESS(
            f'{criados} feriado(s) incluído(s). Pontos facultativos e suspensões de tribunal devem ser cadastrados após conferência do calendário forense.'
        ))
