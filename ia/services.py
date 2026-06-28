"""Serviços de IA do Juri-AI: extração de texto (OCR/Markdown) e RAG.

Todas as dependências pesadas (docling, openai, lancedb) são importadas de
forma tardia (lazy) dentro das funções. Assim o projeto continua iniciando e
rodando mesmo que a infraestrutura de IA não esteja instalada/configurada —
os recursos de IA apenas ficam indisponíveis, sem quebrar o restante do app.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)


class IAIndisponivel(RuntimeError):
    """Levantada quando uma dependência ou configuração de IA está ausente."""


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
def _conf(nome, padrao=''):
    return getattr(settings, nome, os.environ.get(nome, padrao))


def embeddings_configuradas():
    """RAG usa embeddings da OpenAI (a Anthropic não oferece endpoint de embeddings)."""
    return bool(_conf('OPENAI_API_KEY'))


def geracao_configurada():
    """A geração das respostas usa o Claude (Anthropic)."""
    return bool(_conf('ANTHROPIC_API_KEY'))


def ia_configurada():
    """Pipeline completo do assistente: indexação (embeddings) + resposta (Claude)."""
    return embeddings_configuradas() and geracao_configurada()


# ---------------------------------------------------------------------------
# Extração de texto / OCR -> Markdown
# ---------------------------------------------------------------------------
def extrair_markdown(caminho_arquivo: str) -> str:
    """Converte um documento (PDF, DOCX, imagem...) em Markdown.

    Usa o ``docling`` quando disponível (faz OCR de PDFs/imagens). Se o docling
    não estiver instalado, faz um fallback de leitura de texto simples.
    """
    try:
        from docling.document_converter import DocumentConverter
    except Exception:  # docling ausente
        logger.warning('docling indisponível; usando leitura de texto simples.')
        return _ler_texto_simples(caminho_arquivo)

    try:
        converter = DocumentConverter()
        resultado = converter.convert(caminho_arquivo)
        return resultado.document.export_to_markdown()
    except Exception as exc:  # falha na conversão -> fallback
        logger.exception('Falha ao converter documento com docling: %s', exc)
        return _ler_texto_simples(caminho_arquivo)


def _ler_texto_simples(caminho_arquivo: str) -> str:
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as fp:
            return fp.read()
    except Exception:
        return ''


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def dividir_em_chunks(texto: str, tamanho: int = 1000, sobreposicao: int = 150):
    """Divide o texto em pedaços com sobreposição, respeitando parágrafos."""
    texto = (texto or '').strip()
    if not texto:
        return []

    paragrafos = [p.strip() for p in texto.split('\n\n') if p.strip()]
    chunks, atual = [], ''
    for par in paragrafos:
        if len(atual) + len(par) + 2 <= tamanho:
            atual = f'{atual}\n\n{par}' if atual else par
        else:
            if atual:
                chunks.append(atual)
            # Parágrafo maior que o limite: fatia em janelas.
            if len(par) > tamanho:
                inicio = 0
                while inicio < len(par):
                    chunks.append(par[inicio:inicio + tamanho])
                    inicio += tamanho - sobreposicao
                atual = ''
            else:
                atual = par
    if atual:
        chunks.append(atual)
    return chunks


# ---------------------------------------------------------------------------
# Embeddings (OpenAI)
#
# A Anthropic/Claude não oferece endpoint de embeddings, então a parte de
# vetorização do RAG usa a OpenAI. A geração das respostas usa o Claude
# (ver `responder_pergunta`). Para trocar o provedor de embeddings, basta
# reescrever `gerar_embeddings`.
# ---------------------------------------------------------------------------
def _cliente_openai():
    chave = _conf('OPENAI_API_KEY')
    if not chave:
        raise IAIndisponivel('OPENAI_API_KEY não configurada (necessária para indexar/buscar documentos).')
    try:
        from openai import OpenAI
    except Exception as exc:
        raise IAIndisponivel('Pacote openai não instalado.') from exc
    return OpenAI(api_key=chave)


def gerar_embeddings(textos: list[str]) -> list[list[float]]:
    if not textos:
        return []
    cliente = _cliente_openai()
    modelo = _conf('IA_EMBEDDING_MODEL', 'text-embedding-3-small')
    resposta = cliente.embeddings.create(model=modelo, input=textos)
    return [item.embedding for item in resposta.data]


# ---------------------------------------------------------------------------
# Vetor / LanceDB
# ---------------------------------------------------------------------------
def _abrir_tabela(criar_com=None):
    try:
        import lancedb
    except Exception as exc:
        raise IAIndisponivel('Pacote lancedb não instalado.') from exc

    caminho = _conf('LANCEDB_PATH') or os.path.join(settings.BASE_DIR, 'lancedb')
    db = lancedb.connect(caminho)
    nome = 'documentos'
    if nome in db.table_names():
        tabela = db.open_table(nome)
        if criar_com:
            tabela.add(criar_com)
        return tabela
    if criar_com:
        return db.create_table(nome, data=criar_com)
    raise IAIndisponivel('Nenhum documento indexado ainda.')


def indexar_chunks(chunks: list[str], *, documento_id, cliente_id, user_id, tipo=''):
    """Gera embeddings dos chunks e os grava no índice vetorial."""
    if not chunks:
        return 0
    vetores = gerar_embeddings(chunks)
    linhas = [
        {
            'vector': vetores[i],
            'texto': chunk,
            'documento_id': int(documento_id),
            'cliente_id': int(cliente_id),
            'user_id': int(user_id),
            'tipo': tipo or '',
        }
        for i, chunk in enumerate(chunks)
    ]
    _abrir_tabela(criar_com=linhas)
    return len(linhas)


def buscar_trechos(pergunta: str, *, user_id, limite: int = 5):
    """Busca os trechos mais relevantes para a pergunta, do usuário informado."""
    vetor = gerar_embeddings([pergunta])[0]
    tabela = _abrir_tabela()
    resultados = (
        tabela.search(vetor)
        .where(f'user_id = {int(user_id)}')
        .limit(limite)
        .to_list()
    )
    return [
        {'texto': r.get('texto', ''), 'documento_id': r.get('documento_id'),
         'cliente_id': r.get('cliente_id'), 'tipo': r.get('tipo', '')}
        for r in resultados
    ]


# ---------------------------------------------------------------------------
# Geração da resposta com o Claude (Anthropic)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    'Você é um assistente jurídico do escritório. Responda à pergunta do '
    'advogado usando APENAS o contexto extraído dos documentos fornecidos. '
    'Cite trechos quando útil. Se a resposta não estiver no contexto, diga '
    'claramente que não encontrou a informação nos documentos. Nunca invente '
    'fatos. Esta resposta é um apoio e não substitui a análise do advogado.'
)


def _cliente_anthropic():
    chave = _conf('ANTHROPIC_API_KEY')
    if not chave:
        raise IAIndisponivel('ANTHROPIC_API_KEY não configurada (necessária para gerar respostas).')
    try:
        import anthropic
    except Exception as exc:
        raise IAIndisponivel('Pacote anthropic não instalado.') from exc
    return anthropic.Anthropic(api_key=chave)


def responder_pergunta(pergunta: str, *, user_id, limite: int = 5) -> dict:
    """Pipeline RAG: recupera trechos relevantes (embeddings) e gera a resposta com o Claude."""
    trechos = buscar_trechos(pergunta, user_id=user_id, limite=limite)
    if not trechos:
        return {'resposta': 'Não há documentos indexados para responder.', 'fontes': []}

    contexto = '\n\n---\n\n'.join(t['texto'] for t in trechos)
    cliente = _cliente_anthropic()
    modelo = _conf('IA_CLAUDE_MODEL', 'claude-opus-4-8')
    resposta = cliente.messages.create(
        model=modelo,
        max_tokens=4096,
        thinking={'type': 'adaptive'},  # raciocínio adaptativo para análise jurídica
        system=SYSTEM_PROMPT,
        messages=[
            {
                'role': 'user',
                'content': f'Contexto dos documentos:\n{contexto}\n\nPergunta: {pergunta}',
            }
        ],
    )
    texto = next((bloco.text for bloco in resposta.content if bloco.type == 'text'), '')
    return {'resposta': texto, 'fontes': trechos}
