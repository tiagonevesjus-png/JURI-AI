"""Testes do app de gestão jurídica: perfis/acesso, multi-tenancy e fluxos."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Cliente
from .models import Perfil, Processo, Prazo, Tarefa, LancamentoFinanceiro


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
