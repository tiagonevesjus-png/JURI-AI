"""Views do painel de gestão jurídica (dashboard, processos, agenda,
prazos, audiências, tarefas, financeiro, relatórios e controle de acessos)."""

import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest
from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from usuarios.models import Cliente
from .forms import (
    ProcessoForm, MovimentacaoForm, AudienciaForm, PrazoForm, TarefaForm,
    CompromissoForm, LancamentoForm, SolicitacaoAssinaturaForm, FeriadoForenseForm,
    RelatorioProcessosForm, RelatorioPrazosForm, RelatorioAudienciasForm,
    RelatorioMovimentacoesForm, RelatorioFinanceiroForm, RelatorioResumoDiarioForm,
)
from .models import (
    Perfil, Processo, Audiencia, Prazo, Tarefa, Compromisso, LancamentoFinanceiro,
    PublicacaoDJEN, SolicitacaoAssinatura, ItemGoogle, TriagemJuridica, ProcessoColetado, FeriadoForense,
)
from .services.datajud import DataJudError, sincronizar as sincronizar_datajud
from .services.djen import DJENError, sincronizar as sincronizar_djen
from .services.google_workspace import GoogleWorkspaceError, concluir_autorizacao
from .models import Notificacao
from .services.assinaturas import AssinaturaError, sha256_arquivo, validar_p7s
from .services.notificacoes import criar as criar_notificacao
from .services.prazos import _feriados_aplicaveis
from .services.exportacao import (
    dados_relatorio, filtrar_processos, gerar_excel_processos, gerar_excel_tabela,
    gerar_pdf_processos, gerar_pdf_tabela,
)


def google_oauth_callback(request):
    """Recebe o retorno OAuth no Django, sem depender de servidor temporário."""
    try:
        concluir_autorizacao(
            request.GET.get('state', ''),
            request.GET.get('code', ''),
            request.GET.get('error', ''),
        )
    except GoogleWorkspaceError as exc:
        return HttpResponse(
            f'<h2>Não foi possível concluir a autorização.</h2><p>{exc}</p>',
            status=400,
            content_type='text/html; charset=utf-8',
        )
    return HttpResponse(
        '<h2>Google conectado com sucesso.</h2><p>Gmail está autorizado para leitura e envio de alertas; Agenda e Drive permanecem somente para leitura. Você pode fechar esta janela.</p>',
        content_type='text/html; charset=utf-8',
    )


@login_required
def notificacoes(request):
    itens = Notificacao.objects.filter(user=request.user)
    return render(request, 'gestao/notificacoes.html', {'notificacoes': itens[:200]})


@login_required
def notificacoes_feed(request):
    itens = Notificacao.objects.filter(user=request.user, lida_em__isnull=True)[:20]
    return HttpResponse(json.dumps([{'id': n.id, 'titulo': n.titulo, 'mensagem': n.mensagem, 'prioridade': n.prioridade} for n in itens]), content_type='application/json')


@login_required
def notificacao_ler(request, id):
    if request.method == 'POST':
        alerta = get_object_or_404(Notificacao, id=id, user=request.user)
        alerta.lida_em = timezone.now()
        alerta.save(update_fields=['lida_em'])
    return redirect('notificacoes')


@login_required
def assinaturas(request):
    """Central de assinatura assistida por DesktopID/PJeOffice."""
    if request.method == 'POST':
        form = SolicitacaoAssinaturaForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.user = request.user
            solicitacao.hash_original = sha256_arquivo(solicitacao.arquivo_original)
            solicitacao.save()
            messages.success(request, 'Documento preparado. Baixe o PDF, assine pelo PJeOffice e envie o arquivo .p7s retornado.')
            return redirect('assinaturas')
    else:
        form = SolicitacaoAssinaturaForm(user=request.user)
    itens = SolicitacaoAssinatura.objects.filter(user=request.user).select_related('processo')
    return render(request, 'gestao/assinaturas.html', {'form': form, 'assinaturas': itens[:100]})


