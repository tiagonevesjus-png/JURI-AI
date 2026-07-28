"""Endpoints mínimos e autenticados usados pela ponte DJEN local."""

import json
import os
import secrets

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import SolicitacaoSincronizacaoDJEN
from .services.djen import DJENError, configuracao_oab, persistir_itens


def _autorizada(request):
    esperado = os.environ.get('DJEN_BRIDGE_TOKEN', '')
    recebido = request.headers.get('X-DJEN-Bridge-Token', '')
    return bool(esperado) and secrets.compare_digest(esperado, recebido)


def _nao_autorizada():
    return JsonResponse({'erro': 'Ponte DJEN não autorizada.'}, status=401)


def _usuario_padrao():
    username = os.environ.get('DJEN_IMPORT_USERNAME') or os.environ.get('ADMIN_USERNAME')
    if not username:
        return None
    return get_user_model().objects.filter(username=username, is_active=True).first()


@require_GET
def djen_bridge_pendente(request):
    if not _autorizada(request):
        return _nao_autorizada()
    try:
        numero, uf = configuracao_oab()
    except DJENError as exc:
        return JsonResponse({'erro': str(exc)}, status=503)
    pedido = SolicitacaoSincronizacaoDJEN.objects.filter(status='PENDENTE').first()
    dados = None
    if pedido:
        dados = {
            'id': pedido.id,
            'inicio': pedido.inicio.isoformat(),
            'fim': pedido.fim.isoformat(),
        }
    return JsonResponse({'solicitacao': dados, 'numero_oab': numero, 'uf_oab': uf})


@csrf_exempt
@require_POST
def djen_bridge_importar(request):
    if not _autorizada(request):
        return _nao_autorizada()
    if len(request.body) > 8 * 1024 * 1024:
        return JsonResponse({'erro': 'Carga DJEN excede 8 MB.'}, status=413)
    try:
        corpo = json.loads(request.body or b'{}')
    except (TypeError, ValueError):
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)
    itens = corpo.get('items')
    if not isinstance(itens, list) or len(itens) > 1000:
        return JsonResponse({'erro': 'items deve ser uma lista com até 1000 registros.'}, status=400)

    pedido = None
    pedido_id = corpo.get('solicitacao_id')
    if pedido_id:
        pedido = SolicitacaoSincronizacaoDJEN.objects.filter(id=pedido_id, status='PENDENTE').select_related('user').first()
        if pedido is None:
            return JsonResponse({'erro': 'Solicitação pendente não encontrada.'}, status=404)
        user = pedido.user
    else:
        user = _usuario_padrao()
        if user is None:
            return JsonResponse({'erro': 'Usuário de importação não configurado.'}, status=503)

    try:
        novas, total = persistir_itens(user, itens)
    except DJENError as exc:
        if pedido:
            pedido.status = 'FALHOU'
            pedido.mensagem = str(exc)[:2000]
            pedido.concluido_em = timezone.now()
            pedido.save(update_fields=['status', 'mensagem', 'concluido_em', 'atualizado_em'])
        return JsonResponse({'erro': str(exc)}, status=400)

    if pedido:
        pedido.status = 'CONCLUIDA'
        pedido.mensagem = f'{novas} nova(s) de {total} encontrada(s).'
        pedido.concluido_em = timezone.now()
        pedido.save(update_fields=['status', 'mensagem', 'concluido_em', 'atualizado_em'])
    return JsonResponse({'ok': True, 'novas': novas, 'total': total})
