"""Triagem jurídica assistida por OpenAI e consolidação de alertas.

O módulo trabalha somente com metadados que já foram armazenados localmente
pelos conectores oficiais. A classificação é uma sugestão operacional e nunca
constitui contagem de prazo, ciência de intimação ou orientação jurídica final.
"""

import json
import os
import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from gestao.models import ItemGoogle, MovimentacaoProcesso, Processo, PublicacaoDJEN, TriagemJuridica
from gestao.services.notificacoes import criar as criar_notificacao


class TriagemError(RuntimeError):
    """Erro controlado para que a rotina de monitoramento continue operando."""


CATEGORIAS = {'SENTENCA', 'INTIMACAO', 'AUDIENCIA', 'PRAZO', 'RECURSO', 'JUNTADA', 'OUTRO'}
PRIORIDADES = {'BAIXA', 'NORMAL', 'ALTA', 'URGENTE'}
CRITICAS = {'SENTENCA', 'INTIMACAO', 'AUDIENCIA', 'PRAZO', 'RECURSO'}
INFORMATIVAS = {'JUNTADA', 'OUTRO'}


def _texto_limitado(valor, limite=6000):
    return re.sub(r'\s+', ' ', valor or '').strip()[:limite]


def _aplicar_politica(resultado):
    """A regra operacional prevalece sobre a sugestão do modelo de IA."""
    categoria = resultado.get('categoria', 'OUTRO')
    if categoria in CRITICAS:
        resultado['prioridade'] = 'URGENTE'
    elif categoria in INFORMATIVAS:
        resultado['prioridade'] = 'BAIXA'
    return resultado


def _categoria_local(texto):
    normalizado = (texto or '').lower()
    regras = [
        ('SENTENCA', 'URGENTE', ('sentença', 'sentenca')),
        ('INTIMACAO', 'ALTA', ('intimação', 'intimacao', 'intimado')),
        ('AUDIENCIA', 'ALTA', ('audiência', 'audiencia')),
        ('PRAZO', 'ALTA', ('prazo', 'manifestação', 'manifestacao')),
        ('RECURSO', 'ALTA', ('recurso', 'apelação', 'apelacao', 'agravo')),
        ('JUNTADA', 'BAIXA', ('juntada', 'anexação', 'anexacao')),
    ]
    for categoria, prioridade, termos in regras:
        if any(termo in normalizado for termo in termos):
            return categoria, prioridade
    return 'OUTRO', 'NORMAL'


def _fallback(evento):
    categoria, prioridade = _categoria_local(f"{evento['titulo']} {evento['texto']}")
    resumo = _texto_limitado(evento['texto'] or evento['titulo'], 700)
    return {
        'categoria': categoria,
        'prioridade': prioridade,
        'resumo': resumo or 'Evento registrado para conferência.',
        'providencia_sugerida': 'Conferir a fonte oficial e avaliar a providência cabível.',
        'confianca': Decimal('0.400'),
        'modelo': 'regras-locais',
    }


def _classificar_openai(evento):
    """Pede JSON curto ao modelo, sem criar prazo automaticamente."""
    if os.environ.get('OPENAI_TRIAGEM_ENABLED', 'false').lower() not in ('1', 'true', 'yes', 'on'):
        return _fallback(evento)
    chave = os.environ.get('OPENAI_API_KEY', '').strip()
    if not chave:
        return _fallback(evento)
    try:
        from openai import OpenAI
        cliente = OpenAI(api_key=chave)
        instrucao = (
            'Você é um assistente de triagem jurídica brasileira. Classifique o evento apenas como '
            'SENTENCA, INTIMACAO, AUDIENCIA, PRAZO, RECURSO, JUNTADA ou OUTRO. '
            'Não invente fatos, não calcule prazo e não afirme que há prazo fatal. '
            'Retorne JSON com categoria, prioridade (BAIXA/NORMAL/ALTA/URGENTE), resumo, '
            'providencia_sugerida e confianca de 0 a 1. A providência deve exigir conferência humana.'
        )
        conteudo = json.dumps({
            'fonte': evento['fonte'], 'titulo': evento['titulo'], 'conteudo': evento['texto'],
            'processo': evento.get('processo_numero', ''),
        }, ensure_ascii=False)
        resposta = cliente.chat.completions.create(
            model=os.environ.get('OPENAI_TRIAGEM_MODEL', 'gpt-4.1-mini'),
            response_format={'type': 'json_object'},
            temperature=0,
            messages=[
                {'role': 'system', 'content': instrucao},
                {'role': 'user', 'content': conteudo},
            ],
        )
        dados = json.loads(resposta.choices[0].message.content or '{}')
        categoria = str(dados.get('categoria', 'OUTRO')).upper()
        prioridade = str(dados.get('prioridade', 'NORMAL')).upper()
        confianca = Decimal(str(dados.get('confianca', '0.5'))).quantize(Decimal('0.001'))
        return {
            'categoria': categoria if categoria in CATEGORIAS else 'OUTRO',
            'prioridade': prioridade if prioridade in PRIORIDADES else 'NORMAL',
            'resumo': _texto_limitado(str(dados.get('resumo', '')), 1200),
            'providencia_sugerida': _texto_limitado(str(dados.get('providencia_sugerida', '')), 1200),
            'confianca': min(max(confianca, Decimal('0')), Decimal('1')),
            'modelo': os.environ.get('OPENAI_TRIAGEM_MODEL', 'gpt-4.1-mini'),
        }
    except Exception as exc:  # uma falha externa não impede alertas locais
        resultado = _fallback(evento)
        resultado['erro_modelo'] = type(exc).__name__
        return resultado


