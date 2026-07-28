"""Agendamento diário da sincronização de processos públicos pelo DataJud."""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


FUSO = ZoneInfo('America/Sao_Paulo')
USUARIO = os.environ.get('DATAJUD_SYNC_USERNAME', '')
HORA = int(os.environ.get('DATAJUD_SYNC_SCHEDULE_HOUR', '7'))
MINUTO = int(os.environ.get('DATAJUD_SYNC_SCHEDULE_MINUTE', '35'))
ATRASO = int(os.environ.get('DATAJUD_SYNC_RETRY_DELAY_MINUTES', '20'))
LIMITE = max(1, int(os.environ.get('DATAJUD_SYNC_MAX_PROCESSOS', '12')))


def proxima_execucao():
    agora = datetime.now(FUSO)
    alvo = agora.replace(hour=HORA, minute=MINUTO, second=0, microsecond=0)
    return alvo + timedelta(days=1) if alvo <= agora else alvo


def main():
    if not USUARIO:
        raise SystemExit('DATAJUD_SYNC_USERNAME não configurado.')
    while True:
        alvo = proxima_execucao()
        print(f'Próxima sincronização DataJud: {alvo.isoformat()}', flush=True)
        time.sleep(max(1, int((alvo - datetime.now(FUSO)).total_seconds())))
        comando = [sys.executable, 'manage.py', 'sincronizar_datajud', '--usuario', USUARIO, '--limite', str(LIMITE)]
        resultado = subprocess.run(comando, check=False)
        if resultado.returncode:
            print(f'DataJud falhou ({resultado.returncode}); nova tentativa em {ATRASO} minuto(s).', flush=True)
            time.sleep(ATRASO * 60)
            subprocess.run(comando, check=False)


if __name__ == '__main__':
    main()
