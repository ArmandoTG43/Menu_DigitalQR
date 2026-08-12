import qrcode
from io import BytesIO
from django.core.files import File
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class MayusculasMixin:
    
    campos_mayusculas = []  

    def save(self, *args, **kwargs):
        for campo in self.campos_mayusculas:
            valor = getattr(self, campo, None)
            if valor and isinstance(valor, str):
                setattr(self, campo, valor.upper())
        super().save(*args, **kwargs)

class Usuario(MayusculasMixin, AbstractUser):
    campos_mayusculas = ['username', 'first_name', 'last_name']  

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

class Categoria(MayusculasMixin, models.Model):
    campos_mayusculas = ['nombre']
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Producto(MayusculasMixin, models.Model):
    campos_mayusculas = ['nombre', 'descripcion']
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=6, decimal_places=2)
    imagen = models.ImageField(upload_to='productos/', null=True, blank=True)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name='productos'
    )
    tiene_ingredientes = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Mesa(models.Model):
    numero = models.IntegerField(unique=True)
    qr_codigo = models.ImageField(upload_to='qr/', null=True, blank=True)

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)

        if creating and not self.qr_codigo:
            from django.conf import settings
            base_url = getattr(
                settings,
                'BASE_URL',
                'https://menu-digitalqr.onrender.com'
            )
            url = f"{base_url}/menu/{self.id}/"
            qr = qrcode.make(url)
            buffer = BytesIO()
            qr.save(buffer, format='PNG')
            buffer.seek(0)
            file_name = f"mesa_{self.numero}.png"
            self.qr_codigo.save(
                file_name,
                File(buffer),
                save=False
            )
            super().save(update_fields=['qr_codigo'])

    def __str__(self):
        return f"Mesa {self.numero}"


class Pedido(MayusculasMixin, models.Model):
    campos_mayusculas = ['direccion_entrega', 'instrucciones_adicionales']

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

    # Campos para domicilio y personalización
    es_domicilio = models.BooleanField(default=False)
    direccion_entrega = models.CharField(max_length=300, blank=True, null=True)
    hora_entrega = models.TimeField(blank=True, null=True)
    es_personalizado = models.BooleanField(default=False)
    instrucciones_adicionales = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Pedido #{self.id} - Mesa {self.mesa.numero}"

    def calcular_total(self):
        total = sum(detalle.subtotal() for detalle in self.detalles.all())
        self.total = total
        self.save(update_fields=['total'])
        return total

    @property
    def total_calculado(self):
        return sum(detalle.subtotal() for detalle in self.detalles.all()) or 0.00

    def tiene_productos(self):
        return self.detalles.exists()

class DetallePedido(MayusculasMixin, models.Model):
    campos_mayusculas = ['ingredientes_texto']

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    ingredientes_texto = models.TextField(blank=True, null=True)

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        if not self.precio_unitario and self.producto:
            self.precio_unitario = self.producto.precio
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad} = ${self.subtotal():.2f}"

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
    monto = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    referencia = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Pago {self.id} - {self.metodo}"


class Promocion(MayusculasMixin, models.Model):
    campos_mayusculas = ['nombre', 'descripcion']

    TIPO_DESCUENTO = [
        ('porcentaje', 'Porcentaje (%)'),
        ('fijo', 'Monto Fijo ($)'),
    ]

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    tipo_descuento = models.CharField(max_length=20, choices=TIPO_DESCUENTO, default='porcentaje')
    valor_descuento = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activo = models.BooleanField(default=True)
    productos = models.ManyToManyField(Producto, related_name='promociones', blank=True)
    imagen = models.ImageField(upload_to='promociones/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def esta_vigente(self):
        from django.utils import timezone
        ahora = timezone.now()
        return self.activo and self.fecha_inicio <= ahora <= self.fecha_fin

    def precio_con_descuento(self, precio_original):
        if self.tipo_descuento == 'porcentaje':
            return precio_original - (precio_original * self.valor_descuento / 100)
        else:
            return precio_original - self.valor_descuento

class PedidoPersonalizado(MayusculasMixin, models.Model):
    campos_mayusculas = ['instrucciones', 'base', 'acompañamientos', 'salsas']

    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name='personalizado')
    instrucciones = models.TextField(blank=True, null=True)
    base = models.CharField(max_length=100, blank=True, null=True)
    acompañamientos = models.TextField(blank=True, null=True)
    salsas = models.TextField(blank=True, null=True)
    precio_extra = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Personalizado #{self.pedido.id}"

class Extra(MayusculasMixin, models.Model):
    campos_mayusculas = ['nombre']

    CATEGORIAS = [
        ('base', 'Base/Proteína'),
        ('acompañamiento', 'Acompañamiento'),
        ('salsa', 'Salsa'),
    ]

    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=6, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS)

    def __str__(self):
        return f"{self.nombre} (${self.precio})"


class Ingrediente(MayusculasMixin, models.Model):
    campos_mayusculas = ['nombre']

    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE, related_name='ingredientes')
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} (${self.precio})"