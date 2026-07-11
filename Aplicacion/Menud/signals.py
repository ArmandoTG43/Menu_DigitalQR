from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Usuario, PerfilAdmin

@receiver(post_save, sender=Usuario)
def crear_perfil_admin(sender, instance, created, **kwargs):
    if created:
        PerfilAdmin.objects.create(usuario=instance)