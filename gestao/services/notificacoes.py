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


def enviar(notificacao):
    """Tenta canais independentes; erros ficam no registro, sem interromper monitores."""
    resultado = {}
    texto = _texto(notificacao)
    destino = os.environ.get('ALERT_EMAIL_TO', '').strip() or notificacao.user.email
    if _ativo('NOTIFICATIONS_EMAIL_ENABLED') and destino:
        try:
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
            r = requests.post(f'https://graph.facebook.com/v21.0/{phone_id}/messages', headers={'Authorization': f'Bearer {meta_token}'}, json={'messaging_product': 'whatsapp', 'to': para, 'type': 'text', 'text': {'body': texto[:4096]}}, timeout=(5, 15))
            resultado['whatsapp'] = 'enviado' if r.ok else f'falhou: HTTP {r.status_code}'
        except requests.RequestException as exc:
            resultado['whatsapp'] = f'falhou: {type(exc).__name__}'
    # Push real (navegador fechado) exige VAPID + inscrição do dispositivo; o painel usa polling quando aberto.
    resultado['push'] = 'painel' if _ativo('NOTIFICATIONS_PUSH_ENABLED') else 'desativado'
    return resultado
