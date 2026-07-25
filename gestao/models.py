"""Modelos do núcleo de gestão jurídica do Juri-AI.

Reaproveita os modelos ``Cliente`` e ``Documentos`` do app ``usuarios`` e
adiciona as entidades de um escritório de advocacia: processos, audiências,
prazos, tarefas, agenda, financeiro e controle de acesso (perfis).
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from usuarios.models import Cliente


# ---------------------------------------------------------------------------
# Controle de acessos / Perfil do usuário
# ---------------------------------------------------------------------------
class Perfil(models.Model):
    """Estende o ``User`` do Django com cargo e dados profissionais."""

    CARGO_CHOICES = [
        ('ADMIN', 'Administrador'),
        ('ADVOGADO', 'Advogado(a)'),
        ('ESTAGIARIO', 'Estagiário(a)'),
        ('SECRETARIA', 'Secretária(o)'),
        ('FINANCEIRO', 'Financeiro'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    nome_completo = models.CharField('Nome completo', max_length=255, blank=True)
    cargo = models.CharField(max_length=20, choices=CARGO_CHOICES, default='ADVOGADO')
    oab = models.CharField('OAB', max_length=30, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    ativo = models.BooleanField('Acesso ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis / Acessos'

    def __str__(self):
        return f'{self.nome_completo or self.user.username} ({self.get_cargo_display()})'

    @property
    def is_admin(self):
        return self.cargo == 'ADMIN' or self.user.is_superuser


# ---------------------------------------------------------------------------
# Processos judiciais
# ---------------------------------------------------------------------------
class Processo(models.Model):
    AREA_CHOICES = [
        ('CIVEL', 'Cível'),
        ('TRABALHISTA', 'Trabalhista'),
        ('CRIMINAL', 'Criminal'),
        ('TRIBUTARIO', 'Tributário'),
        ('FAMILIA', 'Família e Sucessões'),
        ('PREVIDENCIARIO', 'Previdenciário'),
        ('CONSUMIDOR', 'Consumidor'),
        ('EMPRESARIAL', 'Empresarial'),
        ('OUTRO', 'Outro'),
    ]
    STATUS_CHOICES = [
        ('ANDAMENTO', 'Em andamento'),
        ('SUSPENSO', 'Suspenso'),
        ('ARQUIVADO', 'Arquivado'),
        ('ENCERRADO', 'Encerrado'),
    ]
    INSTANCIA_CHOICES = [
        ('1', '1ª Instância'),
        ('2', '2ª Instância'),
        ('SUP', 'Tribunais Superiores'),
    ]

    numero = models.CharField('Número do processo (CNJ)', max_length=30, blank=True)
    titulo = models.CharField('Título / Identificação', max_length=255)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='processos')
    area = models.CharField(max_length=20, choices=AREA_CHOICES, default='CIVEL')
    tipo_acao = models.CharField('Tipo de ação', max_length=255, blank=True)
    parte_contraria = models.CharField(max_length=255, blank=True)
    vara = models.CharField('Vara / Órgão', max_length=255, blank=True)
    comarca = models.CharField('Comarca / Foro', max_length=255, blank=True)
    tribunal = models.CharField(max_length=255, blank=True)
    datajud_alias = models.CharField(max_length=80, blank=True)
    ultima_sincronizacao_datajud = models.DateTimeField(null=True, blank=True)
    instancia = models.CharField(max_length=3, choices=INSTANCIA_CHOICES, default='1')
    valor_causa = models.DecimalField('Valor da causa', max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ANDAMENTO')
    data_distribuicao = models.DateField('Data de distribuição', null=True, blank=True)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='processos_responsavel')
    observacoes = models.TextField('Observações', blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='processos')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Processo'
        verbose_name_plural = 'Processos'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.titulo} ({self.numero or "sem número"})'

    @property
    def ativo(self):
        return self.status == 'ANDAMENTO'


class MovimentacaoProcesso(models.Model):
    """Andamentos / movimentações registradas em um processo."""

    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='movimentacoes')
    data = models.DateField(default=timezone.now)
    data_hora = models.DateTimeField(null=True, blank=True)
    fonte = models.CharField(max_length=20, default='MANUAL')
    codigo_tpu = models.CharField(max_length=40, blank=True)
    referencia_externa = models.CharField(max_length=64, blank=True, null=True)
    descricao = models.TextField('Descrição')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação'
        verbose_name_plural = 'Movimentações'
        ordering = ['-data', '-criado_em']

    def __str__(self):
        return f'{self.processo} - {self.data}'


class PublicacaoDJEN(models.Model):
    """Comunicação pública obtida pelo endpoint de leitura do DJEN."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='publicacoes_djen')
    processo = models.ForeignKey(Processo, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='publicacoes_djen')
    identificador_externo = models.CharField(max_length=100)
    numero_processo = models.CharField(max_length=30, blank=True)
    data_disponibilizacao = models.DateField(null=True, blank=True)
    tribunal = models.CharField(max_length=30, blank=True)
    tipo_comunicacao = models.CharField(max_length=100, blank=True)
    orgao = models.CharField(max_length=255, blank=True)
    texto = models.TextField(blank=True)
    link = models.URLField(blank=True)
    dados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Publicação DJEN'
        verbose_name_plural = 'Publicações DJEN'
        ordering = ['-data_disponibilizacao', '-criado_em']
        constraints = [
            models.UniqueConstraint(fields=['user', 'identificador_externo'],
                                    name='publicacao_djen_usuario_identificador_unico'),
        ]

    def __str__(self):
        return f'{self.tribunal or "DJEN"} - {self.numero_processo or self.identificador_externo}'