@login_required
def assinatura_baixar_original(request, uid):
    solicitacao = get_object_or_404(SolicitacaoAssinatura, uid=uid, user=request.user)
    solicitacao.status = 'EM_ASSINATURA'
    solicitacao.save(update_fields=['status'])
    return FileResponse(solicitacao.arquivo_original.open('rb'), as_attachment=True,
                        filename=solicitacao.arquivo_original.name.rsplit('/', 1)[-1])


@login_required
@require_POST
def assinatura_enviar_p7s(request, uid):
    solicitacao = get_object_or_404(SolicitacaoAssinatura, uid=uid, user=request.user)
    arquivo = request.FILES.get('arquivo_p7s')
    if not arquivo or not arquivo.name.lower().endswith('.p7s'):
        messages.error(request, 'Envie o arquivo .p7s gerado pelo PJeOffice.')
        return redirect('assinaturas')
    if arquivo.size > 10 * 1024 * 1024:
        messages.error(request, 'O arquivo .p7s não pode ultrapassar 10 MB.')
        return redirect('assinaturas')
    try:
        validacao = validar_p7s(solicitacao.arquivo_original, arquivo)
    except AssinaturaError as exc:
        solicitacao.status = 'FALHOU'
        solicitacao.validacao = {'valida': False, 'erro': str(exc)}
        solicitacao.save(update_fields=['status', 'validacao'])
        messages.error(request, f'Não foi possível validar a assinatura: {exc}')
        return redirect('assinaturas')
    solicitacao.arquivo_p7s = arquivo
    solicitacao.hash_p7s = sha256_arquivo(arquivo)
    solicitacao.certificado_subject = validacao.get('subject', '')
    solicitacao.certificado_issuer = validacao.get('issuer', '')
    solicitacao.validacao = validacao
    solicitacao.status = 'ASSINADO'
    solicitacao.concluido_em = timezone.now()
    solicitacao.save()
    criar_notificacao(
        request.user, 'SISTEMA', 'Documento assinado e validado',
        f'{solicitacao.finalidade}: assinatura P7S validada com sucesso.',
        prioridade='NORMAL', link=request.build_absolute_uri('/assinaturas/'),
        dados={'solicitacao_assinatura': str(solicitacao.uid), 'hash_original': solicitacao.hash_original},
    )
    messages.success(request, 'Assinatura validada criptograficamente e registrada no JURI-AI.')
    return redirect('assinaturas')


@login_required
def push_config(request):
    """Expoe somente a chave publica necessaria para o navegador."""
    habilitado = bool(settings.WEBPUSH_VAPID_PUBLIC_KEY and settings.WEBPUSH_VAPID_PRIVATE_KEY)
    return JsonResponse({
        'habilitado': habilitado,
        'chave_publica': settings.WEBPUSH_VAPID_PUBLIC_KEY if habilitado else '',
    })


