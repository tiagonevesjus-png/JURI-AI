"""Integração local, com OAuth PKCE, para leitura de Gmail e Google Agenda."""

import base64
import os
import hashlib
import json
import secrets
import time
import webbrowser
from datetime import datetime, timedelta, timezone as datetime_timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode

import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from gestao.models import ItemGoogle
from gestao.services.notificacoes import criar as criar_notificacao


AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
GMAIL_URL = 'https://gmail.googleapis.com/gmail/v1/users/me'
CALENDAR_URL = 'https://www.googleapis.com/calendar/v3'
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
]


class GoogleWorkspaceError(Exception):
    """Falha de configuração, autorização ou comunicação com o Google."""


def _client_id():
    value = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '').strip()
    if not value:
        raise GoogleWorkspaceError('GOOGLE_OAUTH_CLIENT_ID não configurado.')
    return value


def _client_secret():
    """Segredo OAuth local; nunca é exibido, registrado ou versionado."""
    return os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '').strip()


def _token_path():
    return Path(os.environ.get('GOOGLE_OAUTH_TOKEN_FILE', '/app/data/google-oauth-token.json'))


def _pending_path():
    return Path(os.environ.get('GOOGLE_OAUTH_PENDING_FILE', '/app/data/google-oauth-pending.json'))


def autorizado():
    return _token_path().is_file()


def _carregar_token():
    try:
        return json.loads(_token_path().read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise GoogleWorkspaceError('A conta Google ainda não foi autorizada localmente.') from exc
    except json.JSONDecodeError as exc:
        raise GoogleWorkspaceError('O arquivo local do token Google está inválido.') from exc


def _salvar_token(token):
    destino = _token_path()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix('.tmp')
    temporario.write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding='utf-8')
    temporario.replace(destino)


def _salvar_pendente(pendente):
    destino = _pending_path()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix('.tmp')
    temporario.write_text(json.dumps(pendente, ensure_ascii=False, indent=2), encoding='utf-8')
    temporario.replace(destino)


def _carregar_pendente():
    try:
        return json.loads(_pending_path().read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise GoogleWorkspaceError('Não há uma autorização Google pendente. Inicie uma nova autorização.') from exc


def _limpar_pendente():
    _pending_path().unlink(missing_ok=True)


def _pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b'=').decode('ascii')
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return verifier, challenge


def url_autorizacao(redirect_uri, state, verifier):
    _, challenge = _pkce_from_verifier(verifier)
    return AUTHORIZATION_URL + '?' + urlencode({
        'client_id': _client_id(),
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })


def _pkce_from_verifier(verifier):
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return verifier, challenge


def iniciar_autorizacao(port=8765, abrir_navegador=True, timeout=None):
    """Cria uma autorização PKCE persistente, tratada pelo endpoint Django local."""
    _client_id()
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    redirect_uri = f'http://127.0.0.1:{port}/google/oauth/callback'
    authorization_url = AUTHORIZATION_URL + '?' + urlencode({
        'client_id': _client_id(),
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })
    arquivo_url = os.environ.get('GOOGLE_OAUTH_AUTHORIZATION_URL_FILE', '').strip()
    if arquivo_url:
        Path(arquivo_url).parent.mkdir(parents=True, exist_ok=True)
        Path(arquivo_url).write_text(authorization_url, encoding='utf-8')
    _salvar_pendente({
        'state': state,
        'verifier': verifier,
        'redirect_uri': redirect_uri,
        'created_at': int(time.time()),
    })
    print(f'Abra a autorização Google neste endereço: {authorization_url}', flush=True)
    if abrir_navegador:
        webbrowser.open(authorization_url)
    return authorization_url


def concluir_autorizacao(state, code='', error=''):
    """Valida o retorno OAuth persistido e salva o token somente no volume local."""
    pendente = _carregar_pendente()
    if not secrets.compare_digest(state or '', pendente.get('state', '')):
        raise GoogleWorkspaceError('Retorno OAuth inválido: o estado não corresponde à solicitação local.')
    if error or not code:
        _limpar_pendente()
        raise GoogleWorkspaceError(f'Autorização Google recusada: {error or "sem código"}.')
    dados_token = {
        'client_id': _client_id(),
        'code': code,
        'code_verifier': pendente['verifier'],
        'grant_type': 'authorization_code',
        'redirect_uri': pendente['redirect_uri'],
    }
    if _client_secret():
        dados_token['client_secret'] = _client_secret()
    resposta = requests.post(TOKEN_URL, data=dados_token, timeout=(5, 20))
    if not resposta.ok:
        try:
            detalhe = resposta.json()
        except ValueError:
            detalhe = {}
        codigo = detalhe.get('error', 'erro_desconhecido')
        descricao = detalhe.get('error_description', '').strip()
        sufixo = f' ({codigo}: {descricao})' if descricao else f' ({codigo})'
        raise GoogleWorkspaceError(f'Falha ao obter token Google: HTTP {resposta.status_code}{sufixo}.')
    token = resposta.json()
    token['expires_at'] = int(time.time()) + int(token.get('expires_in', 3600))
    _salvar_token(token)
    _limpar_pendente()