class ItemGoogle(models.Model):
    """Registro local e minimizado de itens lidos do Gmail e da Agenda."""

    FONTE_CHOICES = [
        ('GMAIL', 'Gmail'),
        ('AGENDA', 'Google Agenda'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='itens_google')
    fonte = models.CharField(max_length=10, choices=FONTE_CHOICES)
    identificador_externo = models.CharField(max_length=255)
    titulo = models.CharField(max_length=500)
    ocorrido_em = models.DateTimeField(null=True, blank=True)
    link = models.URLField(blank=True)
    resumo = models.TextField(blank=True)
    dados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Item Google'
        verbose_name_plural = 'Itens Google'
        ordering = ['-ocorrido_em', '-atualizado_em']
        constraints = [
            models.UniqueConstraint(fields=['user', 'fonte', 'identificador_externo'],
                                    name='item_google_usuario_fonte_identificador_unico'),
        ]

    def __str__(self):
        return f'{self.get_fonte_display()}: {self.titulo}'


class ArquivoGoogleDrive(models.Model):
    """Catálogo local, somente de metadados, da pasta Clientes do Google Drive."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='arquivos_google_drive')
    identificador_externo = models.CharField(max_length=255)
    nome = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=255, blank=True)
    caminho = models.CharField(max_length=2000, blank=True)
    link = models.URLField(blank=True)
    tamanho_bytes = models.BigIntegerField(null=True, blank=True)
    checksum_md5 = models.CharField(max_length=32, blank=True)
    modificado_em = models.DateTimeField(null=True, blank=True)
    dados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Arquivo Google Drive'
        verbose_name_plural = 'Arquivos Google Drive'
        ordering = ['caminho', 'nome']
        constraints = [
            models.UniqueConstraint(fields=['user', 'identificador_externo'],
                                    name='arquivo_drive_usuario_identificador_unico'),
        ]

    def __str__(self):
        return self.caminho or self.nome


class Notificacao(models.Model):
    """Alerta interno com rastreio dos canais externos de entrega."""

    TIPO_CHOICES = [
        ('DJEN', 'Publicação DJEN'), ('GMAIL', 'Gmail'), ('AGENDA', 'Google Agenda'), ('DRIVE', 'Google Drive'),
        ('PRAZO', 'Prazo'), ('AUDIENCIA', 'Audiência'), ('SISTEMA', 'Sistema'),
    ]
    PRIORIDADE_CHOICES = [('BAIXA', 'Baixa'), ('NORMAL', 'Normal'), ('ALTA', 'Alta'), ('URGENTE', 'Urgente')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificacoes')
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES, default='SISTEMA')
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='NORMAL')
    titulo = models.CharField(max_length=255)
    mensagem = models.TextField(blank=True)
    link = models.URLField(blank=True)
    dados = models.JSONField(default=dict, blank=True)
    lida_em = models.DateTimeField(null=True, blank=True)
    entregas = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        indexes = [models.Index(fields=['user', 'lida_em', '-criado_em'])]

    @property
    def lida(self):
        return self.lida_em is not None


# ---------------------------------------------------------------------------
# Audiências
# ---------------------------------------------------------------------------
class PushSubscription(models.Model):
    """Inscricao Web Push vinculada a um navegador autorizado."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='push_subscriptions')
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Inscricao push'
        verbose_name_plural = 'Inscricoes push'

    def __str__(self):
        return f'Push de {self.user.username}'


class SolicitacaoAssinatura(models.Model):
    """Documento preparado no JURI-AI e assinado externamente pelo titular.

    O sistema guarda apenas arquivos, hashes e metadados públicos do
    certificado. PIN, e-Token e chave privada permanecem fora da aplicação.
    """

    STATUS_CHOICES = [
        ('PENDENTE', 'Aguardando assinatura'),
        ('EM_ASSINATURA', 'Em assinatura'),
        ('ASSINADO', 'Assinado e validado'),
        ('FALHOU', 'Validação falhou'),
        ('CANCELADO', 'Cancelado'),
    ]

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='solicitacoes_assinatura')
    processo = models.ForeignKey(Processo, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='solicitacoes_assinatura')
    finalidade = models.CharField(max_length=255)
    arquivo_original = models.FileField(upload_to='assinaturas/originais/%Y/%m/%d/')
    arquivo_p7s = models.FileField(upload_to='assinaturas/p7s/%Y/%m/%d/', blank=True)
    hash_original = models.CharField(max_length=64, editable=False)
    hash_p7s = models.CharField(max_length=64, blank=True, editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='PENDENTE')
    certificado_subject = models.TextField(blank=True)
    certificado_issuer = models.TextField(blank=True)
    validacao = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Solicitação de assinatura'
        verbose_name_plural = 'Solicitações de assinatura'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.finalidade} ({self.get_status_display()})'


