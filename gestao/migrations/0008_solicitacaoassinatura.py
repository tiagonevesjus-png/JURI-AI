# Generated manually for the JURI-AI assisted signing workflow.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('gestao', '0007_rename_gestao_noti_user_id_93fcdc_idx_gestao_noti_user_id_b522c9_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitacaoAssinatura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('finalidade', models.CharField(max_length=255)),
                ('arquivo_original', models.FileField(upload_to='assinaturas/originais/%Y/%m/%d/')),
                ('arquivo_p7s', models.FileField(blank=True, upload_to='assinaturas/p7s/%Y/%m/%d/')),
                ('hash_original', models.CharField(editable=False, max_length=64)),
                ('hash_p7s', models.CharField(blank=True, editable=False, max_length=64)),
                ('status', models.CharField(choices=[('PENDENTE', 'Aguardando assinatura'), ('EM_ASSINATURA', 'Em assinatura'), ('ASSINADO', 'Assinado e validado'), ('FALHOU', 'Validação falhou'), ('CANCELADO', 'Cancelado')], default='PENDENTE', max_length=16)),
                ('certificado_subject', models.TextField(blank=True)),
                ('certificado_issuer', models.TextField(blank=True)),
                ('validacao', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('concluido_em', models.DateTimeField(blank=True, null=True)),
                ('processo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitacoes_assinatura', to='gestao.processo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitacoes_assinatura', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Solicitação de assinatura',
                'verbose_name_plural': 'Solicitações de assinatura',
                'ordering': ['-criado_em'],
            },
        ),
    ]
