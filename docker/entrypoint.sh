#!/usr/bin/env bash
# Inicialização do container: migrações, admin, estáticos e então o processo (CMD).
set -e

echo "==> Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

echo "==> Garantindo o usuário administrador (setup_inicial)..."
python manage.py setup_inicial

echo "==> Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "==> Registrando agendamento de sincronização com o PJe..."
python manage.py agendar_pje || echo "  (agendamento do PJe ignorado)"

echo "==> Iniciando: $*"
exec "$@"
