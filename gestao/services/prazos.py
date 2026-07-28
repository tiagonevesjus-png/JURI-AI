"""Avisos de prazo: apenas para prazos cadastrados e confirmados por pessoa."""

from datetime import timedelta

from django.db import models
from django.utils import timezone

from gestao.models import FeriadoForense, Prazo
from gestao.services.notificacoes import criar


MARCOS = (10, 5, 3, 1, 0)


def _feriados_aplicaveis(prazo):
    processo = prazo.processo
    tribunal = (processo.tribunal if processo else '').strip().upper()
    comarca = (processo.comarca if processo else '').strip().upper()
    itens = FeriadoForense.objects.filter(ativo=True).filter(
        models.Q(abrangencia='NACIONAL') |
        models.Q(abrangencia='ESTADUAL_MA') |
        models.Q(abrangencia='TRIBUNAL', tribunal__iexact=tribunal) |
        models.Q(abrangencia='LOCAL', comarca__iexact=comarca)
    )
    return {item.data: item for item in itens}


def dias_uteis_restantes(prazo, referencia=None):
    """Contagem de apoio; a data fatal é sempre confirmada por pessoa."""
    referencia = referencia or timezone.localdate()
    if prazo.data_fatal <= referencia:
        return 0 if prazo.data_fatal == referencia else -1
    feriados = _feriados_aplicaveis(prazo)
    cursor, total = referencia + timedelta(days=1), 0
    while cursor <= prazo.data_fatal:
        if cursor.weekday() < 5 and cursor not in feriados:
            total += 1
        cursor += timedelta(days=1)
    return total


def emitir_avisos(user):
    """Emite cada marco uma vez; a data fatal é sempre informada pelo usuário."""
    hoje = timezone.localdate()
    enviados = 0
    for prazo in Prazo.objects.filter(user=user, status='PENDENTE', confirmado_em__isnull=False).select_related('processo'):
        dias = dias_uteis_restantes(prazo, hoje) if prazo.regra_contagem == 'UTEIS' else (prazo.data_fatal - hoje).days
        if dias not in MARCOS or dias in prazo.avisos_enviados:
            continue
        titulo = 'Prazo vence hoje' if dias == 0 else f'Prazo vence em {dias} dia(s)'
        processo = prazo.processo.numero if prazo.processo and prazo.processo.numero else (prazo.processo.titulo if prazo.processo else 'sem processo vinculado')
        criar(user, 'PRAZO', titulo, f'{prazo.titulo} · {processo}. Data fatal confirmada: {prazo.data_fatal:%d/%m/%Y}.',
              prioridade='URGENTE' if dias <= 1 else 'ALTA', link='/prazos/',
              dados={'dedup_key': f'prazo:{prazo.id}:{dias}', 'prazo_id': prazo.id, 'dias_restantes': dias})
        prazo.avisos_enviados = [*prazo.avisos_enviados, dias]
        prazo.save(update_fields=['avisos_enviados'])
        enviados += 1
    return enviados
