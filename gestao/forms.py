"""Formulários do app de gestão jurídica.

Aplica uma classe Tailwind padrão a todos os widgets para manter o visual
consistente com o restante do sistema.
"""

from django import forms

from usuarios.models import Cliente
from .models import (
    Processo, MovimentacaoProcesso, Audiencia, Prazo, Tarefa,
    Compromisso, LancamentoFinanceiro, SolicitacaoAssinatura, FeriadoForense,
)

INPUT_CLASS = (
    'w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm '
    'focus:ring-2 focus:ring-slate-900/20 focus:border-slate-300 outline-none'
)


class TailwindModelForm(forms.ModelForm):
    """Aplica classes Tailwind automaticamente a todos os campos."""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'h-4 w-4 rounded border-slate-300')
            else:
                widget.attrs.setdefault('class', INPUT_CLASS)
            if isinstance(widget, (forms.DateInput,)):
                widget.input_type = 'date'
            if isinstance(widget, (forms.DateTimeInput,)):
                widget.input_type = 'datetime-local'
        # Restringe os selects de cliente/processo aos registros do usuário.
        if self.user is not None:
            if 'cliente' in self.fields:
                self.fields['cliente'].queryset = Cliente.objects.filter(user=self.user)
            if 'processo' in self.fields:
                self.fields['processo'].queryset = Processo.objects.filter(user=self.user)


