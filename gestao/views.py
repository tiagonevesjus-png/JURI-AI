"""Views do painel de gestão jurídica (dashboard, processos, agenda,
prazos, audiências, tarefas, financeiro, relatórios e controle de acessos)."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuarios.models import Cliente
from .forms import (
    ProcessoForm, MovimentacaoForm, AudienciaForm, PrazoForm, TarefaForm,
    CompromissoForm, LancamentoForm,
)
from .models import (
    Perfil, Processo, Audiencia, Prazo, Tarefa, Compromisso, LancamentoFinanceiro,
)


# ---------------------------------------------------------------------------
# Dashboard / Indicadores
# ---------------------------------------------------------------------------
@login_required
def dashboard(request):
    user = request.user
    hoje = timezone.localdate()
    em_sete_dias = hoje + timedelta(days=7)
    agora = timezone.now()

    processos = Processo.objects.filter(user=user)
    prazos = Prazo.objects.filter(user=user)
    audiencias = Audiencia.objects.filter(user=user)
    lancamentos = LancamentoFinanceiro.objects.filter(user=user)

    receitas = lancamentos.filter(tipo='RECEITA', status='PAGO').aggregate(t=Sum('valor'))['t'] or 0
    despesas = lancamentos.filter(tipo='DESPESA', status='PAGO').aggregate(t=Sum('valor'))['t'] or 0
    a_receber = lancamentos.filter(tipo='RECEITA', status='PENDENTE').aggregate(t=Sum('valor'))['t'] or 0

    contexto = {
        'total_clientes': Cliente.objects.filter(user=user).count(),
        'processos_ativos': processos.filter(status='ANDAMENTO').count(),
        'processos_total': processos.count(),
        'prazos_pendentes': prazos.filter(status='PENDENTE').count(),
        'prazos_vencendo': prazos.filter(status='PENDENTE', data_fatal__range=[hoje, em_sete_dias]).count(),
        'prazos_atrasados': prazos.filter(status='PENDENTE', data_fatal__lt=hoje).count(),
        'audiencias_proximas': audiencias.filter(status='AGENDADA', data_hora__gte=agora).count(),
        'tarefas_abertas': Tarefa.objects.filter(user=user).exclude(status='CONCLUIDA').count(),
        'receitas': receitas,
        'despesas': despesas,
        'saldo': receitas - despesas,
        'a_receber': a_receber,
        # Listas para os widgets
        'proximos_prazos': prazos.filter(status='PENDENTE').order_by('data_fatal')[:6],
        'proximas_audiencias': audiencias.filter(status='AGENDADA', data_hora__gte=agora)
                                         .order_by('data_hora')[:6],
        'tarefas_recentes': Tarefa.objects.filter(user=user).exclude(status='CONCLUIDA')[:6],
        'processos_por_area': list(
            processos.values('area').annotate(total=Count('id')).order_by('-total')
        ),
        'processos_recentes': processos[:5],
    }
    return render(request, 'gestao/dashboard.html', contexto)


# ---------------------------------------------------------------------------
# Processos
# ---------------------------------------------------------------------------
@login_required
def processos(request):
    qs = Processo.objects.filter(user=request.user).select_related('cliente')
    busca = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    area = request.GET.get('area', '').strip()
    if busca:
        qs = qs.filter(Q(titulo__icontains=busca) | Q(numero__icontains=busca) |
                       Q(cliente__nome__icontains=busca) | Q(parte_contraria__icontains=busca))
    if status:
        qs = qs.filter(status=status)
    if area:
        qs = qs.filter(area=area)

    contexto = {
        'processos': qs,
        'busca': busca,
        'status_atual': status,
        'area_atual': area,
        'status_choices': Processo.STATUS_CHOICES,
        'area_choices': Processo.AREA_CHOICES,
        'form': ProcessoForm(user=request.user),
    }
    return render(request, 'gestao/processos.html', contexto)


@login_required
def processo_novo(request):
    if request.method == 'POST':
        form = ProcessoForm(request.POST, user=request.user)
        if form.is_valid():
            processo = form.save(commit=False)
            processo.user = request.user
            if not processo.responsavel:
                processo.responsavel = request.user
            processo.save()
            messages.success(request, 'Processo cadastrado com sucesso!')
            return redirect('processo_detalhe', id=processo.id)
        messages.error(request, 'Verifique os dados do processo.')
    return redirect('processos')


@login_required
def processo_detalhe(request, id):
    processo = get_object_or_404(Processo, id=id, user=request.user)
    if request.method == 'POST':
        mov_form = MovimentacaoForm(request.POST, user=request.user)
        if mov_form.is_valid():
            mov = mov_form.save(commit=False)
            mov.processo = processo
            mov.save()
            messages.success(request, 'Movimentação registrada.')
            return redirect('processo_detalhe', id=processo.id)
    contexto = {
        'processo': processo,
        'movimentacoes': processo.movimentacoes.all(),
        'audiencias': processo.audiencias.all(),
        'prazos': processo.prazos.all(),
        'lancamentos': processo.lancamentos.all(),
        'mov_form': MovimentacaoForm(user=request.user),
    }
    return render(request, 'gestao/processo_detalhe.html', contexto)


# ---------------------------------------------------------------------------
# Agenda / Compromissos
# ---------------------------------------------------------------------------
@login_required
def agenda(request):
    user = request.user
    agora = timezone.now()
    compromissos = Compromisso.objects.filter(user=user, inicio__gte=agora - timedelta(days=1))
    audiencias = Audiencia.objects.filter(user=user, status='AGENDADA', data_hora__gte=agora)

    # Agrega tudo em uma linha do tempo unificada.
    eventos = []
    for c in compromissos:
        eventos.append({'quando': c.inicio, 'titulo': c.titulo, 'tipo': c.get_tipo_display(),
                        'categoria': 'compromisso', 'local': c.local})
    for a in audiencias:
        eventos.append({'quando': a.data_hora, 'titulo': f'Audiência: {a.get_tipo_display()}',
                        'tipo': 'Audiência', 'categoria': 'audiencia',
                        'local': a.local or a.link_virtual})
    eventos.sort(key=lambda e: e['quando'])

    if request.method == 'POST':
        form = CompromissoForm(request.POST, user=user)
        if form.is_valid():
            comp = form.save(commit=False)
            comp.user = user
            comp.save()
            messages.success(request, 'Compromisso agendado!')
            return redirect('agenda')
        messages.error(request, 'Verifique os dados do compromisso.')

    return render(request, 'gestao/agenda.html', {
        'eventos': eventos,
        'form': CompromissoForm(user=user),
    })


# ---------------------------------------------------------------------------
# Prazos
# ---------------------------------------------------------------------------
@login_required
def prazos(request):
    qs = Prazo.objects.filter(user=request.user).select_related('processo')
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    if request.method == 'POST':
        form = PrazoForm(request.POST, user=request.user)
        if form.is_valid():
            prazo = form.save(commit=False)
            prazo.user = request.user
            prazo.responsavel = request.user
            prazo.save()
            messages.success(request, 'Prazo cadastrado!')
            return redirect('prazos')
        messages.error(request, 'Verifique os dados do prazo.')

    return render(request, 'gestao/prazos.html', {
        'prazos': qs,
        'status_atual': status,
        'status_choices': Prazo.STATUS_CHOICES,
        'form': PrazoForm(user=request.user),
    })


@login_required
def prazo_concluir(request, id):
    prazo = get_object_or_404(Prazo, id=id, user=request.user)
    prazo.status = 'CUMPRIDO'
    prazo.concluido_em = timezone.now()
    prazo.save()
    messages.success(request, 'Prazo marcado como cumprido.')
    return redirect('prazos')


# ---------------------------------------------------------------------------
# Audiências
# ---------------------------------------------------------------------------
@login_required
def audiencias(request):
    qs = Audiencia.objects.filter(user=request.user).select_related('processo', 'cliente')
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    if request.method == 'POST':
        form = AudienciaForm(request.POST, user=request.user)
        if form.is_valid():
            aud = form.save(commit=False)
            aud.user = request.user
            aud.responsavel = request.user
            aud.save()
            messages.success(request, 'Audiência agendada!')
            return redirect('audiencias')
        messages.error(request, 'Verifique os dados da audiência.')

    return render(request, 'gestao/audiencias.html', {
        'audiencias': qs,
        'status_atual': status,
        'status_choices': Audiencia.STATUS_CHOICES,
        'form': AudienciaForm(user=request.user),
    })


# ---------------------------------------------------------------------------
# Tarefas (quadro / rotina)
# ---------------------------------------------------------------------------
@login_required
def tarefas(request):
    qs = Tarefa.objects.filter(user=request.user)
    if request.method == 'POST':
        form = TarefaForm(request.POST, user=request.user)
        if form.is_valid():
            tarefa = form.save(commit=False)
            tarefa.user = request.user
            if not tarefa.responsavel:
                tarefa.responsavel = request.user
            tarefa.save()
            messages.success(request, 'Tarefa criada!')
            return redirect('tarefas')
        messages.error(request, 'Verifique os dados da tarefa.')

    return render(request, 'gestao/tarefas.html', {
        'afazer': qs.filter(status='AFAZER'),
        'fazendo': qs.filter(status='FAZENDO'),
        'concluidas': qs.filter(status='CONCLUIDA')[:20],
        'form': TarefaForm(user=request.user),
    })


@login_required
def tarefa_status(request, id, status):
    tarefa = get_object_or_404(Tarefa, id=id, user=request.user)
    if status in dict(Tarefa.STATUS_CHOICES):
        tarefa.status = status
        tarefa.save()
    return redirect('tarefas')


# ---------------------------------------------------------------------------
# Financeiro
# ---------------------------------------------------------------------------
@login_required
def financeiro(request):
    qs = LancamentoFinanceiro.objects.filter(user=request.user).select_related('cliente', 'processo')
    tipo = request.GET.get('tipo', '').strip()
    if tipo:
        qs = qs.filter(tipo=tipo)

    if request.method == 'POST':
        form = LancamentoForm(request.POST, user=request.user)
        if form.is_valid():
            lanc = form.save(commit=False)
            lanc.user = request.user
            lanc.save()
            messages.success(request, 'Lançamento registrado!')
            return redirect('financeiro')
        messages.error(request, 'Verifique os dados do lançamento.')

    todos = LancamentoFinanceiro.objects.filter(user=request.user)
    receitas = todos.filter(tipo='RECEITA', status='PAGO').aggregate(t=Sum('valor'))['t'] or 0
    despesas = todos.filter(tipo='DESPESA', status='PAGO').aggregate(t=Sum('valor'))['t'] or 0
    a_receber = todos.filter(tipo='RECEITA', status='PENDENTE').aggregate(t=Sum('valor'))['t'] or 0
    a_pagar = todos.filter(tipo='DESPESA', status='PENDENTE').aggregate(t=Sum('valor'))['t'] or 0

    return render(request, 'gestao/financeiro.html', {
        'lancamentos': qs,
        'tipo_atual': tipo,
        'receitas': receitas,
        'despesas': despesas,
        'saldo': receitas - despesas,
        'a_receber': a_receber,
        'a_pagar': a_pagar,
        'form': LancamentoForm(user=request.user),
    })


# ---------------------------------------------------------------------------
# Relatórios / Indicadores
# ---------------------------------------------------------------------------
@login_required
def relatorios(request):
    user = request.user
    processos = Processo.objects.filter(user=user)
    lancamentos = LancamentoFinanceiro.objects.filter(user=user)

    por_area = list(processos.values('area').annotate(total=Count('id')).order_by('-total'))
    area_labels = dict(Processo.AREA_CHOICES)
    for item in por_area:
        item['nome'] = area_labels.get(item['area'], item['area'])

    por_status = list(processos.values('status').annotate(total=Count('id')).order_by('-total'))
    status_labels = dict(Processo.STATUS_CHOICES)
    for item in por_status:
        item['nome'] = status_labels.get(item['status'], item['status'])

    receita_categoria = list(
        lancamentos.filter(tipo='RECEITA').values('categoria')
        .annotate(total=Sum('valor')).order_by('-total')
    )
    cat_labels = dict(LancamentoFinanceiro.CATEGORIA_CHOICES)
    for item in receita_categoria:
        item['nome'] = cat_labels.get(item['categoria'], item['categoria'])

    return render(request, 'gestao/relatorios.html', {
        'total_processos': processos.count(),
        'por_area': por_area,
        'por_status': por_status,
        'receita_categoria': receita_categoria,
        'prazos_cumpridos': Prazo.objects.filter(user=user, status='CUMPRIDO').count(),
        'prazos_perdidos': Prazo.objects.filter(user=user, status='PERDIDO').count(),
        'audiencias_realizadas': Audiencia.objects.filter(user=user, status='REALIZADA').count(),
    })


# ---------------------------------------------------------------------------
# Controle de acessos (apenas administradores)
# ---------------------------------------------------------------------------
@login_required
def acessos(request):
    perfil = getattr(request.user, 'perfil', None)
    is_admin = request.user.is_superuser or (perfil and perfil.cargo == 'ADMIN')
    if not is_admin:
        messages.error(request, 'Apenas administradores acessam o controle de acessos.')
        return redirect('dashboard')

    return render(request, 'gestao/acessos.html', {
        'perfis': Perfil.objects.select_related('user').all(),
        'cargo_choices': Perfil.CARGO_CHOICES,
    })