@login_required
@require_POST
def push_subscribe(request):
    try:
        dados = json.loads(request.body)
        endpoint = dados['endpoint']
        chaves = dados['keys']
        p256dh, auth = chaves['p256dh'], chaves['auth']
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'erro': 'Inscricao push invalida.'}, status=400)
    if not endpoint.startswith('https://'):
        return JsonResponse({'erro': 'Endpoint push invalido.'}, status=400)
    from .models import PushSubscription
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={'user': request.user, 'p256dh': p256dh, 'auth': auth},
    )
    return JsonResponse({'ok': True})


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        endpoint = json.loads(request.body)['endpoint']
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'erro': 'Endpoint push invalido.'}, status=400)
    from .models import PushSubscription
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'ok': True})


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
# Painel operacional do dia
# ---------------------------------------------------------------------------
@login_required
def hoje(request):
    """Reúne a triagem e os compromissos operacionais sem criar prazos."""
    user = request.user
    data = timezone.localdate()
    agora = timezone.now()
    inicio = timezone.make_aware(datetime.combine(data, datetime.min.time()))
    fim = inicio + timedelta(days=1)
    return render(request, 'gestao/hoje.html', {
        'hoje': data,
        'triagens': TriagemJuridica.objects.filter(user=user, criado_em__gte=inicio, criado_em__lt=fim).select_related('processo'),
        'prazos': Prazo.objects.filter(user=user, status='PENDENTE', data_fatal__range=[data, data + timedelta(days=7)]).select_related('processo'),
        'audiencias': Audiencia.objects.filter(user=user, status='AGENDADA', data_hora__gte=agora, data_hora__lt=agora + timedelta(days=7)).select_related('processo'),
        'agenda_google': ItemGoogle.objects.filter(user=user, fonte='AGENDA', ocorrido_em__gte=inicio, ocorrido_em__lt=fim),
        'publicacoes_hoje': PublicacaoDJEN.objects.filter(user=user, criado_em__gte=inicio, criado_em__lt=fim).select_related('processo')[:20],
        'movimentacoes_relevantes': TriagemJuridica.objects.filter(user=user, fonte='DATAJUD', criado_em__gte=inicio, criado_em__lt=fim).exclude(categoria__in=['JUNTADA', 'OUTRO']).select_related('processo')[:20],
        'emails_importantes': ItemGoogle.objects.filter(user=user, fonte='GMAIL', criado_em__gte=inicio, criado_em__lt=fim)[:20],
        'tarefas_pendentes': Tarefa.objects.filter(user=user).exclude(status='CONCLUIDA')[:20],
        'alertas_nao_lidos': Notificacao.objects.filter(user=user, lida_em__isnull=True).exclude(tipo__in=['DJEN', 'GMAIL', 'AGENDA']).count(),
    })


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
        'coletas_pendentes': ProcessoColetado.objects.filter(
            user=request.user, status='PENDENTE'
        ).count(),
        'busca': busca,
        'status_atual': status,
        'area_atual': area,
        'status_choices': Processo.STATUS_CHOICES,
        'area_choices': Processo.AREA_CHOICES,
        'form': ProcessoForm(user=request.user),
    }
    return render(request, 'gestao/processos.html', contexto)


@login_required
def processos_coletados(request):
    """Fila de conferência para processos descobertos em portais externos.

    Esta tela é deliberadamente separada da lista principal: só processos
    com vínculo seguro a um cliente entram automaticamente na carteira.
    """
    itens = ProcessoColetado.objects.filter(user=request.user).select_related('processo')
    clientes = Cliente.objects.filter(user=request.user, status=True).order_by('nome')
    return render(request, 'gestao/processos_coletados.html', {'itens': itens[:500], 'clientes': clientes})


@login_required
@require_POST
def processo_coletado_importar(request, id):
    """Converte uma coleta em processo somente após escolha explícita do cliente."""
    item = get_object_or_404(ProcessoColetado, id=id, user=request.user)
    cliente = get_object_or_404(Cliente, id=request.POST.get('cliente_id'), user=request.user, status=True)
    somente_digitos = ''.join(ch for ch in item.numero if ch.isdigit())
    existente = next(
        (p for p in Processo.objects.filter(user=request.user).select_related('cliente')
         if ''.join(ch for ch in (p.numero or '') if ch.isdigit()) == somente_digitos),
        None,
    )
    if existente:
        item.processo = existente
        item.status = 'VINCULADO'
        item.save(update_fields=['processo', 'status', 'atualizado_em'])
        messages.info(request, 'A coleta já correspondia a um processo existente; o vínculo foi registrado.')
        return redirect('processos_coletados')
    processo = Processo.objects.create(
        user=request.user,
        responsavel=request.user,
        cliente=cliente,
        numero=item.numero,
        titulo=item.titulo or f'Processo coletado — {item.numero}',
        tribunal=item.tribunal,
        area='TRABALHISTA' if 'TRT' in item.tribunal.upper() else 'CIVEL',
        status='ANDAMENTO',
        observacoes=f'Importado da coleta {item.get_fonte_display()} em {timezone.localdate():%d/%m/%Y}.',
    )
    item.processo = processo
    item.status = 'IMPORTADO'
    item.save(update_fields=['processo', 'status', 'atualizado_em'])
    messages.success(request, 'Processo importado para a carteira selecionada. A sincronização DataJud ocorrerá na próxima rotina.')
    return redirect('processos_coletados')


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


