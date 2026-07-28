#!/bin/sh
set -eu

HORA="${BACKUP_SCHEDULE_HOUR:-3}"
MINUTO="${BACKUP_SCHEDULE_MINUTE:-30}"
RETENCAO="${BACKUP_RETENTION_DAYS:-30}"
DIA_TESTE="${BACKUP_RESTORE_VERIFY_DAY:-1}"
DESTINO="/backups"
ARQUIVO_ATUAL=""

mkdir -p "$DESTINO"

executar_backup() {
  hoje="$(TZ=America/Sao_Paulo date +%F)"
  temporario="$DESTINO/juriai-${hoje}.sql.gz.tmp"
  final="$DESTINO/juriai-${hoje}.sql.gz"
  export PGPASSWORD="$POSTGRES_PASSWORD"
  echo "Iniciando backup local: ${final}"
  pg_dump -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$temporario"
  mv "$temporario" "$final"
  ARQUIVO_ATUAL="$final"
  find "$DESTINO" -type f -name 'juriai-*.sql.gz' -mtime "+$RETENCAO" -delete
  echo "Backup concluído: ${final}"
}

registrar_integridade() {
  restauracao="$1"
  hoje="$(TZ=America/Sao_Paulo date +%F)"
  temporario="$DESTINO/integridade-${hoje}.json.tmp"
  final="$DESTINO/integridade-${hoje}.json"
  cat > "$temporario" <<EOF
{"backup":"ok","restauracao":"${restauracao}","arquivo":"${ARQUIVO_ATUAL}","gerado_em":"$(TZ=America/Sao_Paulo date -Iseconds)"}
EOF
  mv "$temporario" "$final"
  echo "Integridade registrada: ${final}"
}

testar_restauracao() {
  arquivo="$1"
  banco_teste="juriai_restore_verify"
  export PGPASSWORD="$POSTGRES_PASSWORD"
  echo "Testando restauração isolada: ${arquivo}"
  dropdb -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" --if-exists "$banco_teste"
  createdb -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" "$banco_teste"
  if ! gunzip -c "$arquivo" | psql -v ON_ERROR_STOP=1 -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" "$banco_teste" >/dev/null; then
    dropdb -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" --if-exists "$banco_teste"
    return 1
  fi
  psql -v ON_ERROR_STOP=1 -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" "$banco_teste" -Atc "SELECT 1 FROM django_migrations LIMIT 1" >/dev/null
  dropdb -h db -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" --if-exists "$banco_teste"
  echo "Restauração isolada validada."
}

if [ "${1:-}" = "--once" ]; then
  executar_backup
  if testar_restauracao "$ARQUIVO_ATUAL"; then
    registrar_integridade "validada"
  else
    registrar_integridade "falhou"
    exit 1
  fi
  exit 0
fi

ultimo_dia=""
while true; do
  hoje="$(TZ=America/Sao_Paulo date +%F)"
  horario="$(TZ=America/Sao_Paulo date +%H:%M)"
  if [ "$horario" = "${HORA}:${MINUTO}" ] && [ "$ultimo_dia" != "$hoje" ]; then
    executar_backup
    restauracao="nao_executada"
    if [ "$(TZ=America/Sao_Paulo date +%d | sed 's/^0//')" = "$DIA_TESTE" ]; then
      if testar_restauracao "$ARQUIVO_ATUAL"; then
        restauracao="validada"
      else
        restauracao="falhou"
        echo "ERRO: teste de restauração falhou."
      fi
    fi
    registrar_integridade "$restauracao"
    ultimo_dia="$hoje"
  fi
  sleep 30
done
