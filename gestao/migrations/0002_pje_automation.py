from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="processo",
            name="monitorar_pje",
            field=models.BooleanField(
                default=True,
                help_text="Sincronizar automaticamente as movimentações pela API do DataJud.",
                verbose_name="Monitorar no PJe (DataJud)",
            ),
        ),
        migrations.AddField(
            model_name="processo",
            name="pje_sincronizado_em",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Última sincronização (PJe)"
            ),
        ),
        migrations.AddField(
            model_name="movimentacaoprocesso",
            name="origem",
            field=models.CharField(
                choices=[("MANUAL", "Registro manual"), ("PJE", "PJe / DataJud")],
                default="MANUAL",
                max_length=6,
            ),
        ),
        migrations.AddField(
            model_name="movimentacaoprocesso",
            name="codigo_movimento",
            field=models.CharField(
                blank=True, max_length=20, verbose_name="Código (DataJud)"
            ),
        ),
    ]
