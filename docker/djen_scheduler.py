"""Executa uma única consulta diária do DJEN, no horário local configurado."""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


FUSO = ZoneInfo('America/Sao_Paulo')
USUARIO = os.environ.get('DJEN_USERNAME', '')
HORA = int(os.environ.get('DJEN_SCHEDULE_HOUR', '7'))
MINUTO = int(os.environ.get('DJEN_SCHEDULE_MINUTE', '10'))
ATRASO_REPETICAO_MINUTOS = int(os.environ.get('DJEN_RETRY_DELAY_MINUTES', '15'))


def proxima_execucao():
    agora = datetime.now(FUSO)
    alvo = agora.replace(hour=HORA, minute=MINUTO, second=0, microsecond=0)
    if alvo <= agora:
        alvo += timedelta(days=1)
    return alvo


def main():
    if not USUARIO:
        raise SystemExit('DJEN_USERNAME não configurado.')
    if not 0 <= HORA <= 23 or not 0 <= MINUTO <= 59:
        raise SystemExit('Horário DJEN inválido.')
    while True:
        alvo = proxima_execucao()
        espera = max(1, int((alvo - datetime.now(FUSO)).total_seconds()))
        print(f'Próxima sincronização DJEN: {alvo.isoformat()}', flush=True)
        time.sleep(espera)
        comando = [sys.executable, 'manage.py', 'sincronizar_djen', '--usuario', USUARIO, '--dias', '1']
        resultado = subprocess.run(comando, check=False)
        if resultado.returncode:
            print(f'Sincronização DJEN terminou com código {resultado.returncode}.', flush=True)
            print(f'Nova tentativa em {ATRASO_REPETICAO_MINUTOS} minuto(s).', flush=True)
            time.sleep(ATRASO_REPETICAO_MINUTOS * 60)
            resultado = subprocess.run(comando, check=False)
            if resultado.returncode:
                print('A segunda tentativa também falhou; a rotina será retomada no próximo dia.', flush=True)


if __name__ == '__main__':
    main()
