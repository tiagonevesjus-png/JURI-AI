from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('gestao', '0004_item_google')]

    operations = [
        migrations.CreateModel(
            name='Notificacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('DJEN', 'Publicação DJEN'), ('GMAIL', 'Gmail'), ('AGENDA', 'Google Agenda'), ('PRAZO', 'Prazo'), ('AUDIENCIA', 'Audiência'), ('SISTEMA', 'Sistema')], default='SISTEMA', max_length=12)),
                ('prioridade', models.CharField(choices=[('BAIXA', 'Baixa'), ('NORMAL', 'Normal'), ('ALTA', 'Alta'), ('URGENTE', 'Urgente')], default='NORMAL', max_length=10)),
                ('titulo', models.CharField(max_length=255)), ('mensagem', models.TextField(blank=True)), ('link', models.URLField(blank=True)),
                ('dados', models.JSONField(blank=True, default=dict)), ('lida_em', models.DateTimeField(blank=True, null=True)),
                ('entregas', models.JSONField(blank=True, default=dict)), ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='notificacoes', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-criado_em']},
        ),
        migrations.AddIndex(model_name='notificacao', index=models.Index(fields=['user', 'lida_em', '-criado_em'], name='gestao_noti_user_id_93fcdc_idx')),
    ]
