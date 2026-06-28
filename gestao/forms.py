"""Formulários do app de gestão jurídica.

Aplica uma classe Tailwind padrão a todos os widgets para manter o visual
consistente com o restante do sistema.
"""

from django import forms

from usuarios.models import Cliente
from .models import (
    Processo, MovimentacaoProcesso, Audiencia, Prazo, Tarefa,
    Compromisso, LancamentoFinanceiro,
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
    class Meta:
        model = Prazo
        fields = ['titulo', 'descricao', 'processo', 'data_fatal', 'prioridade', 'status']
        widgets = {
            'data_fatal': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 2}),
        }


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