class Audiencia(models.Model):
    TIPO_CHOICES = [
        ('CONCILIACAO', 'Conciliação / Mediação'),
        ('INSTRUCAO', 'Instrução e Julgamento'),
        ('UNA', 'Una'),
        ('PRELIMINAR', 'Preliminar'),
        ('OUTRA', 'Outra'),
    ]
    STATUS_CHOICES = [
        ('AGENDADA', 'Agendada'),
        ('REALIZADA', 'Realizada'),
        ('CANCELADA', 'Cancelada'),
        ('ADIADA', 'Adiada'),
    ]

    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='audiencias',
                                 null=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='audiencias')
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES, default='CONCILIACAO')
    data_hora = models.DateTimeField('Data e hora')
    local = models.CharField(max_length=255, blank=True)
    link_virtual = models.URLField('Link (audiência virtual)', blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='AGENDADA')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='audiencias_responsavel')
    observacoes = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='audiencias')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Audiência'
        verbose_name_plural = 'Audiências'
        ordering = ['data_hora']

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.data_hora:%d/%m/%Y %H:%M}'


# ---------------------------------------------------------------------------
# Prazos
# ---------------------------------------------------------------------------
class Prazo(models.Model):
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
    ]
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('CUMPRIDO', 'Cumprido'),
        ('PERDIDO', 'Perdido'),
    ]

    titulo = models.CharField('Título', max_length=255)
    descricao = models.TextField('Descrição', blank=True)
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='prazos',
                                 null=True, blank=True)
    data_fatal = models.DateField('Data fatal')
    prioridade = models.CharField(max_length=6, choices=PRIORIDADE_CHOICES, default='MEDIA')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDENTE')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='prazos_responsavel')
    concluido_em = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prazos')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prazo'
        verbose_name_plural = 'Prazos'
        ordering = ['data_fatal']

    def __str__(self):
        return f'{self.titulo} - {self.data_fatal:%d/%m/%Y}'

    @property
    def dias_restantes(self):
        return (self.data_fatal - timezone.localdate()).days

    @property
    def atrasado(self):
        return self.status == 'PENDENTE' and self.data_fatal < timezone.localdate()


