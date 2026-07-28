"""Validação de assinaturas CMS/PKCS#7 produzidas pelo PJeOffice.

O PJeOffice/desktopID continua sendo o responsável pela operação
criptográfica. Esta camada apenas confere o arquivo P7S retornado e preserva
uma trilha de auditoria local.
"""

import hashlib
import subprocess
import tempfile
from pathlib import Path


class AssinaturaError(Exception):
    pass


def sha256_arquivo(arquivo):
    digest = hashlib.sha256()
    for bloco in arquivo.chunks():
        digest.update(bloco)
    return digest.hexdigest()


def _executar(comando):
    try:
        return subprocess.run(comando, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssinaturaError('Não foi possível executar o validador criptográfico.') from exc


def validar_p7s(arquivo_original, arquivo_p7s):
    """Confere uma assinatura CMS anexa ou destacada e lê o certificado público."""
    with tempfile.TemporaryDirectory(prefix='juriai-assinatura-') as diretorio:
        original = Path(diretorio) / 'original.pdf'
        p7s = Path(diretorio) / 'assinatura.p7s'
        certs = Path(diretorio) / 'certificados.txt'
        with open(original, 'wb') as destino:
            for bloco in arquivo_original.chunks():
                destino.write(bloco)
        with open(p7s, 'wb') as destino:
            for bloco in arquivo_p7s.chunks():
                destino.write(bloco)

        # PJeOffice pode produzir CMS anexo ou destacado. Tentamos ambos.
        comando = ['openssl', 'cms', '-verify', '-inform', 'DER', '-in', str(p7s), '-noverify', '-out', '/dev/null']
        resultado = _executar(comando)
        modo = 'anexa'
        if resultado.returncode != 0:
            comando = ['openssl', 'cms', '-verify', '-inform', 'DER', '-in', str(p7s), '-content', str(original), '-noverify', '-out', '/dev/null']
            resultado = _executar(comando)
            modo = 'destacada'
        if resultado.returncode != 0:
            detalhe = (resultado.stderr or resultado.stdout or 'assinatura inválida').strip()[:500]
            raise AssinaturaError(f'Assinatura P7S não validada: {detalhe}')

        certificados = _executar(['openssl', 'pkcs7', '-inform', 'DER', '-in', str(p7s), '-print_certs', '-noout'])
        if certificados.returncode != 0:
            raise AssinaturaError('A assinatura foi verificada, mas o certificado público não pôde ser lido.')
        linhas = certificados.stdout.splitlines()
        subject = next((linha.removeprefix('subject=').strip() for linha in linhas if linha.startswith('subject=')), '')
        issuer = next((linha.removeprefix('issuer=').strip() for linha in linhas if linha.startswith('issuer=')), '')
        return {
            'valida': True,
            'modo': modo,
            'subject': subject,
            'issuer': issuer,
            'mensagem': 'CMS Verification successful',
        }
