#!/bin/sh
# Backup local diário do PostgreSQL. Mantém apenas arquivos compactados recentes.
set -eu

HORA="${BACKUP_SCHEDULE_HOUR:-3}"
MINUTO="${BACKUP_SCHEDULE_MINUTE:-30}"
RETENCAO="${BACKUP_RETENTION_DAYS:-30}"
DESTINO="/backups"

mkdir -p "$DESTINO"

executar_backup() {
  hoje="$(TZ=America/Sao_Paulo date +%F)"
  temporario="$DESTINO/juriai-${hoje}.sql.gz.tmp"
  final="$DESTINO/juriai-${hoje}.sql.gz"
  export PGPASSWORD="$POSTGRES_PASSWORD"
  echo "Iniciando backup local: ${final}"
  pg_dump -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$temporario"
  mv "$temporario" "$final"
  find "$DESTINO" -type f -name 'juriai-*.sql.gz' -mtime "+$RETENCAO" -delete
  echo "Backup concluído: ${final}"
}

if [ "${1:-}" = "--once" ]; then
  executar_backup
  exit 0
fi

ultimo_dia=""
while true; do
  hoje="$(TZ=America/Sao_Paulo date +%F)"
  horario="$(TZ=America/Sao_Paulo date +%H:%M)"
  if [ "$horario" = "${HORA}:${MINUTO}" ] && [ "$ultimo_dia" != "$hoje" ]; then
    executar_backup
    ultimo_dia="$hoje"
  fi
  sleep 30
done
