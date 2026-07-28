"""Testes do app de gestão jurídica: perfis/acesso, multi-tenancy e fluxos."""

import json
import os
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from usuarios.models import Cliente
from .models import (
    Audiencia, Perfil, Processo, Prazo, Tarefa, LancamentoFinanceiro,
    PublicacaoDJEN, SolicitacaoSincronizacaoDJEN, TriagemJuridica,
)
from .services.djen import DJENBloqueioRede, sincronizar as sincronizar_djen


class PerfilSignalTest(TestCase):
    def test_perfil_criado_automaticamente(self):
        user = User.objects.create_user('joao', password='x12345678')
        self.assertTrue(hasattr(user, 'perfil'))
        self.assertEqual(user.perfil.cargo, 'ADVOGADO')

    def test_superuser_vira_admin(self):
        admin = User.objects.create_superuser('chefe', 'c@x.com', 'x12345678')
        self.assertEqual(admin.perfil.cargo, 'ADMIN')


class AutenticacaoTest(TestCase):
    def test_dashboard_exige_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/usuarios/login/', resp.url)

    def test_dashboard_renderiza_logado(self):
        User.objects.create_user('ana', password='x12345678')
        self.client.login(username='ana', password='x12345678')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dashboard')


class ProcessoFluxoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('adv', password='x12345678')
        self.client.login(username='adv', password='x12345678')
        self.cliente = Cliente.objects.create(nome='Cliente X', email='x@x.com', user=self.user)

    def test_cria_processo_e_define_dono(self):
        resp = self.client.post(reverse('processo_novo'), {
            'titulo': 'Ação Teste', 'cliente': self.cliente.id, 'area': 'CIVEL',
            'instancia': '1', 'status': 'ANDAMENTO',
        })
        self.assertEqual(resp.status_code, 302)
        proc = Processo.objects.get(titulo='Ação Teste')
        self.assertEqual(proc.user, self.user)
        self.assertEqual(proc.responsavel, self.user)

    def test_registra_movimentacao(self):
        proc = Processo.objects.create(titulo='P', cliente=self.cliente, user=self.user)
        resp = self.client.post(reverse('processo_detalhe', args=[proc.id]), {
            'data': date.today().isoformat(), 'descricao': 'Juntada de petição',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(proc.movimentacoes.count(), 1)

    def test_publicacoes_exigem_login_e_respeitam_usuario(self):
        outro = User.objects.create_user('outro', password='x12345678')
        PublicacaoDJEN.objects.create(user=outro, identificador_externo='1', texto='Publicação de outro usuário')
        resp = self.client.get(reverse('publicacoes_djen'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Publicação de outro usuário')


class DJENServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('advdjen', password='x12345678')
        self.cliente = Cliente.objects.create(nome='Cliente DJEN', email='djen@x.com', user=self.user)
        self.processo = Processo.objects.create(
            titulo='Processo monitorado', cliente=self.cliente, user=self.user,
            numero='0016068-39.2026.5.16.0003',
        )

    @patch.dict(os.environ, {'DJEN_OAB_NUMERO': '10042', 'DJEN_OAB_UF': 'MA'}, clear=False)
    @patch('gestao.services.djen._cliente_http')
    def test_sincroniza_e_deduplica_publicacoes(self, cliente_http):
        resposta = Mock()
        resposta.status_code = 200
        resposta.raise_for_status.return_value = None
        resposta.json.return_value = {
            'status': 'success', 'count': 1,
            'items': [{
                'id': 987, 'numero_processo': '00160683920265160003',
                'numeroprocessocommascara': '0016068-39.2026.5.16.0003',
                'data_disponibilizacao': '2026-07-22', 'siglaTribunal': 'TRT16',
                'tipoComunicacao': 'Intimação', 'nomeOrgao': 'Vara de teste',
                'texto': 'Teor de teste', 'link': 'https://exemplo.test/publicacao',
            }],
        }
        cliente_http.return_value.get.return_value = resposta
        novas, total = sincronizar_djen(self.user, date(2026, 7, 22), date(2026, 7, 22))
        self.assertEqual((novas, total), (1, 1))
        publicacao = PublicacaoDJEN.objects.get(user=self.user)
        self.assertEqual(publicacao.processo, self.processo)
        novas, total = sincronizar_djen(self.user, date(2026, 7, 22), date(2026, 7, 22))
        self.assertEqual((novas, total), (0, 1))


class DJENBridgeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tiago', email='tiago@example.com', password='x12345678')
        self.cliente = Cliente.objects.create(nome='Cliente ponte', user=self.user)
        self.processo = Processo.objects.create(
            titulo='Processo ponte', cliente=self.cliente, user=self.user,
            numero='0016068-39.2026.5.16.0003',
        )
        self.headers = {'HTTP_X_DJEN_BRIDGE_TOKEN': 'segredo-teste'}

    @patch.dict(os.environ, {
        'DJEN_BRIDGE_TOKEN': 'segredo-teste', 'DJEN_OAB_NUMERO': '10042',
        'DJEN_OAB_UF': 'MA', 'DJEN_IMPORT_USERNAME': 'tiago',
    }, clear=False)
    def test_ponte_exige_token_e_informa_configuracao(self):
        self.assertEqual(self.client.get(reverse('djen_bridge_pendente')).status_code, 401)
        pedido = SolicitacaoSincronizacaoDJEN.objects.create(
            user=self.user, inicio=date(2026, 7, 27), fim=date(2026, 7, 28),
        )
        resp = self.client.get(reverse('djen_bridge_pendente'), **self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['solicitacao']['id'], pedido.id)
        self.assertEqual(resp.json()['numero_oab'], '10042')
        self.assertEqual(resp.json()['uf_oab'], 'MA')

    @patch.dict(os.environ, {
        'DJEN_BRIDGE_TOKEN': 'segredo-teste', 'DJEN_IMPORT_USERNAME': 'tiago',
    }, clear=False)
    def test_importa_e_conclui_solicitacao(self):
        pedido = SolicitacaoSincronizacaoDJEN.objects.create(
            user=self.user, inicio=date(2026, 7, 27), fim=date(2026, 7, 28),
        )
        item = {
            'id': 321, 'numero_processo': '00160683920265160003',
            'numeroprocessocommascara': '0016068-39.2026.5.16.0003',
            'data_disponibilizacao': '2026-07-28', 'siglaTribunal': 'TRT16',
            'tipoComunicacao': 'Intimação', 'texto': 'Teste da ponte',
        }
        resp = self.client.post(
            reverse('djen_bridge_importar'),
            data=json.dumps({'solicitacao_id': pedido.id, 'items': [item]}),
            content_type='application/json', **self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'ok': True, 'novas': 1, 'total': 1})
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'CONCLUIDA')
        self.assertEqual(PublicacaoDJEN.objects.get().processo, self.processo)

    @patch.dict(os.environ, {
        'DJEN_BRIDGE_TOKEN': 'segredo-teste', 'DJEN_IMPORT_USERNAME': 'tiago@example.com',
    }, clear=False)
    def test_importacao_automatica_localiza_usuario_por_email(self):
        item = {
            'id': 654, 'numero_processo': '00160683920265160003',
            'data_disponibilizacao': '2026-07-28', 'siglaTribunal': 'TRT16',
            'tipoComunicacao': 'Intimação', 'texto': 'Importação automática',
        }
        resp = self.client.post(
            reverse('djen_bridge_importar'),
            data=json.dumps({'solicitacao_id': None, 'items': [item]}),
            content_type='application/json', **self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PublicacaoDJEN.objects.get().user, self.user)

    @patch('gestao.views.sincronizar_djen', side_effect=DJENBloqueioRede('bloqueio'))
    def test_tela_cria_pedido_quando_ip_e_bloqueado(self, _sincronizar):
        self.client.login(username='tiago', password='x12345678')
        resp = self.client.post(reverse('publicacoes_djen'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(SolicitacaoSincronizacaoDJEN.objects.filter(status='PENDENTE').count(), 1)


class MultiTenancyTest(TestCase):
    def test_usuario_nao_ve_processo_de_outro(self):
        u1 = User.objects.create_user('u1', password='x12345678')
        u2 = User.objects.create_user('u2', password='x12345678')
        cli = Cliente.objects.create(nome='C', email='c@x.com', user=u1)
        proc = Processo.objects.create(titulo='Sigiloso', cliente=cli, user=u1)

        self.client.login(username='u2', password='x12345678')
        # u2 não enxerga na listagem
        resp = self.client.get(reverse('processos'))
        self.assertNotContains(resp, 'Sigiloso')
        # u2 não acessa o detalhe (404)
        resp = self.client.get(reverse('processo_detalhe', args=[proc.id]))
        self.assertEqual(resp.status_code, 404)


class PrazoTarefaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('adv', password='x12345678')
        self.client.login(username='adv', password='x12345678')

    def test_prazo_concluir(self):
        prazo = Prazo.objects.create(titulo='Recurso', data_fatal=date.today() + timedelta(days=2),
                                     user=self.user)
        self.client.get(reverse('prazo_concluir', args=[prazo.id]))
        prazo.refresh_from_db()
        self.assertEqual(prazo.status, 'CUMPRIDO')
        self.assertIsNotNone(prazo.concluido_em)

    def test_prazo_atrasado_property(self):
        prazo = Prazo.objects.create(titulo='Atrasado', data_fatal=date.today() - timedelta(days=1),
                                     user=self.user)
        self.assertTrue(prazo.atrasado)

    def test_tarefa_muda_status(self):
        tarefa = Tarefa.objects.create(titulo='T', status='AFAZER', user=self.user)
        self.client.get(reverse('tarefa_status', args=[tarefa.id, 'FAZENDO']))
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, 'FAZENDO')

    def test_tarefa_status_invalido_ignorado(self):
        tarefa = Tarefa.objects.create(titulo='T', status='AFAZER', user=self.user)
        self.client.get(reverse('tarefa_status', args=[tarefa.id, 'INEXISTENTE']))
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, 'AFAZER')


class FinanceiroTest(TestCase):
    def test_resumo_financeiro(self):
        user = User.objects.create_user('fin', password='x12345678')
        self.client.login(username='fin', password='x12345678')
        LancamentoFinanceiro.objects.create(tipo='RECEITA', descricao='Honorário', valor=1000,
                                             data_vencimento=date.today(), status='PAGO', user=user)
        LancamentoFinanceiro.objects.create(tipo='DESPESA', descricao='Custa', valor=300,
                                             data_vencimento=date.today(), status='PAGO', user=user)
        resp = self.client.get(reverse('financeiro'))
        self.assertEqual(resp.context['receitas'], 1000)
        self.assertEqual(resp.context['despesas'], 300)
        self.assertEqual(resp.context['saldo'], 700)


class RelatorioProcessosTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('relatorios', password='x12345678')
        self.outro = User.objects.create_user('outrorel', password='x12345678')
        self.cliente = Cliente.objects.create(nome='Cliente Relatório', email='relatorio@x.com', user=self.user)
        cliente_outro = Cliente.objects.create(nome='Cliente Alheio', email='outro@x.com', user=self.outro)
        self.processo = Processo.objects.create(
            titulo='Ação exportável', numero='0000000-00.2026.8.10.0001', cliente=self.cliente,
            area='CIVEL', status='ANDAMENTO', tribunal='TJMA', user=self.user,
        )
        Processo.objects.create(titulo='Processo alheio', cliente=cliente_outro, user=self.outro)
        self.client.login(username='relatorios', password='x12345678')

    def test_exporta_excel_filtrado_por_cliente(self):
        resposta = self.client.get(reverse('relatorio_processos_download', args=['xlsx']), {'cliente': self.cliente.id})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(resposta.content.startswith(b'PK'))
        planilha = load_workbook(BytesIO(resposta.content))
        self.assertEqual(planilha['Processos']['A6'].value, self.processo.numero)
        self.assertEqual(planilha['Processos']['B6'].value, self.processo.titulo)

    def test_exporta_pdf_filtrado_por_cliente(self):
        resposta = self.client.get(reverse('relatorio_processos_download', args=['pdf']), {'cliente': self.cliente.id})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertTrue(resposta.content.startswith(b'%PDF'))

    def test_formulario_de_relatorios_exibe_exportacao(self):
        resposta = self.client.get(reverse('relatorios'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Exportar carteira processual')


class RelatoriosAdicionaisTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('relatoriosplus', password='x12345678')
        self.cliente = Cliente.objects.create(nome='Cliente Plus', email='plus@x.com', user=self.user)
        self.processo = Processo.objects.create(titulo='Processo Plus', numero='0000000-00.2026.8.10.0002', cliente=self.cliente, user=self.user)
        Prazo.objects.create(titulo='Manifestação', processo=self.processo, data_fatal=date.today() + timedelta(days=5), prioridade='ALTA', user=self.user)
        Audiencia.objects.create(processo=self.processo, cliente=self.cliente, data_hora=timezone.now() + timedelta(days=1), user=self.user)
        LancamentoFinanceiro.objects.create(tipo='RECEITA', descricao='Honorários Plus', valor=100, data_vencimento=date.today(), cliente=self.cliente, processo=self.processo, user=self.user)
        TriagemJuridica.objects.create(user=self.user, processo=self.processo, fonte='DATAJUD', identificador_origem='relatorio-plus', titulo_origem='Intimação', categoria='INTIMACAO', prioridade='URGENTE', resumo='Providência necessária')
        self.client.login(username='relatoriosplus', password='x12345678')

    def test_exporta_relatorios_adicionais(self):
        for tipo in ['prazos', 'audiencias', 'movimentacoes', 'financeiro', 'resumo-diario']:
            resposta_excel = self.client.get(reverse('relatorio_download', args=[tipo, 'xlsx']), {'cliente': self.cliente.id})
            self.assertEqual(resposta_excel.status_code, 200)
            self.assertTrue(resposta_excel.content.startswith(b'PK'))
            resposta_pdf = self.client.get(reverse('relatorio_download', args=[tipo, 'pdf']), {'cliente': self.cliente.id})
            self.assertEqual(resposta_pdf.status_code, 200)
            self.assertTrue(resposta_pdf.content.startswith(b'%PDF'))


class ControleAcessoTest(TestCase):
    def test_nao_admin_bloqueado(self):
        User.objects.create_user('comum', password='x12345678')
        self.client.login(username='comum', password='x12345678')
        resp = self.client.get(reverse('acessos'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('dashboard'), resp.url)

    def test_admin_acessa(self):
        admin = User.objects.create_superuser('adm', 'a@x.com', 'x12345678')
        self.client.login(username='adm', password='x12345678')
        resp = self.client.get(reverse('acessos'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Controle de acessos')
