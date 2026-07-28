import os
import re
import hashlib

import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime


BASE_URL = 'https://api-publica.datajud.cnj.jus.br'


class DataJudError(RuntimeError):
    pass


def numero_cnj_limpo(numero):
    valor = re.sub(r'\D', '', numero or '')
    if len(valor) != 20:
        raise DataJudError('Informe um numero CNJ valido, com 20 digitos.')
    return valor


def alias_por_numero(numero):
    cnj = numero_cnj_limpo(numero)
    ramo, tribunal = cnj[13], cnj[14:16]
    if ramo == '4':
        return f'api_publica_trf{int(tribunal)}'
    if ramo == '5':
        return f'api_publica_trt{int(tribunal)}'
    if ramo == '8':
        estados = {'10': 'tjma', '07': 'tjdft', '18': 'tjpr', '19': 'tjrj', '26': 'tjsp'}
        if tribunal in estados:
            return f"api_publica_{estados[tribunal]}"
    raise DataJudError('Defina o alias DataJud do tribunal antes de sincronizar este processo.')


def consultar(numero, alias=''):
    chave = os.environ.get('DATAJUD_API_KEY', '')
    if not chave:
        raise DataJudError('DATAJUD_API_KEY nao configurada.')
    cnj = numero_cnj_limpo(numero)
    alias = (alias or alias_por_numero(cnj)).strip().lower().strip('/')
    if not re.fullmatch(r'api_publica_[a-z0-9-]+', alias):
        raise DataJudError('Alias DataJud invalido.')
    try:
        resposta = requests.post(
            f'{BASE_URL}/{alias}/_search',
            headers={'Authorization': f'APIKey {chave}', 'Content-Type': 'application/json'},
            json={'size': 100, 'query': {'match': {'numeroProcesso': cnj}}}, timeout=(5, 30))
        resposta.raise_for_status()
    except requests.RequestException as exc:
        raise DataJudError('Falha de conexão com o DataJud; a rotina tentará novamente.') from exc
    corpo = resposta.json()
    if corpo.get('timed_out') or corpo.get('_shards', {}).get('failed', 0):
        raise DataJudError('Resposta parcial do DataJud; tente novamente mais tarde.')
    return corpo.get('hits', {}).get('hits', [])


def sincronizar(processo):
    resultados = consultar(processo.numero, processo.datajud_alias)
    adicionadas = 0
    for resultado in resultados:
        for movimento in resultado.get('_source', {}).get('movimentos') or []:
            descricao = movimento.get('nome') or 'Movimentacao sem descricao'
            instante = parse_datetime(movimento.get('dataHora') or '')
            if instante and timezone.is_naive(instante):
                instante = timezone.make_aware(instante)
            referencia = hashlib.sha256(
                f"{resultado.get('_id','')}|{movimento.get('codigo','')}|{movimento.get('dataHora','')}|{descricao}".encode()
            ).hexdigest()
            _, criada = processo.movimentacoes.get_or_create(
                referencia_externa=referencia,
                defaults={
                    'data': instante.date() if instante else timezone.localdate(),
                    'data_hora': instante,
                    'descricao': descricao,
                    'fonte': 'DATAJUD',
                    'codigo_tpu': str(movimento.get('codigo', '')),
                },
            )
            adicionadas += int(criada)
    processo.ultima_sincronizacao_datajud = timezone.now()
    processo.save(update_fields=['ultima_sincronizacao_datajud', 'atualizado_em'])
    return adicionadas
