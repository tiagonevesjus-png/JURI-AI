"""Views da camada de IA: assistente jurídico baseado em RAG sobre os
documentos do usuário."""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import services

logger = logging.getLogger(__name__)


@login_required
def assistente(request):
    """Assistente jurídico: responde perguntas com base nos documentos indexados."""
    contexto = {
        'ia_configurada': services.ia_configurada(),
        'pergunta': '',
        'resposta': None,
        'fontes': [],
        'erro': None,
    }

    if request.method == 'POST':
        pergunta = (request.POST.get('pergunta') or '').strip()
        contexto['pergunta'] = pergunta
        if not pergunta:
            contexto['erro'] = 'Digite uma pergunta.'
        elif not services.ia_configurada():
            contexto['erro'] = ('A IA não está totalmente configurada (defina ANTHROPIC_API_KEY '
                                'para as respostas e OPENAI_API_KEY para a busca nos documentos).')
        else:
            try:
                resultado = services.responder_pergunta(pergunta, user_id=request.user.id)
                contexto['resposta'] = resultado['resposta']
                contexto['fontes'] = resultado['fontes']
            except services.IAIndisponivel as exc:
                contexto['erro'] = str(exc)
            except Exception as exc:
                logger.exception('Erro no assistente de IA: %s', exc)
                contexto['erro'] = 'Ocorreu um erro ao consultar a IA. Tente novamente.'

    return render(request, 'ia/assistente.html', contexto)
