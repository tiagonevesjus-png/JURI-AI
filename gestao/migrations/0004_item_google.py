from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('gestao', '0003_publicacao_djen'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemGoogle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fonte', models.CharField(choices=[('GMAIL', 'Gmail'), ('AGENDA', 'Google Agenda')], max_length=10)),
                ('identificador_externo', models.CharField(max_length=255)),
                ('titulo', models.CharField(max_length=500)),
                ('ocorrido_em', models.DateTimeField(blank=True, null=True)),
                ('link', models.URLField(blank=True)),
                ('resumo', models.TextField(blank=True)),
                ('dados', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='itens_google', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Item Google', 'verbose_name_plural': 'Itens Google', 'ordering': ['-ocorrido_em', '-atualizado_em']},
        ),
        migrations.AddConstraint(
            model_name='itemgoogle',
            constraint=models.UniqueConstraint(fields=('user', 'fonte', 'identificador_externo'), name='item_google_usuario_fonte_identificador_unico'),
        ),
    ]
