"""Unifica dados de uma conta local duplicada em outra conta local.

Uso restrito à administração local. O comando opera em transação e preserva
clientes, processos, integrações e assinaturas. A conta de origem pode ser
desativada ao final para evitar que o painel pareça vazio por novo login nela.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from usuarios.models import Cliente
from gestao.models import (
    ArquivoGoogleDrive, Audiencia, Compromisso, ItemGoogle, LancamentoFinanceiro,
    Notificacao, Perfil, Prazo, Processo, PublicacaoDJEN, PushSubscription,
    SolicitacaoAssinatura, Tarefa, TriagemJuridica,
)


class Command(BaseCommand):
    help = 'Move todos os dados de uma conta local para outra, sem duplicar registros.'

    def add_arguments(self, parser):
        parser.add_argument('--origem', required=True)
        parser.add_argument('--destino', required=True)
        parser.add_argument('--desativar-origem', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        try:
            origem = User.objects.select_for_update().get(username=options['origem'])
            destino = User.objects.select_for_update().get(username=options['destino'])
        except User.DoesNotExist as exc:
            raise CommandError('Conta local de origem ou destino não encontrada.') from exc
        if origem.pk == destino.pk:
            raise CommandError('Origem e destino devem ser contas diferentes.')

        modelos = [
            Cliente, Processo, PublicacaoDJEN, ItemGoogle, ArquivoGoogleDrive,
            Notificacao, TriagemJuridica, PushSubscription, SolicitacaoAssinatura,
            Audiencia, Prazo, Tarefa, Compromisso, LancamentoFinanceiro,
        ]
        movidos = {}
        for modelo in modelos:
            quantidade = modelo.objects.filter(user=origem).update(user=destino)
            movidos[modelo._meta.verbose_name_plural] = quantidade

        # Campos de responsável também devem apontar para a conta canônica.
        Processo.objects.filter(responsavel=origem).update(responsavel=destino)
        Audiencia.objects.filter(responsavel=origem).update(responsavel=destino)
        Prazo.objects.filter(responsavel=origem).update(responsavel=destino)
        Tarefa.objects.filter(responsavel=origem).update(responsavel=destino)

        perfil_origem = Perfil.objects.filter(user=origem).first()
        perfil_destino, _ = Perfil.objects.get_or_create(user=destino)
        if perfil_origem:
            perfil_destino.nome_completo = perfil_origem.nome_completo or perfil_destino.nome_completo
            perfil_destino.oab = perfil_origem.oab or perfil_destino.oab
            perfil_destino.telefone = perfil_origem.telefone or perfil_destino.telefone
            perfil_origem.delete()
        perfil_destino.cargo = 'ADMIN'
        perfil_destino.ativo = True
        perfil_destino.save()

        destino.email = origem.email or destino.email
        destino.is_staff = True
        destino.is_superuser = True
        destino.is_active = True
        destino.save(update_fields=['email', 'is_staff', 'is_superuser', 'is_active'])

        if options['desativar_origem']:
            origem.is_active = False
            origem.save(update_fields=['is_active'])

        total = sum(movidos.values())
        detalhe = ', '.join(f'{nome}: {qtd}' for nome, qtd in movidos.items() if qtd)
        self.stdout.write(self.style.SUCCESS(
            f'Conta unificada: {total} registro(s) movido(s). {detalhe or "Nenhum registro pendente"}.'
        ))
