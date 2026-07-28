import os, subprocess, sys, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo('America/Sao_Paulo')
USUARIO = os.environ.get('PRAZOS_USERNAME', '')
HORA = int(os.environ.get('PRAZOS_SCHEDULE_HOUR', '8'))
MINUTO = int(os.environ.get('PRAZOS_SCHEDULE_MINUTE', '0'))

def main():
    if not USUARIO: raise SystemExit('PRAZOS_USERNAME não configurado.')
    while True:
        agora = datetime.now(FUSO); alvo = agora.replace(hour=HORA, minute=MINUTO, second=0, microsecond=0)
        if alvo <= agora: alvo += timedelta(days=1)
        time.sleep(max(1, int((alvo - datetime.now(FUSO)).total_seconds())))
        subprocess.run([sys.executable, 'manage.py', 'avisar_prazos', '--usuario', USUARIO], check=False)

if __name__ == '__main__': main()
