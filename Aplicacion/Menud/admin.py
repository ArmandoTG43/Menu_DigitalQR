from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Usuario, Categoria, Producto, Mesa, Pedido, Pago, DetallePedido, PerfilAdmin


# ==================== USUARIO CON ROLES ====================
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_rol_display', 'is_staff', 'is_active', 'fecha_registro')
    list_filter = ('rol', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_editable = ('is_active',)
    
    def get_rol_display(self, obj):
        colores = {
            'admin': '#dc3545',
            'cocinero': '#28a745',
            'cliente': '#007bff'
        }
        color = colores.get(obj.rol, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_rol_display()
        )
    get_rol_display.short_description = 'Rol'
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información del Rol', {
            'fields': ('rol', 'telefono', 'direccion', 'foto'),
            'classes': ('wide',)
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información del Rol', {
            'fields': ('rol', 'telefono', 'direccion'),
        }),
    )
    
    def fecha_registro(self, obj):
        return obj.date_joined.strftime('%d/%m/%Y %H:%M')
    fecha_registro.short_description = 'Registro'


# ==================== PERFIL ADMIN ====================
@admin.register(PerfilAdmin)
class PerfilAdminAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'telefono', 'direccion', 'fecha_creacion')
    search_fields = ('usuario__username', 'telefono')
    list_filter = ('fecha_creacion',)
    raw_id_fields = ('usuario',)


# ==================== CATEGORÍAS ====================
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'total_productos')
    search_fields = ('nombre',)
    ordering = ('nombre',)
    
    def total_productos(self, obj):
        return obj.productos.count()
    total_productos.short_description = 'Productos'
    
    fieldsets = (
        ('Información de Categoría', {
            'fields': ('nombre',)
        }),
    )


# ==================== PRODUCTOS ====================
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'precio', 'categoria', 'ver_imagen')
    list_filter = ('categoria',)
    search_fields = ('nombre', 'descripcion')
    list_editable = ('precio',)
    list_per_page = 20
    
    def ver_imagen(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 8px; object-fit: cover;" />', obj.imagen.url)
        return format_html('<span style="color: gray;">Sin imagen</span>')
    ver_imagen.short_description = 'Imagen'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'precio', 'categoria')
        }),
        ('Imagen del Producto', {
            'fields': ('imagen',),
            'classes': ('collapse',)
        }),
    )


# ==================== MESAS CON QR ====================
@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'ver_qr', 'pedidos_activos', 'ultimo_pedido')
    search_fields = ('numero',)
    list_per_page = 15
    readonly_fields = ('qr_codigo', 'ver_qr_grande')
    
    def ver_qr(self, obj):
        if obj.qr_codigo:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 5px;" />', obj.qr_codigo.url)
        return format_html('<span style="color: red;">No generado</span>')
    ver_qr.short_description = 'Código QR'
    
    def ver_qr_grande(self, obj):
        if obj.qr_codigo:
            return format_html('<img src="{}" width="200" height="200" style="border-radius: 10px;" /><br><small>Escanea para ver el menú</small>', obj.qr_codigo.url)
        return format_html('<span style="color: red;">QR no disponible</span>')
    ver_qr_grande.short_description = 'Vista previa del QR'
    
    def pedidos_activos(self, obj):
        pedidos = obj.pedidos.filter(estado__in=['pendiente', 'en_preparacion']).count()
        if pedidos > 0:
            return format_html('<span style="color: #ff9800;">{} pedido(s) activo(s)</span>', pedidos)
        return format_html('<span style="color: green;">Sin pedidos activos</span>')
    pedidos_activos.short_description = 'Estado'
    
    def ultimo_pedido(self, obj):
        ultimo = obj.pedidos.order_by('-fecha_hora').first()
        if ultimo:
            return ultimo.fecha_hora.strftime('%H:%M %d/%m')
        return 'Sin pedidos'
    ultimo_pedido.short_description = 'Último pedido'
    
    fieldsets = (
        ('Información de la Mesa', {
            'fields': ('numero',)
        }),
        ('Código QR', {
            'fields': ('ver_qr_grande', 'qr_codigo'),
            'description': 'Escanea este código QR desde tu celular para ver el menú'
        }),
    )


# ==================== DETALLE PEDIDO (Inline) ====================
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 1
    fields = ('producto', 'cantidad', 'subtotal')
    readonly_fields = ('subtotal',)
    
    def subtotal(self, obj):
        return f'${obj.producto.precio * obj.cantidad}'
    subtotal.short_description = 'Subtotal'


