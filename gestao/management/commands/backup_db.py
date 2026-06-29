"""Gera um backup do banco de dados em um arquivo local (.sql.gz ou cópia .sqlite3).

Uso:
    python manage.py backup_db            # salva em ./backups/
    python manage.py backup_db --dir /caminho

O envio automático para o OneDrive é feito pelo workflow
.github/workflows/backup.yml (GitHub Actions). Este comando serve para
backups manuais/locais.
"""

import gzip
import os
import shutil
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Gera um backup do banco de dados em um arquivo local.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', default='backups', help='Diretório de destino.')

    def handle(self, *args, **options):
        destino = options['dir']
        os.makedirs(destino, exist_ok=True)
        carimbo = datetime.now().strftime('%Y%m%d-%H%M%S')
        engine = settings.DATABASES['default']['ENGINE']

        if 'postgresql' in engine:
            url = os.environ.get('DATABASE_URL', '')
            caminho = os.path.join(destino, f'juriai-{carimbo}.sql.gz')
            if url:
                dump = subprocess.run(['pg_dump', url], check=True, stdout=subprocess.PIPE)
            else:
                db = settings.DATABASES['default']
                env = {**os.environ, 'PGPASSWORD': db.get('PASSWORD', '')}
                dump = subprocess.run(
                    ['pg_dump', '-h', db['HOST'], '-p', str(db['PORT']),
                     '-U', db['USER'], db['NAME']],
                    check=True, stdout=subprocess.PIPE, env=env,
                )
            with gzip.open(caminho, 'wb') as fp:
                fp.write(dump.stdout)
        else:
            origem = settings.DATABASES['default']['NAME']
            caminho = os.path.join(destino, f'juriai-{carimbo}.sqlite3')
            shutil.copy2(origem, caminho)

        self.stdout.write(self.style.SUCCESS(f'Backup gerado: {caminho}'))
