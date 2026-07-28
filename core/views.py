from django.db import connections
from django.http import JsonResponse


def healthz(request):
    """Verifica se a aplicacao e o banco de dados estao acessiveis."""
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'indisponivel', 'database': 'indisponivel'}, status=503)
    return JsonResponse({'status': 'ok', 'database': 'ok'})