# ==================== PEDIDOS ====================
#  SOLO UNA VEZ - ELIMINA LA SEGUNDA DEFINICIÓN
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'mesa', 'estado_color', 'total_formateado', 'fecha_hora', 'tiempo_transcurrido_admin')
    list_filter = ('estado', 'fecha_hora')
    search_fields = ('mesa__numero', 'id')
    list_per_page = 25
    inlines = [DetallePedidoInline]
    readonly_fields = ('fecha_hora', 'total_formateado')
    
    def estado_color(self, obj):
        colores = {
            'pendiente': '#ff9800',
            'en_preparacion': '#2196f3',
            'listo': '#4caf50',
            'entregado': '#9e9e9e'
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_color.short_description = 'Estado'
    
    def total_formateado(self, obj):
        return f'${obj.total}'
    total_formateado.short_description = 'Total'
    
    def tiempo_transcurrido_admin(self, obj):
        from django.utils import timezone
        
        now = timezone.now()
        diff = now - obj.fecha_hora
        
        if diff.days > 0:
            return f'{diff.days} día(s)'
        elif diff.seconds < 3600:
            minutos = diff.seconds // 60
            return f'{minutos} minuto(s)'
        else:
            horas = diff.seconds // 3600
            return f'{horas} hora(s)'
    tiempo_transcurrido_admin.short_description = 'Tiempo transcurrido'
    
    actions = ['marcar_como_preparacion', 'marcar_como_listo', 'marcar_como_entregado']
    
    def marcar_como_preparacion(self, request, queryset):
        queryset.update(estado='en_preparacion')
        self.message_user(request, f'{queryset.count()} pedido(s) marcados como "En Preparación"')
    marcar_como_preparacion.short_description = 'Marcar como "En Preparación"'
    
    def marcar_como_listo(self, request, queryset):
        queryset.update(estado='listo')
        self.message_user(request, f'{queryset.count()} pedido(s) marcados como "Listo"')
    marcar_como_listo.short_description = 'Marcar como "Listo"'
    
    def marcar_como_entregado(self, request, queryset):
        queryset.update(estado='entregado')
        self.message_user(request, f'{queryset.count()} pedido(s) marcados como "Entregado"')
    marcar_como_entregado.short_description = 'Marcar como "Entregado"'
    
    fieldsets = (
        ('Información del Pedido', {
            'fields': ('mesa', 'estado', 'total_formateado')
        }),
        ('Fecha y Hora', {
            'fields': ('fecha_hora', 'tiempo_transcurrido_admin'),
            'classes': ('collapse',),
        }),
    )


# ==================== PAGOS ====================
@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido_info', 'monto_total', 'metodo', 'estado_color', 'fecha_formateada')
    list_filter = ('metodo', 'estado', 'fecha')
    search_fields = ('pedido__id', 'pedido__mesa__numero')
    readonly_fields = ('fecha',)
    
    def pedido_info(self, obj):
        return format_html(
            '<strong>Pedido #{}</strong><br><small>Mesa {}</small>',
            obj.pedido.id,
            obj.pedido.mesa.numero
        )
    pedido_info.short_description = 'Pedido'
    
    def monto_total(self, obj):
        return format_html('<span style="font-size: 14px; font-weight: bold; color: #2e7d32;">${}</span>', obj.pedido.total)
    monto_total.short_description = 'Monto'
    
    def estado_color(self, obj):
        colores = {
            'pendiente': '#ff9800',
            'aprobado': '#4caf50'
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_color.short_description = 'Estado'
    
    def fecha_formateada(self, obj):
        return obj.fecha.strftime('%d/%m/%Y %H:%M:%S')
    fecha_formateada.short_description = 'Fecha'
    
    actions = ['aprobar_pagos']
    
    def aprobar_pagos(self, request, queryset):
        queryset.update(estado='aprobado')
        self.message_user(request, f'{queryset.count()} pago(s) aprobado(s)')
    aprobar_pagos.short_description = 'Aprobar pagos seleccionados'


# ==================== CONFIGURACIÓN DEL SITIO ====================
admin.site.site_header = 'Freedom Lounge - Sistema de Gestión'
admin.site.site_title = 'Panel de Administración'
admin.site.index_title = 'Bienvenido al Sistema del Restaurante'