"""Testes da automação do PJe (API Pública do DataJud)."""

from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Cliente
from . import pje
from .models import Processo, MovimentacaoProcesso
from .tasks import sincronizar_processo_pje


# Número CNJ de exemplo (TJSP): 1234567-89.2020.8.26.0100
NUMERO_TJSP = '1234567-89.2020.8.26.0100'

RESPOSTA_DATAJUD = {
    'hits': {
        'hits': [
            {
                '_source': {
                    'numeroProcesso': '12345678920208260100',
                    'tribunal': 'TJSP',
                    'grau': 'G1',
                    'dataAjuizamento': '2020-03-10T00:00:00.000Z',
                    'classe': {'codigo': 7, 'nome': 'Procedimento Comum Cível'},
                    'assuntos': [{'codigo': 1, 'nome': 'Indenização'}],
                    'orgaoJulgador': {'codigo': 1, 'nome': '1ª Vara Cível'},
                    'movimentos': [
                        {'codigo': 26, 'nome': 'Distribuição',
                         'dataHora': '2020-03-10T10:00:00.000Z'},
                        {'codigo': 51, 'nome': 'Juntada de petição',
                         'dataHora': '2020-04-01T14:30:00.000Z'},
                    ],
                }
            }
        ]
    }
}


class CNJParsingTest(TestCase):
    def test_limpar_e_validar(self):
        self.assertEqual(pje.limpar_numero(NUMERO_TJSP), '12345678920208260100')
        self.assertTrue(pje.numero_valido(NUMERO_TJSP))
        self.assertFalse(pje.numero_valido('123'))

    def test_formatar(self):
        self.assertEqual(pje.formatar_numero('12345678920208260100'), NUMERO_TJSP)

    def test_tribunal_estadual(self):
        self.assertEqual(pje.tribunal_para_numero(NUMERO_TJSP), 'api_publica_tjsp')

    def test_tribunal_federal_trabalho_superior(self):
        # TRF1: segmento 4, TR 01
        self.assertEqual(
            pje.tribunal_para_numero('0000832-35.2018.4.01.3202'), 'api_publica_trf1')
        # TRT2: segmento 5, TR 02
        self.assertEqual(
            pje.tribunal_para_numero('0001000-00.2021.5.02.0001'), 'api_publica_trt2')
        # STJ: segmento 3
        self.assertEqual(
            pje.tribunal_para_numero('0001000-00.2021.3.00.0000'), 'api_publica_stj')

    def test_tribunal_desconhecido(self):
        # Segmento 1 (STF) não está na API Pública.
        self.assertIsNone(pje.tribunal_para_numero('0001000-00.2021.1.00.0000'))


class ConsultaDataJudTest(TestCase):
    def _resp_fake(self, status=200, json_data=None):
        resp = mock.Mock()
        resp.status_code = status
        resp.json.return_value = json_data if json_data is not None else RESPOSTA_DATAJUD
        return resp

    def test_consultar_normaliza(self):
        with mock.patch('requests.post', return_value=self._resp_fake()) as post:
            consulta = pje.consultar(NUMERO_TJSP)
        post.assert_called_once()
        self.assertIsNotNone(consulta)
        self.assertEqual(consulta.tribunal, 'TJSP')
        self.assertEqual(consulta.classe, 'Procedimento Comum Cível')
        self.assertEqual(consulta.assunto, 'Indenização')
        self.assertEqual(consulta.total_movimentos, 2)
        # Ordenado do mais antigo para o mais recente.
        self.assertEqual(consulta.movimentos[0].descricao, 'Distribuição')
        self.assertEqual(consulta.movimentos[0].data, date(2020, 3, 10))

    def test_consultar_nao_encontrado(self):
        vazio = {'hits': {'hits': []}}
        with mock.patch('requests.post', return_value=self._resp_fake(json_data=vazio)):
            self.assertIsNone(pje.consultar(NUMERO_TJSP))

    def test_numero_invalido(self):
        with self.assertRaises(pje.PJeIndisponivel):
            pje.consultar('123')

    def test_erro_http(self):
        with mock.patch('requests.post', return_value=self._resp_fake(status=500)):
            with self.assertRaises(pje.PJeIndisponivel):
                pje.consultar(NUMERO_TJSP)


class SincronizacaoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('adv', password='x12345678')
        self.cliente = Cliente.objects.create(nome='C', email='c@x.com', user=self.user)
        self.processo = Processo.objects.create(
            titulo='Ação', numero=NUMERO_TJSP, cliente=self.cliente, user=self.user)

    def _consulta_fake(self):
        return pje.ConsultaProcesso(
            numero='12345678920208260100',
            tribunal='TJSP',
            classe='Procedimento Comum Cível',
            orgao_julgador='1ª Vara Cível',
            data_ajuizamento=date(2020, 3, 10),
            movimentos=[
                pje.Movimento(codigo='26', descricao='Distribuição', data=date(2020, 3, 10)),
                pje.Movimento(codigo='51', descricao='Juntada', data=date(2020, 4, 1)),
            ],
        )

    def test_importa_e_preenche_metadados(self):
        with mock.patch('gestao.pje.consultar', return_value=self._consulta_fake()):
            res = sincronizar_processo_pje(self.processo.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['importadas'], 2)
        self.assertEqual(self.processo.movimentacoes.filter(origem='PJE').count(), 2)
        self.processo.refresh_from_db()
        self.assertEqual(self.processo.vara, '1ª Vara Cível')
        self.assertEqual(self.processo.tipo_acao, 'Procedimento Comum Cível')
        self.assertEqual(self.processo.data_distribuicao, date(2020, 3, 10))
        self.assertIsNotNone(self.processo.pje_sincronizado_em)

    def test_dedup_nao_duplica(self):
        with mock.patch('gestao.pje.consultar', return_value=self._consulta_fake()):
            sincronizar_processo_pje(self.processo.id)
            res2 = sincronizar_processo_pje(self.processo.id)
        self.assertEqual(res2['importadas'], 0)
        self.assertEqual(self.processo.movimentacoes.filter(origem='PJE').count(), 2)

    def test_numero_invalido_nao_consulta(self):
        self.processo.numero = '123'
        self.processo.save()
        res = sincronizar_processo_pje(self.processo.id)
        self.assertFalse(res['ok'])

    def test_view_dispara_sincronizacao(self):
        self.client.login(username='adv', password='x12345678')
        with mock.patch('gestao.tasks.sincronizar_processo_pje',
                        return_value={'ok': True, 'mensagem': 'ok', 'importadas': 1}) as task:
            resp = self.client.post(
                reverse('processo_sincronizar_pje', args=[self.processo.id]))
        self.assertEqual(resp.status_code, 302)
        task.assert_called_once_with(self.processo.id)

    def test_view_exige_dono(self):
        outro = User.objects.create_user('outro', password='x12345678')
        self.client.login(username='outro', password='x12345678')
        resp = self.client.post(
            reverse('processo_sincronizar_pje', args=[self.processo.id]))
        self.assertEqual(resp.status_code, 404)
