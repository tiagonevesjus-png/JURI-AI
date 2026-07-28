import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


FUSO = ZoneInfo('America/Sao_Paulo')
USUARIO = os.environ.get('BACKUP_REPORT_USERNAME', '')
HORA = int(os.environ.get('BACKUP_REPORT_SCHEDULE_HOUR', '3'))
MINUTO = int(os.environ.get('BACKUP_REPORT_SCHEDULE_MINUTE', '45'))


def main():
    if not USUARIO:
        raise SystemExit('BACKUP_REPORT_USERNAME não configurado.')
    while True:
        agora = datetime.now(FUSO)
        alvo = agora.replace(hour=HORA, minute=MINUTO, second=0, microsecond=0)
        if alvo <= agora:
            alvo += timedelta(days=1)
        time.sleep(max(1, int((alvo - datetime.now(FUSO)).total_seconds())))
        subprocess.run(
            [sys.executable, 'manage.py', 'relatorio_integridade_backup', '--usuario', USUARIO],
            check=False,
        )


if __name__ == '__main__':
    main()