@login_required
def processo_sincronizar_datajud(request, id):
    if request.method != 'POST':
        return redirect('processo_detalhe', id=id)
    processo = get_object_or_404(Processo, id=id, user=request.user)
    try:
        novas = sincronizar_datajud(processo)
    except DataJudError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'DataJud sincronizado: {novas} nova(s) movimentacao(oes).')
    return redirect('processo_detalhe', id=id)


@login_required
def publicacoes_djen(request):
    """Tela de leitura das publicações trazidas da API pública do DJEN."""
    hoje = timezone.localdate()
    inicio = hoje - timedelta(days=1)
    if request.method == 'POST':
        try:
            novas, encontradas = sincronizar_djen(request.user, inicio, hoje)
        except DJENError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'DJEN sincronizado: {novas} nova(s) publicação(ões) de {encontradas} encontrada(s).')
        return redirect('publicacoes_djen')
    return render(request, 'gestao/publicacoes_djen.html', {
        'publicacoes': PublicacaoDJEN.objects.filter(user=request.user).select_related('processo')[:100],
        'inicio_consulta': inicio,
        'fim_consulta': hoje,
    })


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
            # O formulário é a confirmação expressa da pessoa responsável.
            prazo.confirmado_em = timezone.now()
            prazo.feriados_considerados = [
                {'data': item.data.isoformat(), 'descricao': item.descricao, 'abrangencia': item.abrangencia}
                for item in _feriados_aplicaveis(prazo).values()
                if prazo.termo_inicial and prazo.termo_inicial <= item.data <= prazo.data_fatal
            ]
            prazo.save()
            messages.success(request, 'Prazo cadastrado e confirmado. Os avisos serão enviados nos marcos configurados.')
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


@login_required
def feriados_forenses(request):
    if request.method == 'POST':
        form = FeriadoForenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Feriado incluído como apoio à conferência de prazos.')
            return redirect('feriados_forenses')
        messages.error(request, 'Verifique os dados do feriado.')
    return render(request, 'gestao/feriados_forenses.html', {
        'feriados': FeriadoForense.objects.filter(ativo=True),
        'form': FeriadoForenseForm(),
    })


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
        'export_form': RelatorioProcessosForm(user=user),
        'prazos_export_form': RelatorioPrazosForm(user=user),
        'audiencias_export_form': RelatorioAudienciasForm(user=user),
        'movimentacoes_export_form': RelatorioMovimentacoesForm(user=user),
        'financeiro_export_form': RelatorioFinanceiroForm(user=user),
        'resumo_diario_export_form': RelatorioResumoDiarioForm(user=user),
    })


