"""Executa a triagem depois dos monitores de DJEN, Google e DataJud."""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


FUSO = ZoneInfo('America/Sao_Paulo')
USUARIO = os.environ.get('TRIAGEM_USERNAME', '')
HORA = int(os.environ.get('TRIAGEM_SCHEDULE_HOUR', '7'))
MINUTO = int(os.environ.get('TRIAGEM_SCHEDULE_MINUTE', '50'))


def proxima_execucao():
    agora = datetime.now(FUSO)
    alvo = agora.replace(hour=HORA, minute=MINUTO, second=0, microsecond=0)
    return alvo + timedelta(days=1) if alvo <= agora else alvo


def main():
    if not USUARIO:
        raise SystemExit('TRIAGEM_USERNAME não configurado.')
    while True:
        alvo = proxima_execucao()
        print(f'Próxima triagem jurídica: {alvo.isoformat()}', flush=True)
        time.sleep(max(1, int((alvo - datetime.now(FUSO)).total_seconds())))
        subprocess.run([sys.executable, 'manage.py', 'triagem_juridica', '--usuario', USUARIO], check=False)


if __name__ == '__main__':
    main()
