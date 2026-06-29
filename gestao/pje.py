"""Automação do PJe via API Pública do DataJud (CNJ).

O DataJud (https://www.cnj.jus.br/sistemas/datajud/api-publica/) é a base
nacional de dados do Poder Judiciário mantida pelo CNJ. A *API Pública*
disponibiliza, de forma gratuita e sem credenciais por tribunal, os metadados
processuais (classe, assunto, órgão julgador) e — o mais útil para o
escritório — o histórico de **movimentações** de cada processo, consultado
pelo número único CNJ.

Este módulo é a camada de automação: dado um número de processo no padrão
CNJ, descobre o tribunal, consulta a API e devolve os dados já normalizados.
A gravação no banco (modelo ``MovimentacaoProcesso``) fica em ``tasks.py``.

Decisões de projeto, no mesmo espírito do app ``ia``:

* ``requests`` é importado de forma tardia (lazy) — se o pacote não estiver
  instalado, a automação fica indisponível sem quebrar o resto do sistema.
* Toda a configuração vem de ``settings`` (com fallback para variável de
  ambiente), via o helper ``_conf``.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger(__name__)


class PJeIndisponivel(RuntimeError):
    """Levantada quando a consulta ao DataJud não pode ser realizada."""


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
def _conf(nome, padrao=''):
    return getattr(settings, nome, os.environ.get(nome, padrao))


# Chave pública da API do DataJud, divulgada pelo próprio CNJ na documentação
# oficial da API Pública. Não é um segredo do escritório: é compartilhada por
# todos os consumidores da API pública. Pode ser sobrescrita por ``DATAJUD_API_KEY``.
CHAVE_PUBLICA_DATAJUD = (
    'cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=='
)

URL_BASE_DATAJUD = 'https://api-publica.datajud.cnj.jus.br'


def api_configurada() -> bool:
    """A automação do PJe depende apenas do pacote ``requests`` + uma chave.

    A chave tem um padrão público embutido, então na prática basta o pacote
    estar instalado. Mantido como função para simetria com ``ia.services``.
    """
    return bool(_conf('DATAJUD_API_KEY', CHAVE_PUBLICA_DATAJUD))


# ---------------------------------------------------------------------------
# Número CNJ
# ---------------------------------------------------------------------------
# Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO (20 dígitos no total).
#   NNNNNNN  sequencial (7)
#   DD       dígito verificador (2)
#   AAAA     ano de ajuizamento (4)
#   J        segmento do Judiciário (1)
#   TR       tribunal (2)
#   OOOO     unidade de origem (4)
_RE_NAO_DIGITO = re.compile(r'\D')


def limpar_numero(numero: str) -> str:
    """Remove máscara e devolve só os dígitos do número CNJ."""
    return _RE_NAO_DIGITO.sub('', numero or '')


def numero_valido(numero: str) -> bool:
    return len(limpar_numero(numero)) == 20


def formatar_numero(numero: str) -> str:
    """Aplica a máscara CNJ a um número com 20 dígitos (senão devolve original)."""
    d = limpar_numero(numero)
    if len(d) != 20:
        return numero
    return f'{d[0:7]}-{d[7:9]}.{d[9:13]}.{d[13:14]}.{d[14:16]}.{d[16:20]}'


# Segmento '8' (Justiça Estadual): TR -> sigla do TJ (alias do DataJud).
_TJ_POR_TR = {
    '01': 'tjac', '02': 'tjal', '03': 'tjap', '04': 'tjam', '05': 'tjba',
    '06': 'tjce', '07': 'tjdft', '08': 'tjes', '09': 'tjgo', '10': 'tjma',
    '11': 'tjmt', '12': 'tjms', '13': 'tjmg', '14': 'tjpa', '15': 'tjpb',
    '16': 'tjpr', '17': 'tjpe', '18': 'tjpi', '19': 'tjrj', '20': 'tjrn',
    '21': 'tjrs', '22': 'tjro', '23': 'tjrr', '24': 'tjsc', '25': 'tjse',
    '26': 'tjsp', '27': 'tjto',
}

# Segmento '9' (Justiça Militar Estadual): TR -> alias.
_TJM_POR_TR = {'13': 'tjmmg', '21': 'tjmrs', '26': 'tjmsp'}


def tribunal_para_numero(numero: str) -> str | None:
    """Descobre o *alias* do DataJud a partir do número CNJ.

    Devolve, por exemplo, ``'api_publica_tjsp'``. Retorna ``None`` quando o
    tribunal não é coberto pela API Pública / não é reconhecido.
    """
    d = limpar_numero(numero)
    if len(d) != 20:
        return None

    segmento = d[13]
    tr = d[14:16]

    alias = None
    if segmento == '1':            # STF
        alias = None               # STF não publica na API Pública do DataJud
    elif segmento == '3':          # STJ
        alias = 'stj'
    elif segmento == '4':          # Justiça Federal -> TRF1..TRF6
        n = int(tr)
        if 1 <= n <= 6:
            alias = f'trf{n}'
    elif segmento == '5':          # Justiça do Trabalho
        n = int(tr)
        if tr == '00':
            alias = 'tst'
        elif 1 <= n <= 24:
            alias = f'trt{n}'
    elif segmento == '6':          # Justiça Eleitoral
        if tr == '00':
            alias = 'tse'
        else:
            sigla = _TJ_POR_TR.get(tr)
            if sigla:
                alias = f'tre_{sigla[2:]}'  # tre_sp, tre_rj, ...
    elif segmento == '7':          # Justiça Militar da União
        alias = 'stm'
    elif segmento == '8':          # Justiça Estadual
        alias = _TJ_POR_TR.get(tr)
    elif segmento == '9':          # Justiça Militar Estadual
        alias = _TJM_POR_TR.get(tr)

    return f'api_publica_{alias}' if alias else None


# ---------------------------------------------------------------------------
# Resultado da consulta (normalizado)
# ---------------------------------------------------------------------------
@dataclass
class Movimento:
    codigo: str
    descricao: str
    data: object  # date | None


@dataclass
class ConsultaProcesso:
    numero: str
    tribunal: str = ''
    classe: str = ''
    assunto: str = ''
    orgao_julgador: str = ''
    grau: str = ''
    data_ajuizamento: object = None
    movimentos: list = field(default_factory=list)

    @property
    def total_movimentos(self) -> int:
        return len(self.movimentos)


# ---------------------------------------------------------------------------
# Consulta à API
# ---------------------------------------------------------------------------
def _parse_data(valor):
    """Converte uma data ISO do DataJud (ex.: '2018-05-30T00:00:00.000Z') em ``date``."""
    if not valor:
        return None
    from datetime import datetime

    texto = str(valor).strip().replace('Z', '+00:00')
    for parse in (datetime.fromisoformat,):
        try:
            return parse(texto).date()
        except ValueError:
            pass
    # Fallback: apenas os 10 primeiros caracteres (YYYY-MM-DD).
    try:
        return datetime.strptime(texto[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _maior_nome(item, *chaves):
    """Extrai um nome legível de um dict que pode ter 'nome'/'descricao'."""
    if not isinstance(item, dict):
        return ''
    for chave in chaves:
        valor = item.get(chave)
        if valor:
            return str(valor)
    return ''


def _normalizar_fonte(fonte: dict) -> ConsultaProcesso:
    """Transforma o ``_source`` retornado pelo DataJud em ``ConsultaProcesso``."""
    movimentos = []
    for mov in fonte.get('movimentos', []) or []:
        movimentos.append(
            Movimento(
                codigo=str(mov.get('codigo', '')),
                descricao=_maior_nome(mov, 'nome', 'descricao'),
                data=_parse_data(mov.get('dataHora')),
            )
        )
    # Ordena do mais antigo para o mais recente (data ausente vai para o fim).
    from datetime import date

    movimentos.sort(key=lambda m: m.data or date.min)

    assuntos = fonte.get('assuntos') or []
    assunto = _maior_nome(assuntos[0], 'nome') if assuntos else ''

    return ConsultaProcesso(
        numero=str(fonte.get('numeroProcesso', '')),
        tribunal=str(fonte.get('tribunal', '')),
        classe=_maior_nome(fonte.get('classe'), 'nome'),
        assunto=assunto,
        orgao_julgador=_maior_nome(fonte.get('orgaoJulgador'), 'nome'),
        grau=str(fonte.get('grau', '')),
        data_ajuizamento=_parse_data(fonte.get('dataAjuizamento')),
        movimentos=movimentos,
    )


def consultar(numero: str, *, timeout: int = 30) -> ConsultaProcesso | None:
    """Consulta um processo na API Pública do DataJud pelo número CNJ.

    Retorna ``ConsultaProcesso`` ou ``None`` se o processo não for encontrado.
    Levanta ``PJeIndisponivel`` em erros de configuração/rede/tribunal.
    """
    digitos = limpar_numero(numero)
    if len(digitos) != 20:
        raise PJeIndisponivel(
            f'Número CNJ inválido (esperados 20 dígitos): {numero!r}'
        )

    alias = tribunal_para_numero(digitos)
    if not alias:
        raise PJeIndisponivel(
            'Tribunal não suportado pela API Pública do DataJud para o '
            f'número {formatar_numero(digitos)}.'
        )

    try:
        import requests
    except Exception as exc:  # pacote ausente
        raise PJeIndisponivel('Pacote requests não instalado.') from exc

    chave = _conf('DATAJUD_API_KEY', CHAVE_PUBLICA_DATAJUD)
    base = _conf('DATAJUD_API_URL', URL_BASE_DATAJUD).rstrip('/')
    url = f'{base}/{alias}/_search'
    headers = {
        'Authorization': f'APIKey {chave}',
        'Content-Type': 'application/json',
    }
    payload = {'query': {'match': {'numeroProcesso': digitos}}, 'size': 1}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except Exception as exc:  # erro de rede
        raise PJeIndisponivel(f'Falha de rede ao consultar o DataJud: {exc}') from exc

    if resp.status_code == 401:
        raise PJeIndisponivel('Chave da API do DataJud rejeitada (HTTP 401).')
    if resp.status_code != 200:
        raise PJeIndisponivel(
            f'DataJud respondeu HTTP {resp.status_code} para o tribunal {alias}.'
        )

    try:
        dados = resp.json()
    except ValueError as exc:
        raise PJeIndisponivel('Resposta do DataJud não é um JSON válido.') from exc

    hits = (dados.get('hits') or {}).get('hits') or []
    if not hits:
        logger.info('Processo %s não encontrado no DataJud (%s).', digitos, alias)
        return None

    return _normalizar_fonte(hits[0].get('_source') or {})
