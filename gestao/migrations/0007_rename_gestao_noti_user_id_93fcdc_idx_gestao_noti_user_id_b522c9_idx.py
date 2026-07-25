from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('gestao', '0006_pushsubscription')]

    operations = [
        migrations.RenameIndex(
            model_name='notificacao',
            new_name='gestao_noti_user_id_b522c9_idx',
            old_name='gestao_noti_user_id_93fcdc_idx',
        ),
    ]
