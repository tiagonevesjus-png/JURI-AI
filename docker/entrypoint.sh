#!/usr/bin/env bash
# Inicialização do container: migrações, admin, estáticos e então o processo (CMD).
set -e

if [ "${SKIP_STARTUP_TASKS:-false}" != "true" ]; then
echo "==> Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

echo "==> Garantindo o usuário administrador (setup_inicial)..."
python manage.py setup_inicial

echo "==> Coletando arquivos estáticos..."
python manage.py collectstatic --noinput
else
echo "==> Tarefas de inicialização delegadas ao serviço web."
fi

echo "==> Iniciando: $*"
exec "$@"
