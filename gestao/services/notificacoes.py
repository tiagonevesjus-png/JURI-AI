"""Central de alertas: registra sempre no Juri-AI e envia externamente só quando habilitado."""

import os

import requests
from django.conf import settings
from django.core.mail import send_mail

from gestao.models import Notificacao


def _ativo(nome):
    return os.environ.get(nome, 'false').lower() in ('1', 'true', 'yes', 'on')


def criar(user, tipo, titulo, mensagem='', prioridade='NORMAL', link='', dados=None):
    notificacao = Notificacao.objects.create(
        user=user, tipo=tipo, titulo=titulo[:255], mensagem=mensagem, prioridade=prioridade,
        link=link, dados=dados or {},
    )
    if _ativo('NOTIFICATIONS_DELIVERY_ENABLED'):
        notificacao.entregas = enviar(notificacao)
        notificacao.save(update_fields=['entregas'])
    return notificacao


def _texto(notificacao):
    base = f'[{notificacao.get_prioridade_display()}] {notificacao.titulo}\n{notificacao.mensagem}'
    return f'{base}\n{notificacao.link}' if notificacao.link else base


def _payload_whatsapp(notificacao, texto):
    """Usa template aprovado para conversas iniciadas pelo sistema.

    O template ``juri_ai_alerta`` deve ter trÃªs variÃ¡veis no corpo: tÃ­tulo,
    mensagem e link. Sem template configurado, texto livre sÃ³ Ã© adequado
    dentro da janela de conversa aberta pelo destinatÃ¡rio.
    """
    template = os.environ.get('WHATSAPP_TEMPLATE_NAME', '').strip()
    if not template:
        return {
            'messaging_product': 'whatsapp', 'to': os.environ['WHATSAPP_TO'],
            'type': 'text', 'text': {'body': texto[:4096]},
        }, 'texto_livre'
    linguagem = os.environ.get('WHATSAPP_TEMPLATE_LANGUAGE', 'pt_BR').strip() or 'pt_BR'
    parametros = [notificacao.titulo, notificacao.mensagem or '-', notificacao.link or 'Acesse o JURI-AI.']
    return {
        'messaging_product': 'whatsapp', 'to': os.environ['WHATSAPP_TO'],
        'type': 'template',
        'template': {
            'name': template, 'language': {'code': linguagem},
            'components': [{'type': 'body', 'parameters': [
                {'type': 'text', 'text': valor[:1024]} for valor in parametros
            ]}],
        },
    }, f'template:{template}'


def enviar(notificacao):
    """Tenta canais independentes; erros ficam no registro, sem interromper monitores."""
    resultado = {}
    texto = _texto(notificacao)
    destino = os.environ.get('ALERT_EMAIL_TO', '').strip() or notificacao.user.email
    if _ativo('NOTIFICATIONS_EMAIL_ENABLED') and destino:
        try:
            if os.environ.get('NOTIFICATIONS_EMAIL_MODE', 'smtp').strip().lower() == 'google_oauth':
                from gestao.services.google_workspace import enviar_email
                enviar_email(destino, notificacao.titulo, texto)
            else:
                send_mail(notificacao.titulo, texto, settings.DEFAULT_FROM_EMAIL, [destino], fail_silently=False)
            resultado['email'] = 'enviado'
        except Exception as exc:  # transportes externos não podem derrubar a sincronização
            resultado['email'] = f'falhou: {type(exc).__name__}'
    token, chat = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip(), os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if _ativo('NOTIFICATIONS_TELEGRAM_ENABLED') and token and chat:
        try:
            r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat, 'text': texto[:4000]}, timeout=(5, 15))
            resultado['telegram'] = 'enviado' if r.ok else f'falhou: HTTP {r.status_code}'
        except requests.RequestException as exc:
            resultado['telegram'] = f'falhou: {type(exc).__name__}'
    meta_token, phone_id, para = (os.environ.get('WHATSAPP_ACCESS_TOKEN', '').strip(), os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '').strip(), os.environ.get('WHATSAPP_TO', '').strip())
    if _ativo('NOTIFICATIONS_WHATSAPP_ENABLED') and meta_token and phone_id and para:
        try:
            payload, modo = _payload_whatsapp(notificacao, texto)
            r = requests.post(f'https://graph.facebook.com/v21.0/{phone_id}/messages', headers={'Authorization': f'Bearer {meta_token}'}, json=payload, timeout=(5, 15))
            if r.ok:
                resposta = r.json()
                mensagem_id = (resposta.get('messages') or [{}])[0].get('id')
                resultado['whatsapp'] = {
                    'status': 'aceito_pela_meta',
                    'mensagem_id': mensagem_id,
                    'destinatario': para,
                    'modo': modo,
                }
            else:
                erro = r.json().get('error', {}) if r.headers.get('content-type', '').startswith('application/json') else {}
                resultado['whatsapp'] = {
                    'status': 'falhou',
                    'http_status': r.status_code,
                    'codigo': erro.get('code'),
                    'subcodigo': erro.get('error_subcode'),
                    'mensagem': erro.get('message', f'HTTP {r.status_code}')[:300],
                }
        except requests.RequestException as exc:
            resultado['whatsapp'] = f'falhou: {type(exc).__name__}'
    # Push real (navegador fechado) exige VAPID + inscrição do dispositivo; o painel usa polling quando aberto.
    resultado['push'] = _enviar_push(notificacao) if _ativo('NOTIFICATIONS_PUSH_ENABLED') else 'desativado'
    return resultado


def _enviar_push(notificacao):
    """Entrega Web Push a todos os navegadores autorizados do usuario."""
    if not settings.WEBPUSH_VAPID_PUBLIC_KEY or not settings.WEBPUSH_VAPID_PRIVATE_KEY:
        return {'status': 'nao_configurado'}
    from pywebpush import WebPushException, webpush
    from gestao.models import PushSubscription
    payload = {
        'title': notificacao.titulo,
        'body': notificacao.mensagem or notificacao.get_prioridade_display(),
        'url': notificacao.link or '/notificacoes/',
    }
    entregues, removidas, falhas = 0, 0, 0
    for inscricao in PushSubscription.objects.filter(user=notificacao.user):
        try:
            webpush(
                subscription_info={
                    'endpoint': inscricao.endpoint,
                    'keys': {'p256dh': inscricao.p256dh, 'auth': inscricao.auth},
                },
                data=__import__('json').dumps(payload),
                vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims=settings.WEBPUSH_VAPID_CLAIMS,
                ttl=86400,
            )
            entregues += 1
        except WebPushException as exc:
            if getattr(exc.response, 'status_code', None) in (404, 410):
                inscricao.delete()
                removidas += 1
            else:
                falhas += 1
    return {'status': 'enviado', 'entregues': entregues, 'removidas': removidas, 'falhas': falhas}
