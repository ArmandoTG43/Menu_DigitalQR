import qrcode
from io import BytesIO
from django.core.files import File
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

# -------------------
# USUARIO
# -------------------
class Usuario(AbstractUser):
    ROLES = [
        ('admin', 'Administrador'),
        ('cocinero', 'Cocinero'),
        ('Cliente', 'Cliente'),
    ]

    rol = models.CharField(max_length=20, choices=ROLES, default='Cliente')

    def __str__(self):
        return self.username

class PerfilAdmin(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    foto = models.ImageField(upload_to='perfiles/', null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    direccion = models.CharField(max_length=150, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Perfil de {self.usuario.username}"
# -------------------
# Menud
# -------------------

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=6, decimal_places=2)
    imagen = models.ImageField(upload_to='productos/', null=True, blank=True)


    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name='productos'
    )

    def __str__(self):
        return self.nombre
    


class Mesa(models.Model):
    numero = models.IntegerField(unique=True)
    qr_codigo = models.ImageField(upload_to='qr/', null=True, blank=True)

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        
        if creating and not self.qr_codigo:
            # 👇 CAMBIA ESTO - Usa la URL de ngrok
            # Si quieres que funcione con cualquier URL dinámicamente:
            from django.conf import settings
            base_url = getattr(settings, 'BASE_URL', 'https://ammonium-sliceable-sizzle.ngrok-free.dev')
            url = f"{base_url}/menu/{self.id}/"
            
            qr = qrcode.make(url)
            buffer = BytesIO()
            qr.save(buffer, format='PNG')
            file_name = f"mesa_{self.numero}.png"
            self.qr_codigo.save(file_name, File(buffer), save=False)
            super().save(update_fields=['qr_codigo'])

# -------------------
# PEDIDO
# -------------------
class Pedido(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_preparacion', 'En Preparación'),
        ('listo', 'Listo'),
        ('entregado', 'Entregado'),
    ]

    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='pedidos')
    productos = models.ManyToManyField(Producto, through='DetallePedido')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    total = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pedido {self.id} - Mesa {self.mesa.numero}"
    
# -------------------
# PAGO
# -------------------

class Pago(models.Model):
    METODOS = [
        ('tarjeta', 'Tarjeta'),
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE)
    metodo = models.CharField(max_length=20, choices=METODOS)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha = models.DateTimeField(auto_now_add=True)
    
    #  NUEVOS CAMPOS
    monto = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    referencia = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Pago {self.id} - {self.metodo}"

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)



    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad}"