class ProcessoForm(TailwindModelForm):
    class Meta:
        model = Processo
        fields = ['titulo', 'numero', 'cliente', 'area', 'tipo_acao', 'parte_contraria',
                  'vara', 'comarca', 'tribunal', 'instancia', 'valor_causa', 'status',
                  'data_distribuicao', 'observacoes']
        widgets = {
            'data_distribuicao': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class RelatorioProcessosForm(forms.Form):
    """Filtros seguros para exportação da carteira processual do usuário."""

    cliente = forms.ModelChoiceField(
        label='Cliente', queryset=Cliente.objects.none(), required=False,
        empty_label='Todos os clientes',
    )
    area = forms.ChoiceField(
        label='Área', required=False,
        choices=[('', 'Todas as áreas')] + Processo.AREA_CHOICES,
    )
    status = forms.ChoiceField(
        label='Status', required=False,
        choices=[('', 'Todos os status')] + Processo.STATUS_CHOICES,
    )
    tribunal = forms.CharField(
        label='Tribunal', required=False, max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Ex.: TJMA, TRT16 ou TRF1'}),
    )
    data_inicial = forms.DateField(
        label='Distribuído de', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    data_final = forms.DateField(
        label='Distribuído até', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = Cliente.objects.filter(user=user).order_by('nome') if user else Cliente.objects.none()
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', INPUT_CLASS)

    def clean(self):
        dados = super().clean()
        inicial, final = dados.get('data_inicial'), dados.get('data_final')
        if inicial and final and inicial > final:
            self.add_error('data_final', 'A data final deve ser igual ou posterior à data inicial.')
        return dados


class RelatorioPeriodoClienteForm(forms.Form):
    """Base para relatórios que pertencem à carteira de um único usuário."""

    cliente = forms.ModelChoiceField(
        label='Cliente', queryset=Cliente.objects.none(), required=False,
        empty_label='Todos os clientes',
    )
    data_inicial = forms.DateField(
        label='De', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
    )
    data_final = forms.DateField(
        label='Até', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = Cliente.objects.filter(user=user).order_by('nome') if user else Cliente.objects.none()
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', INPUT_CLASS)

    def clean(self):
        dados = super().clean()
        if dados.get('data_inicial') and dados.get('data_final') and dados['data_inicial'] > dados['data_final']:
            self.add_error('data_final', 'A data final deve ser igual ou posterior à data inicial.')
        return dados


class RelatorioPrazosForm(RelatorioPeriodoClienteForm):
    prioridade = forms.ChoiceField(label='Prioridade', required=False, choices=[('', 'Todas')] + Prazo.PRIORIDADE_CHOICES)
    status = forms.ChoiceField(label='Status', required=False, choices=[('', 'Todos')] + Prazo.STATUS_CHOICES)


class RelatorioAudienciasForm(RelatorioPeriodoClienteForm):
    tipo = forms.ChoiceField(label='Tipo', required=False, choices=[('', 'Todos')] + Audiencia.TIPO_CHOICES)
    status = forms.ChoiceField(label='Status', required=False, choices=[('', 'Todos')] + Audiencia.STATUS_CHOICES)


class RelatorioMovimentacoesForm(RelatorioPeriodoClienteForm):
    categoria = forms.ChoiceField(
        label='Categoria', required=False,
        choices=[('', 'Todas as relevantes')],
    )
    fonte = forms.ChoiceField(label='Fonte', required=False, choices=[('', 'Todas'), ('DATAJUD', 'DataJud'), ('DJEN', 'DJEN'), ('GMAIL', 'Gmail'), ('AGENDA', 'Google Agenda')])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import TriagemJuridica
        self.fields['categoria'].choices = [('', 'Todas as relevantes')] + TriagemJuridica.CATEGORIA_CHOICES


class RelatorioFinanceiroForm(RelatorioPeriodoClienteForm):
    tipo = forms.ChoiceField(label='Tipo', required=False, choices=[('', 'Receitas e despesas')] + LancamentoFinanceiro.TIPO_CHOICES)
    status = forms.ChoiceField(label='Status', required=False, choices=[('', 'Todos')] + LancamentoFinanceiro.STATUS_CHOICES)


class RelatorioResumoDiarioForm(RelatorioPeriodoClienteForm):
    data = forms.DateField(label='Data do resumo', required=False, widget=forms.DateInput(attrs={'type': 'date'}))


class MovimentacaoForm(TailwindModelForm):
    class Meta:
        model = MovimentacaoProcesso
        fields = ['data', 'descricao']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 2}),
        }


class AudienciaForm(TailwindModelForm):
    class Meta:
        model = Audiencia
        fields = ['tipo', 'data_hora', 'processo', 'cliente', 'local', 'link_virtual',
                  'status', 'observacoes']
        widgets = {
            'data_hora': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
        }


class PrazoForm(TailwindModelForm):
    confirmar_conferencia = forms.BooleanField(
        required=True,
        label='Confirmo que conferi o termo inicial, a data final e o calendário aplicável.',
    )

    class Meta:
        model = Prazo
        fields = ['titulo', 'descricao', 'processo', 'termo_inicial', 'data_fatal', 'regra_contagem', 'prioridade', 'status']
        widgets = {
            'termo_inicial': forms.DateInput(attrs={'type': 'date'}),
            'data_fatal': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        dados = super().clean()
        inicial, final = dados.get('termo_inicial'), dados.get('data_fatal')
        if inicial and final and inicial > final:
            self.add_error('data_fatal', 'A data final não pode ser anterior ao termo inicial.')
        return dados


class FeriadoForenseForm(TailwindModelForm):
    class Meta:
        model = FeriadoForense
        fields = ['data', 'descricao', 'abrangencia', 'tribunal', 'comarca', 'fonte', 'ativo']
        widgets = {'data': forms.DateInput(attrs={'type': 'date'})}


class TarefaForm(TailwindModelForm):
    class Meta:
        model = Tarefa
        fields = ['titulo', 'descricao', 'processo', 'cliente', 'status', 'prioridade', 'prazo']
        widgets = {
            'prazo': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 2}),
        }


class CompromissoForm(TailwindModelForm):
    class Meta:
        model = Compromisso
        fields = ['titulo', 'descricao', 'tipo', 'inicio', 'fim', 'local', 'cliente', 'processo']
        widgets = {
            'inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'descricao': forms.Textarea(attrs={'rows': 2}),
        }


class LancamentoForm(TailwindModelForm):
    class Meta:
        model = LancamentoFinanceiro
        fields = ['tipo', 'categoria', 'descricao', 'valor', 'data_vencimento',
                  'data_pagamento', 'status', 'cliente', 'processo']
        widgets = {
            'data_vencimento': forms.DateInput(attrs={'type': 'date'}),
            'data_pagamento': forms.DateInput(attrs={'type': 'date'}),
        }


class SolicitacaoAssinaturaForm(TailwindModelForm):
    class Meta:
        model = SolicitacaoAssinatura
        fields = ['processo', 'finalidade', 'arquivo_original']

    def clean_arquivo_original(self):
        arquivo = self.cleaned_data['arquivo_original']
        if not arquivo.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Envie somente documentos PDF.')
        limite = 25 * 1024 * 1024
        if arquivo.size > limite:
            raise forms.ValidationError('O PDF não pode ultrapassar 25 MB.')
        return arquivo
