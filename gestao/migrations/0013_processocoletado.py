# Generated manually for the local JURI-AI deployment.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('gestao', '0012_prazo_avisos_enviados_prazo_confirmado_em'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessoColetado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fonte', models.CharField(choices=[('ELAW', 'eLaw Adv'), ('PJE_TRT16', 'PJe TRT16'), ('PJE_TJMA', 'PJe TJMA'), ('PJE_TRF1', 'PJe TRF1')], max_length=12)),
                ('numero', models.CharField(max_length=30)),
                ('tribunal', models.CharField(blank=True, max_length=80)),
                ('titulo', models.CharField(blank=True, max_length=500)),
                ('parte_autora', models.CharField(blank=True, max_length=500)),
                ('parte_re', models.CharField(blank=True, max_length=500)),
                ('data_referencia', models.DateField(blank=True, null=True)),
                ('dados', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('PENDENTE', 'Aguardando conferência'), ('VINCULADO', 'Vinculado a processo existente'), ('IMPORTADO', 'Importado'), ('IGNORADO', 'Ignorado')], default='PENDENTE', max_length=10)),
                ('coletado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('processo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coletas_externas', to='gestao.processo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='processos_coletados', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Processo coletado', 'verbose_name_plural': 'Processos coletados', 'ordering': ['-atualizado_em']},
        ),
        migrations.AddConstraint(
            model_name='processocoletado',
            constraint=models.UniqueConstraint(fields=('user', 'fonte', 'numero'), name='processo_coletado_usuario_fonte_numero_unico'),
        ),
    ]