def _numeros_cnj(texto):
    return {re.sub(r'\D', '', achado) for achado in re.findall(r'(?:\d\D*){20}', texto or '')
            if len(re.sub(r'\D', '', achado)) == 20}


def _processos_por_numero(user):
    return {
        re.sub(r'\D', '', processo.numero): processo
        for processo in Processo.objects.filter(user=user).exclude(numero='')
    }


def _eventos(user, desde):
    """Converte os quatro conectores em eventos homogêneos e vinculados a processo."""
    numeros = _processos_por_numero(user)
    eventos = []
    for item in MovimentacaoProcesso.objects.filter(processo__user=user, criado_em__gte=desde).select_related('processo'):
        eventos.append({
            'fonte': 'DATAJUD', 'identificador': str(item.id), 'processo': item.processo,
            'processo_numero': item.processo.numero, 'titulo': item.descricao[:500],
            'texto': item.descricao, 'link': f'/processos/{item.processo_id}/',
        })
    for item in PublicacaoDJEN.objects.filter(user=user, criado_em__gte=desde).select_related('processo'):
        processo = item.processo or numeros.get(re.sub(r'\D', '', item.numero_processo))
        eventos.append({
            'fonte': 'DJEN', 'identificador': item.identificador_externo, 'processo': processo,
            'processo_numero': item.numero_processo, 'titulo': f'{item.tribunal} — {item.tipo_comunicacao}'[:500],
            'texto': _texto_limitado(item.texto, 6000), 'link': item.link or (f'/processos/{processo.id}/' if processo else ''),
        })
    for item in ItemGoogle.objects.filter(user=user, criado_em__gte=desde):
        texto = f'{item.titulo}\n{item.resumo}'
        processo = next((numeros[numero] for numero in _numeros_cnj(texto) if numero in numeros), None)
        eventos.append({
            'fonte': item.fonte, 'identificador': item.identificador_externo, 'processo': processo,
            'processo_numero': processo.numero if processo else '', 'titulo': item.titulo,
            'texto': _texto_limitado(texto, 6000), 'link': item.link,
        })
    return eventos


def _consolidar_alertas(user, triagens):
    """Emite no máximo um alerta externo diário por processo, reunindo fontes."""
    hoje = timezone.localdate().isoformat()
    grupos = defaultdict(list)
    for triagem in triagens:
        if triagem.processo_id:
            grupos[triagem.processo_id].append(triagem)
    criados = 0
    for processo_id, itens in grupos.items():
        processo = itens[0].processo
        prioridade = max((item.prioridade for item in itens), key=lambda p: ['BAIXA', 'NORMAL', 'ALTA', 'URGENTE'].index(p))
        linhas = [f'• {item.get_categoria_display()}: {item.resumo[:280]}' for item in itens[:8]]
        if len(itens) > 8:
            linhas.append(f'• … e mais {len(itens) - 8} evento(s).')
        chave = f'processo:{processo_id}:{hoje}'
        existente = criar_notificacao(
            user, 'SISTEMA', f'Atualização consolidada — {processo.numero or processo.titulo}',
            '\n'.join(linhas) + '\n\nConferência humana necessária; nenhum prazo foi criado automaticamente.',
            prioridade=prioridade, link=f'/processos/{processo_id}/',
            dados={'dedup_key': chave, 'processo_id': processo_id, 'triagens': [item.id for item in itens]},
        )
        criados += int(existente.criado_em.date() == timezone.localdate())
    return criados


def executar(user, dias=1, limite=50):
    """Triagem idempotente de eventos recentes e geração de alertas consolidados."""
    desde = timezone.now() - timedelta(days=max(1, dias))
    pendentes = [evento for evento in _eventos(user, desde) if not TriagemJuridica.objects.filter(
        user=user, fonte=evento['fonte'], identificador_origem=evento['identificador']).exists()]
    # O backlog pode conter e-mails genéricos; prioriza imediatamente tudo que
    # já está vinculado a processo cadastrado para a rotina jurídica diária.
    pendentes.sort(key=lambda evento: (evento['processo'] is None, evento['fonte'] != 'DJEN'))
    triagens = []
    for evento in pendentes[:max(1, limite)]:
        resultado = _aplicar_politica(_classificar_openai(evento))
        triagem = TriagemJuridica.objects.create(
            user=user, processo=evento['processo'], fonte=evento['fonte'], identificador_origem=evento['identificador'],
            titulo_origem=evento['titulo'][:500], categoria=resultado['categoria'], prioridade=resultado['prioridade'],
            resumo=resultado['resumo'], providencia_sugerida=resultado['providencia_sugerida'],
            confianca=resultado['confianca'], requer_conferencia=True,
            dados={'modelo': resultado.get('modelo'), 'erro_modelo': resultado.get('erro_modelo', ''),
                   'processo_numero': evento.get('processo_numero', '')},
        )
        triagens.append(triagem)
    alertas = _consolidar_alertas(user, triagens)
    return len(triagens), alertas, len(pendentes)
