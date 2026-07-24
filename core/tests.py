from django.test import TestCase
from django.urls import reverse


class HealthCheckTest(TestCase):
    def test_healthz_confirma_aplicacao_e_banco(self):
        response = self.client.get(reverse('healthz'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'ok'})
