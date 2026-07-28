from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('gestao', '0002_datajud_monitoramento')]

    operations = [
        migrations.CreateModel(
            name='PublicacaoDJEN',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identificador_externo', models.CharField(max_length=100)),
                ('numero_processo', models.CharField(blank=True, max_length=30)),
                ('data_disponibilizacao', models.DateField(blank=True, null=True)),
                ('tribunal', models.CharField(blank=True, max_length=30)),
                ('tipo_comunicacao', models.CharField(blank=True, max_length=100)),
                ('orgao', models.CharField(blank=True, max_length=255)),
                ('texto', models.TextField(blank=True)),
                ('link', models.URLField(blank=True)),
                ('dados', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('processo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='publicacoes_djen', to='gestao.processo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='publicacoes_djen', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Publicação DJEN', 'verbose_name_plural': 'Publicações DJEN', 'ordering': ['-data_disponibilizacao', '-criado_em']},
        ),
        migrations.AddConstraint(
            model_name='publicacaodjen',
            constraint=models.UniqueConstraint(fields=('user', 'identificador_externo'), name='publicacao_djen_usuario_identificador_unico'),
        ),
    ]
