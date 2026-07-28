from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('gestao', '0013_processocoletado')]

    operations = [
        migrations.AddField(
            model_name='prazo', name='termo_inicial',
            field=models.DateField(blank=True, null=True, verbose_name='Termo inicial'),
        ),
        migrations.AddField(
            model_name='prazo', name='regra_contagem',
            field=models.CharField(choices=[('MANUAL', 'Conferida manualmente'), ('UTEIS', 'Dias úteis (apoio)')], default='MANUAL', max_length=12, verbose_name='Regra de contagem'),
        ),
        migrations.AddField(
            model_name='prazo', name='feriados_considerados',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name='FeriadoForense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField()),
                ('descricao', models.CharField(max_length=255)),
                ('abrangencia', models.CharField(choices=[('NACIONAL', 'Nacional'), ('ESTADUAL_MA', 'Estado do Maranhão'), ('TRIBUNAL', 'Tribunal'), ('LOCAL', 'Comarca/local')], max_length=15)),
                ('tribunal', models.CharField(blank=True, max_length=80)),
                ('comarca', models.CharField(blank=True, max_length=120)),
                ('ativo', models.BooleanField(default=True)),
                ('fonte', models.URLField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Feriado forense', 'verbose_name_plural': 'Feriados forenses', 'ordering': ['data', 'abrangencia']},
        ),
        migrations.AddConstraint(
            model_name='feriadoforense',
            constraint=models.UniqueConstraint(fields=('data', 'descricao', 'abrangencia', 'tribunal', 'comarca'), name='feriado_forense_unico'),
        ),
    ]
