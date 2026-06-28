"""Tarefas assíncronas de IA (executadas via django-q).

São encadeadas pelo signal ``post_save`` de ``usuarios.Documentos``:
primeiro extrai o texto do arquivo (OCR -> Markdown), depois indexa o
conteúdo no índice vetorial para busca por RAG.
"""

import logging

from . import services

logger = logging.getLogger(__name__)


def ocr_and_markdown_file(instance_id):
    """Extrai o texto do documento e salva em ``Documentos.content`` (Markdown)."""
    from usuarios.models import Documentos

    try:
        doc = Documentos.objects.get(id=instance_id)
    except Documentos.DoesNotExist:
        logger.warning('Documento %s não encontrado para OCR.', instance_id)
        return instance_id

    try:
        markdown = services.extrair_markdown(doc.arquivo.path)
        if markdown:
            # Evita disparar novamente o signal de post_save em cascata.
            Documentos.objects.filter(id=doc.id).update(content=markdown)
            logger.info('OCR/Markdown gerado para o documento %s.', instance_id)
    except Exception as exc:
        logger.exception('Falha no OCR do documento %s: %s', instance_id, exc)

    return instance_id


def rag_documentos(instance_id):
    """Indexa o conteúdo do documento no índice vetorial (RAG)."""
    from usuarios.models import Documentos

    try:
        doc = Documentos.objects.select_related('cliente').get(id=instance_id)
    except Documentos.DoesNotExist:
        logger.warning('Documento %s não encontrado para indexação.', instance_id)
        return instance_id

    if not services.embeddings_configuradas():
        logger.info('Embeddings não configuradas; pulando indexação do documento %s.', instance_id)
        return instance_id

    try:
        chunks = services.dividir_em_chunks(doc.content or '')
        total = services.indexar_chunks(
            chunks,
            documento_id=doc.id,
            cliente_id=doc.cliente_id,
            user_id=doc.cliente.user_id,
            tipo=doc.get_tipo_display(),
        )
        logger.info('Documento %s indexado em %s trecho(s).', instance_id, total)
    except services.IAIndisponivel as exc:
        logger.info('Indexação indisponível para o documento %s: %s', instance_id, exc)
    except Exception as exc:
        logger.exception('Falha ao indexar documento %s: %s', instance_id, exc)

    return instance_id


def rag_dados_empresa(instance_id):
    """Reservado para indexar a base de conhecimento do escritório/empresa.

    Mantido como ponto de extensão: pode indexar modelos de petição, teses e
    documentos institucionais para uso pelo assistente. Hoje apenas registra
    a chamada para não quebrar a cadeia de tarefas.
    """
    logger.info('rag_dados_empresa chamado para %s (ponto de extensão).', instance_id)
    return instance_id
