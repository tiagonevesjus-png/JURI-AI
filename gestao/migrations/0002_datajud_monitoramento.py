from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('gestao', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='processo', name='datajud_alias',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='processo', name='ultima_sincronizacao_datajud',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='movimentacaoprocesso', name='codigo_tpu',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='movimentacaoprocesso', name='data_hora',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='movimentacaoprocesso', name='fonte',
            field=models.CharField(default='MANUAL', max_length=20),
        ),
        migrations.AddField(
            model_name='movimentacaoprocesso', name='referencia_externa',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