def _access_token():
    token = _carregar_token()
    if token.get('access_token') and int(token.get('expires_at', 0)) > int(time.time()) + 60:
        return token['access_token']
    refresh = token.get('refresh_token')
    if not refresh:
        raise GoogleWorkspaceError('O token Google não possui refresh_token; autorize novamente.')
    dados_refresh = {
        'client_id': _client_id(),
        'grant_type': 'refresh_token',
        'refresh_token': refresh,
    }
    if _client_secret():
        dados_refresh['client_secret'] = _client_secret()
    resposta = requests.post(TOKEN_URL, data=dados_refresh, timeout=(5, 20))
    if not resposta.ok:
        raise GoogleWorkspaceError('Não foi possível renovar o acesso Google; autorize novamente.')
    atualizado = resposta.json()
    token.update(atualizado)
    token['expires_at'] = int(time.time()) + int(atualizado.get('expires_in', 3600))
    _salvar_token(token)
    return token['access_token']


def _get(url, params=None):
    resposta = requests.get(url, params=params, headers={'Authorization': f'Bearer {_access_token()}'}, timeout=(5, 25))
    if resposta.status_code == 401:
        token = _carregar_token()
        token['expires_at'] = 0
        _salvar_token(token)
        resposta = requests.get(url, params=params, headers={'Authorization': f'Bearer {_access_token()}'}, timeout=(5, 25))
    if not resposta.ok:
        raise GoogleWorkspaceError(f'Consulta Google falhou: HTTP {resposta.status_code}.')
    return resposta.json()


def _data_gmail(headers):
    valor = next((h.get('value', '') for h in headers if h.get('name', '').lower() == 'date'), '')
    try:
        data = parsedate_to_datetime(valor)
        if data.tzinfo is None:
            data = data.replace(tzinfo=datetime_timezone.utc)
        return data
    except (TypeError, ValueError, IndexError):
        return None


def _salvar_item(user, fonte, identificador, titulo, ocorrido_em=None, link='', resumo='', dados=None):
    _, criado = ItemGoogle.objects.update_or_create(
        user=user,
        fonte=fonte,
        identificador_externo=identificador,
        defaults={
            'titulo': (titulo or '(sem título)')[:500],
            'ocorrido_em': ocorrido_em,
            'link': link,
            'resumo': resumo or '',
            'dados': dados or {},
        },
    )
    return criado


def sincronizar(user):
    """Lê e armazena apenas metadados úteis, sem anexos ou corpo integral de e-mails."""
    if os.environ.get('GOOGLE_SYNC_ENABLED', 'false').lower() != 'true':
        raise GoogleWorkspaceError('GOOGLE_SYNC_ENABLED está desativado.')
    query = os.environ.get('GOOGLE_GMAIL_QUERY', 'label:inbox newer_than:2d -category:promotions -category:social')
    dias_agenda = max(1, min(90, int(os.environ.get('GOOGLE_CALENDAR_DAYS_AHEAD', '14'))))
    novas_gmail = novas_agenda = 0

    mensagens = _get(f'{GMAIL_URL}/messages', {'q': query, 'maxResults': 50}).get('messages', [])
    for item in mensagens:
        mensagem = _get(f'{GMAIL_URL}/messages/{item["id"]}', {'format': 'metadata', 'metadataHeaders': ['From', 'Subject', 'Date']})
        headers = mensagem.get('payload', {}).get('headers', [])
        subject = next((h.get('value', '') for h in headers if h.get('name', '').lower() == 'subject'), '')
        remetente = next((h.get('value', '') for h in headers if h.get('name', '').lower() == 'from'), '')
        if _salvar_item(user, 'GMAIL', mensagem['id'], subject, _data_gmail(headers),
                         f'https://mail.google.com/mail/u/0/#all/{mensagem["id"]}',
                         mensagem.get('snippet', ''), {'remetente': remetente, 'thread_id': mensagem.get('threadId', '')}):
            novas_gmail += 1
            criar_notificacao(user, 'GMAIL', f'Novo e-mail: {subject or "sem assunto"}',
                              f'Remetente: {remetente}', link=f'https://mail.google.com/mail/u/0/#all/{mensagem["id"]}',
                              dados={'id': mensagem['id']})

    inicio = timezone.now()
    fim = inicio + timedelta(days=dias_agenda)
    eventos = _get(f'{CALENDAR_URL}/calendars/primary/events', {
        'timeMin': inicio.isoformat(), 'timeMax': fim.isoformat(), 'singleEvents': 'true',
        'orderBy': 'startTime', 'maxResults': 100,
    }).get('items', [])
    for evento in eventos:
        inicio_evento = evento.get('start', {})
        valor_data = inicio_evento.get('dateTime')
        data_evento = parse_datetime(valor_data) if valor_data else None
        if data_evento is None and inicio_evento.get('date'):
            data_evento = timezone.make_aware(datetime.fromisoformat(inicio_evento['date']))
        if _salvar_item(user, 'AGENDA', evento['id'], evento.get('summary', ''), data_evento,
                         evento.get('htmlLink', ''), evento.get('location', ''),
                         {'status': evento.get('status', ''), 'fim': evento.get('end', {})}):
            novas_agenda += 1
            criar_notificacao(user, 'AGENDA', f'Novo evento: {evento.get("summary") or "sem título"}',
                              evento.get('location', ''), link=evento.get('htmlLink', ''), dados={'id': evento['id']})
    return novas_gmail, novas_agenda, len(mensagens), len(eventos)
