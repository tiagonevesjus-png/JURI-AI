"""Modelos do núcleo de gestão jurídica do Juri-AI.

Reaproveita os modelos ``Cliente`` e ``Documentos`` do app ``usuarios`` e
adiciona as entidades de um escritório de advocacia: processos, audiências,
prazos, tarefas, agenda, financeiro e controle de acesso (perfis).
"""

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
    instancia = models.CharField(max_length=3, choices=INSTANCIA_CHOICES, default='1')
    valor_causa = models.DecimalField('Valor da causa', max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ANDAMENTO')
    data_distribuicao = models.DateField('Data de distribuição', null=True, blank=True)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='processos_responsavel')
    observacoes = models.TextField('Observações', blank=True)
    # Automação PJe / DataJud
    monitorar_pje = models.BooleanField(
        'Monitorar no PJe (DataJud)', default=True,
        help_text='Sincronizar automaticamente as movimentações pela API do DataJud.')
    pje_sincronizado_em = models.DateTimeField('Última sincronização (PJe)', null=True, blank=True)
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

    ORIGEM_CHOICES = [
        ('MANUAL', 'Registro manual'),
        ('PJE', 'PJe / DataJud'),
    ]

    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='movimentacoes')
    data = models.DateField(default=timezone.now)
    descricao = models.TextField('Descrição')
    origem = models.CharField(max_length=6, choices=ORIGEM_CHOICES, default='MANUAL')
    codigo_movimento = models.CharField('Código (DataJud)', max_length=20, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação'
        verbose_name_plural = 'Movimentações'
        ordering = ['-data', '-criado_em']

    def __str__(self):
        return f'{self.processo} - {self.data}'


# ---------------------------------------------------------------------------
# Audiências
# ---------------------------------------------------------------------------
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
