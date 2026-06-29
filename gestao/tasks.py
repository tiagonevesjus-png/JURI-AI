"""Tarefas de automação do PJe (executadas via django-q).

Consultam a API Pública do DataJud (ver ``gestao.pje``) e gravam as
movimentações no processo, evitando duplicidade. Podem ser disparadas:

* pela interface (botão "Sincronizar com PJe" na tela do processo);
* em lote, pelo management command ``sincronizar_pje``;
* agendadas periodicamente (django-q Schedule).
"""

import logging

from django.utils import timezone

from . import pje

logger = logging.getLogger(__name__)


def sincronizar_processo_pje(processo_id):
    """Consulta o DataJud e importa as movimentações novas de um processo.

    Retorna um dicionário com o resultado (``importadas``, ``total`` etc.),
    útil tanto para a task assíncrona quanto para a chamada síncrona da view.
    """
    from .models import Processo, MovimentacaoProcesso

    resultado = {
        'processo_id': processo_id,
        'ok': False,
        'importadas': 0,
        'total': 0,
        'mensagem': '',
    }

    try:
        processo = Processo.objects.get(id=processo_id)
    except Processo.DoesNotExist:
        resultado['mensagem'] = 'Processo não encontrado.'
        logger.warning('Processo %s não encontrado para sincronização PJe.', processo_id)
        return resultado

    if not pje.numero_valido(processo.numero):
        resultado['mensagem'] = 'Processo sem número CNJ válido (20 dígitos).'
        return resultado

    try:
        consulta = pje.consultar(processo.numero)
    except pje.PJeIndisponivel as exc:
        resultado['mensagem'] = str(exc)
        logger.info('Sincronização PJe indisponível para o processo %s: %s', processo_id, exc)
        return resultado
    except Exception as exc:  # falha inesperada não deve derrubar o worker
        resultado['mensagem'] = f'Erro inesperado: {exc}'
        logger.exception('Falha ao sincronizar processo %s com o PJe: %s', processo_id, exc)
        return resultado

    if consulta is None:
        resultado['ok'] = True
        resultado['mensagem'] = 'Processo não localizado no DataJud.'
        Processo.objects.filter(id=processo.id).update(pje_sincronizado_em=timezone.now())
        return resultado

    # Conjunto das movimentações PJe já gravadas (dedup por código + data).
    existentes = set(
        MovimentacaoProcesso.objects
        .filter(processo=processo, origem='PJE')
        .values_list('codigo_movimento', 'data')
    )

    novas = []
    for mov in consulta.movimentos:
        chave = (mov.codigo or '', mov.data)
        if chave in existentes:
            continue
        existentes.add(chave)
        novas.append(MovimentacaoProcesso(
            processo=processo,
            data=mov.data or timezone.localdate(),
            descricao=mov.descricao or '(movimento sem descrição)',
            origem='PJE',
            codigo_movimento=mov.codigo or '',
        ))

    if novas:
        MovimentacaoProcesso.objects.bulk_create(novas)

    # Completa metadados do processo se ainda estiverem vazios.
    campos = {'pje_sincronizado_em': timezone.now()}
    if not processo.tribunal and consulta.tribunal:
        campos['tribunal'] = consulta.tribunal[:255]
    if not processo.vara and consulta.orgao_julgador:
        campos['vara'] = consulta.orgao_julgador[:255]
    if not processo.tipo_acao and consulta.classe:
        campos['tipo_acao'] = consulta.classe[:255]
    if processo.data_distribuicao is None and consulta.data_ajuizamento:
        campos['data_distribuicao'] = consulta.data_ajuizamento
    Processo.objects.filter(id=processo.id).update(**campos)

    resultado.update(
        ok=True,
        importadas=len(novas),
        total=consulta.total_movimentos,
        mensagem=(
            f'{len(novas)} movimentação(ões) nova(s) importada(s) '
            f'de {consulta.total_movimentos} no DataJud.'
        ),
    )
    logger.info('Processo %s sincronizado: %s', processo_id, resultado['mensagem'])
    return resultado


def sincronizar_monitorados(user_id=None):
    """Sincroniza todos os processos com ``monitorar_pje`` e número CNJ válido.

    Pensada para agendamento periódico. ``user_id`` restringe a um usuário.
    """
    from .models import Processo

    qs = Processo.objects.filter(monitorar_pje=True).exclude(numero='')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)

    total = importadas = 0
    for processo in qs.iterator():
        if not pje.numero_valido(processo.numero):
            continue
        total += 1
        res = sincronizar_processo_pje(processo.id)
        importadas += res.get('importadas', 0)

    logger.info('Sincronização em lote: %s processo(s), %s movimentação(ões) nova(s).',
                total, importadas)
    return {'processos': total, 'importadas': importadas}