# ---------------------------------------------------------------------------
# Tarefas / Rotina
# ---------------------------------------------------------------------------
class Tarefa(models.Model):
    STATUS_CHOICES = [
        ('AFAZER', 'A fazer'),
        ('FAZENDO', 'Em andamento'),
        ('CONCLUIDA', 'Concluída'),
    ]
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
    ]

    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    processo = models.ForeignKey(Processo, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='tarefas')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='tarefas')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='tarefas_responsavel')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='AFAZER')
    prioridade = models.CharField(max_length=6, choices=PRIORIDADE_CHOICES, default='MEDIA')
    prazo = models.DateField('Prazo', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tarefas')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tarefa'
        verbose_name_plural = 'Tarefas'
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo


# ---------------------------------------------------------------------------
# Agenda / Compromissos
# ---------------------------------------------------------------------------
class Compromisso(models.Model):
    TIPO_CHOICES = [
        ('REUNIAO', 'Reunião'),
        ('ATENDIMENTO', 'Atendimento'),
        ('DILIGENCIA', 'Diligência'),
        ('OUTRO', 'Outro'),
    ]

    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES, default='REUNIAO')
    inicio = models.DateTimeField('Início')
    fim = models.DateTimeField('Fim', null=True, blank=True)
    local = models.CharField(max_length=255, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='compromissos')
    processo = models.ForeignKey(Processo, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='compromissos')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='compromissos')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Compromisso'
        verbose_name_plural = 'Compromissos'
        ordering = ['inicio']

    def __str__(self):
        return f'{self.titulo} - {self.inicio:%d/%m/%Y %H:%M}'


# ---------------------------------------------------------------------------
# Financeiro
# ---------------------------------------------------------------------------
class LancamentoFinanceiro(models.Model):
    TIPO_CHOICES = [
        ('RECEITA', 'Receita'),
        ('DESPESA', 'Despesa'),
    ]
    CATEGORIA_CHOICES = [
        ('HONORARIOS', 'Honorários'),
        ('CUSTAS', 'Custas processuais'),
        ('REEMBOLSO', 'Reembolso'),
        ('SALARIO', 'Salário / Pró-labore'),
        ('ALUGUEL', 'Aluguel'),
        ('FORNECEDOR', 'Fornecedor'),
        ('IMPOSTO', 'Imposto / Tributo'),
        ('OUTRO', 'Outro'),
    ]
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('PAGO', 'Pago / Recebido'),
        ('ATRASADO', 'Atrasado'),
    ]

    tipo = models.CharField(max_length=8, choices=TIPO_CHOICES, default='RECEITA')
    categoria = models.CharField(max_length=12, choices=CATEGORIA_CHOICES, default='HONORARIOS')
    descricao = models.CharField('Descrição', max_length=255)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    data_vencimento = models.DateField('Vencimento')
    data_pagamento = models.DateField('Pagamento', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDENTE')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='lancamentos')
    processo = models.ForeignKey(Processo, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='lancamentos')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lancamentos')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lançamento financeiro'
        verbose_name_plural = 'Lançamentos financeiros'
        ordering = ['-data_vencimento']

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.descricao} - R$ {self.valor}'
