"""Consulta somente de leitura à API pública do DJEN/Comunica PJe."""

import os
import re
from datetime import date

import requests
from django.utils.dateparse import parse_date
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from gestao.models import Processo, PublicacaoDJEN
from gestao.services.notificacoes import criar as criar_notificacao


BASE_URL = 'https://comunicaapi.pje.jus.br/api/v1/comunicacao'


def _cliente_http():
    """Reexecuta apenas consultas idempotentes após indisponibilidade de rede."""
    sessao = requests.Session()
    sessao.mount('https://', HTTPAdapter(max_retries=Retry(
        total=2,
        connect=2,
        read=1,
        status=1,
        backoff_factor=1,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({'GET'}),
    )))
    return sessao


class DJENError(RuntimeError):
    """Erro controlado de consulta ao DJEN."""


class DJENBloqueioRede(DJENError):
    """A API recusou o IP do servidor e exige a ponte executada no Brasil."""


def configuracao_oab():
    numero = re.sub(r'\D', '', os.environ.get('DJEN_OAB_NUMERO', ''))
    uf = os.environ.get('DJEN_OAB_UF', '').strip().upper()
    if not numero or len(uf) != 2 or not uf.isalpha():
        raise DJENError('Configure DJEN_OAB_NUMERO e DJEN_OAB_UF antes de consultar o DJEN.')
    return numero, uf


def consultar(inicio: date, fim: date, pagina=1):
    """Busca uma página pública; o monitor usa 100 itens por página, conforme a API."""
    if inicio > fim:
        raise DJENError('A data inicial não pode ser posterior à data final.')
    numero, uf = configuracao_oab()
    try:
        resposta = _cliente_http().get(
            BASE_URL,
            params={
                'numeroOab': numero,
                'ufOab': uf,
                'dataDisponibilizacaoInicio': inicio.isoformat(),
                'dataDisponibilizacaoFim': fim.isoformat(),
                'pagina': pagina,
                'itensPorPagina': 100,
                'meio': 'D',
            },
            timeout=(5, 15),
        )
    except requests.RequestException as exc:
        raise DJENError(f'Falha na consulta ao DJEN: {exc}') from exc
    if resposta.status_code == 429:
        raise DJENError('Limite temporário de consultas do DJEN atingido. Aguarde um minuto antes de tentar novamente.')
    if resposta.status_code == 403:
        raise DJENBloqueioRede(
            'O Comunica PJe recusou o IP deste servidor. A consulta foi encaminhada à ponte DJEN no Brasil.'
        )
    try:
        resposta.raise_for_status()
        corpo = resposta.json()
    except (requests.RequestException, ValueError) as exc:
        raise DJENError(f'Resposta inválida do DJEN: {exc}') from exc
    if not isinstance(corpo, dict):
        raise DJENError('Resposta inesperada do DJEN.')
    return corpo


def _identificador(item):
    valor = item.get('id') or item.get('numeroComunicacao') or item.get('hash')
    if valor is None:
        raise DJENError('O DJEN retornou uma comunicação sem identificador.')
    return str(valor)


def _processo_correspondente(user, numero):
    """Compara apenas dígitos, sem depender do formato com máscara do CNJ."""
    if not numero:
        return None
    for processo in Processo.objects.filter(user=user).exclude(numero=''):
        if re.sub(r'\D', '', processo.numero) == numero:
            return processo
    return None


def persistir_itens(user, itens):
    """Persiste uma lista já consultada, mantendo a mesma deduplicação do fluxo direto."""
    novas = 0
    validos = 0
    for item in itens or []:
        if not isinstance(item, dict):
            continue
        validos += 1
        numero = re.sub(r'\D', '', str(item.get('numero_processo') or ''))
        processo = _processo_correspondente(user, numero)
        disponibilidade = parse_date(str(item.get('data_disponibilizacao') or item.get('datadisponibilizacao') or ''))
        _, criada = PublicacaoDJEN.objects.update_or_create(
            user=user,
            identificador_externo=_identificador(item),
            defaults={
                'processo': processo,
                'numero_processo': item.get('numeroprocessocommascara') or item.get('numero_processo') or '',
                'data_disponibilizacao': disponibilidade,
                'tribunal': item.get('siglaTribunal') or '',
                'tipo_comunicacao': item.get('tipoComunicacao') or '',
                'orgao': item.get('nomeOrgao') or '',
                'texto': item.get('texto') or '',
                'link': item.get('link') or '',
                'dados': item,
            },
        )
        if criada:
            novas += 1
            criar_notificacao(user, 'DJEN', f'Nova publicação DJEN: {item.get("siglaTribunal") or "tribunal"}',
                              (item.get('tipoComunicacao') or item.get('texto') or 'Nova comunicação processual.')[:2000],
                              prioridade='ALTA', link=item.get('link') or '', dados={'identificador': _identificador(item)})
    return novas, validos


def sincronizar(user, inicio: date, fim: date):
    """Consulta e persiste comunicações públicas do DJEN."""
    corpo = consultar(inicio, fim)
    return persistir_itens(user, corpo.get('items') or [])