@login_required
def relatorio_processos_download(request, formato):
    """Gera um relatório filtrado em Excel ou PDF sem expor dados de terceiros."""
    if formato not in {'xlsx', 'pdf'}:
        return HttpResponseBadRequest('Formato de relatório inválido.')
    form = RelatorioProcessosForm(request.GET, user=request.user)
    if not form.is_valid():
        messages.error(request, 'Revise os filtros antes de gerar o relatório.')
        return redirect('relatorios')

    processos = filtrar_processos(request.user, form.cleaned_data)
    data_arquivo = timezone.localdate().strftime('%Y-%m-%d')
    if formato == 'xlsx':
        resposta = HttpResponse(
            gerar_excel_processos(processos, form.cleaned_data),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        resposta['Content-Disposition'] = f'attachment; filename="juri-ai-processos-{data_arquivo}.xlsx"'
        return resposta
    resposta = HttpResponse(gerar_pdf_processos(processos, form.cleaned_data), content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="juri-ai-processos-{data_arquivo}.pdf"'
    return resposta


RELATORIO_FORMULARIOS = {
    'prazos': RelatorioPrazosForm,
    'audiencias': RelatorioAudienciasForm,
    'movimentacoes': RelatorioMovimentacoesForm,
    'financeiro': RelatorioFinanceiroForm,
    'resumo-diario': RelatorioResumoDiarioForm,
}


@login_required
def relatorio_download(request, tipo, formato):
    """Exporta os relatórios auxiliares em Excel ou PDF conforme os filtros."""
    formulario = RELATORIO_FORMULARIOS.get(tipo)
    if not formulario or formato not in {'xlsx', 'pdf'}:
        return HttpResponseBadRequest('Tipo ou formato de relatório inválido.')
    form = formulario(request.GET, user=request.user)
    if not form.is_valid():
        messages.error(request, 'Revise os filtros antes de gerar o relatório.')
        return redirect('relatorios')
    try:
        titulo, filtros, cabecalhos, linhas = dados_relatorio(request.user, tipo, form.cleaned_data)
    except ValueError:
        return HttpResponseBadRequest('Tipo de relatório inválido.')
    data_arquivo = timezone.localdate().strftime('%Y-%m-%d')
    slug = tipo.replace('-', '_')
    if formato == 'xlsx':
        resposta = HttpResponse(
            gerar_excel_tabela(titulo, filtros, cabecalhos, linhas),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        resposta['Content-Disposition'] = f'attachment; filename="juri-ai-{slug}-{data_arquivo}.xlsx"'
        return resposta
    resposta = HttpResponse(gerar_pdf_tabela(titulo, filtros, cabecalhos, linhas), content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="juri-ai-{slug}-{data_arquivo}.pdf"'
    return resposta


# ---------------------------------------------------------------------------
# Controle de acessos (apenas administradores)
# ---------------------------------------------------------------------------
@login_required
def base_conhecimento(request):
    """Base interna, escrita para o JURI-AI e sem reproduzir material de terceiros."""
    artigos = [
        {'tema': 'Processos', 'titulo': 'Importar processos com segurança', 'resumo': 'Confira o cliente e o status antes de transformar uma coleta externa em processo ativo.', 'passos': ['Revise a fila de processos coletados.', 'Vincule o cliente correto.', 'Mantenha arquivados fora da carteira ativa.']},
        {'tema': 'Expediente', 'titulo': 'Tratar o expediente do dia', 'resumo': 'Use a tela Hoje para consolidar publicações, movimentações, e-mails e compromissos.', 'passos': ['Abra o alerta vinculado.', 'Leia a fonte oficial.', 'Registre a providência ou tarefa.']},
        {'tema': 'Prazos', 'titulo': 'Confirmar prazo antes de alertar', 'resumo': 'O JURI-AI sugere alertas; o marco inicial e a contagem exigem conferência profissional.', 'passos': ['Confira a comunicação oficial.', 'Informe o termo inicial.', 'Confirme o prazo e acompanhe os alertas.']},
        {'tema': 'Assinaturas', 'titulo': 'Assinar documentos pelo fluxo oficial', 'resumo': 'Prepare o PDF no JURI-AI e autorize a assinatura no PJeOffice/DesktopID.', 'passos': ['Revise a versão final.', 'Confirme o hash do arquivo.', 'Autorize no certificado e salve o recibo.']},
        {'tema': 'Integrações', 'titulo': 'Manter rastreabilidade das fontes', 'resumo': 'Cada dado externo deve conservar origem, data de coleta e vínculo com o processo.', 'passos': ['Use apenas fontes autorizadas.', 'Evite duplicar registros.', 'Registre exceções para revisão.']},
    ]
    return render(request, 'gestao/base_conhecimento.html', {'artigos': artigos})


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
