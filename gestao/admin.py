from django.contrib import admin

from .models import (
    Perfil, Processo, MovimentacaoProcesso, Audiencia, Prazo, Tarefa,
    Compromisso, LancamentoFinanceiro,
)


class MovimentacaoInline(admin.TabularInline):
    model = MovimentacaoProcesso
    extra = 0


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'user', 'cargo', 'oab', 'ativo')
    list_filter = ('cargo', 'ativo')
    search_fields = ('nome_completo', 'user__username', 'oab')


@admin.register(Processo)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'numero', 'cliente', 'area', 'status', 'monitorar_pje',
                    'pje_sincronizado_em', 'responsavel', 'criado_em')
    list_filter = ('area', 'status', 'instancia', 'monitorar_pje')
    search_fields = ('titulo', 'numero', 'cliente__nome', 'parte_contraria')
    readonly_fields = ('pje_sincronizado_em',)
    inlines = [MovimentacaoInline]
    date_hierarchy = 'criado_em'


@admin.register(Audiencia)
class AudienciaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'data_hora', 'processo', 'cliente', 'status', 'responsavel')
    list_filter = ('tipo', 'status')
    search_fields = ('processo__titulo', 'cliente__nome', 'local')
    date_hierarchy = 'data_hora'


@admin.register(Prazo)
class PrazoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_fatal', 'prioridade', 'status', 'processo', 'responsavel')
    list_filter = ('status', 'prioridade')
    search_fields = ('titulo', 'processo__titulo')
    date_hierarchy = 'data_fatal'


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'status', 'prioridade', 'prazo', 'responsavel')
    list_filter = ('status', 'prioridade')
    search_fields = ('titulo',)


@admin.register(Compromisso)
class CompromissoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'inicio', 'fim', 'cliente', 'processo')
    list_filter = ('tipo',)
    search_fields = ('titulo', 'cliente__nome')
    date_hierarchy = 'inicio'


@admin.register(LancamentoFinanceiro)
class LancamentoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'tipo', 'categoria', 'valor', 'data_vencimento', 'status')
    list_filter = ('tipo', 'categoria', 'status')
    search_fields = ('descricao', 'cliente__nome')
    date_hierarchy = 'data_vencimento'
