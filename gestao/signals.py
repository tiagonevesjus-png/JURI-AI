"""Cria automaticamente um Perfil sempre que um usuário é criado."""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Perfil


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_perfil(sender, instance, created, **kwargs):
    if created:
        cargo = 'ADMIN' if instance.is_superuser else 'ADVOGADO'
        Perfil.objects.get_or_create(user=instance, defaults={'cargo': cargo})
