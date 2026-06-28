"""Testes da camada de IA: chunking, seleção de backend e degradação graciosa."""

import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from ia import services


class ChunkingTest(TestCase):
    def test_texto_vazio(self):
        self.assertEqual(services.dividir_em_chunks(''), [])

    def test_paragrafos_pequenos_unidos(self):
        chunks = services.dividir_em_chunks('par1\n\npar2', tamanho=1000)
        self.assertEqual(len(chunks), 1)

    def test_paragrafo_grande_fatiado(self):
        texto = 'x' * 2500
        chunks = services.dividir_em_chunks(texto, tamanho=1000, sobreposicao=100)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 1000 for c in chunks))


class BackendEmbeddingsTest(TestCase):
    @override_settings(IA_EMBEDDING_BACKEND='local')
    def test_local_e_padrao_sem_chave(self):
        self.assertEqual(services._backend_embeddings(), 'local')
        self.assertTrue(services.embeddings_configuradas())

    @override_settings(IA_EMBEDDING_BACKEND='openai', OPENAI_API_KEY='')
    def test_openai_exige_chave(self):
        self.assertFalse(services.embeddings_configuradas())

    @override_settings(IA_EMBEDDING_BACKEND='openai', OPENAI_API_KEY='sk-teste')
    def test_openai_com_chave(self):
        self.assertTrue(services.embeddings_configuradas())

    @override_settings(IA_EMBEDDING_BACKEND='voyage', VOYAGE_API_KEY='')
    def test_voyage_exige_chave(self):
        self.assertFalse(services.embeddings_configuradas())


class GeracaoConfigTest(TestCase):
    @override_settings(ANTHROPIC_API_KEY='')
    def test_sem_chave_nao_configurada(self):
        self.assertFalse(services.geracao_configurada())

    @override_settings(ANTHROPIC_API_KEY='sk-ant-teste')
    def test_com_chave_configurada(self):
        self.assertTrue(services.geracao_configurada())

    @override_settings(ANTHROPIC_API_KEY='')
    def test_cliente_anthropic_sem_chave_levanta(self):
        with self.assertRaises(services.IAIndisponivel):
            services._cliente_anthropic()


class ExtrairMarkdownTest(TestCase):
    def test_fallback_texto_simples(self):
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as fp:
            fp.write('conteúdo de teste')
            caminho = fp.name
        # Sem docling instalado, cai no fallback de leitura simples.
        self.assertIn('conteúdo de teste', services.extrair_markdown(caminho))


class AssistenteViewTest(TestCase):
    def setUp(self):
        User.objects.create_user('adv', password='x12345678')
        self.client.login(username='adv', password='x12345678')

    def test_get_renderiza(self):
        resp = self.client.get(reverse('assistente'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Assistente')

    @override_settings(ANTHROPIC_API_KEY='')
    def test_post_sem_chave_degrada(self):
        resp = self.client.post(reverse('assistente'), {'pergunta': 'Qual o prazo?'})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context['erro'])

    def test_post_vazio_pede_pergunta(self):
        resp = self.client.post(reverse('assistente'), {'pergunta': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('pergunta', resp.context['erro'].lower())
