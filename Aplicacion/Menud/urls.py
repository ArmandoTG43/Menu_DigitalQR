from django.urls import path
from django.contrib.auth import views as auth_views
from Aplicacion.Menud import reportes
from . import views
from django.urls import reverse_lazy


urlpatterns = [

    #  AUTENTICACIÓN
    path('', views.login_view, name='login'),          # página principal = login
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    #  REGISTRO
    path('registro/', views.registro, name='registro'),

    #  HOME
    path('home/', views.home_unificado, name='home'),

    #  MENÚ - UNA SOLA VISTA PARA AMBOS ROLES
    path('menu/', views.menu_unificado, name='menu'),           # Para admin
    path('menu/<int:mesa_id>/', views.menu_unificado, name='menu_cliente'),  # Para cliente QR

    #  CARRITO
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_carrito, name='agregar_carrito'),
    path('carrito/eliminar/<int:producto_id>/', views.eliminar_carrito, name='eliminar_carrito'),
    path('carrito/restar/<int:producto_id>/', views.restar_carrito, name='restar_carrito'),

    #  PEDIDO
    path('confirmar/', views.confirmar_pedido, name='confirmar_pedido'),

    #  PRODUCTOS
    path('producto/agregar/', views.agregar_producto, name='agregar_producto'),
    path('producto/editar/<int:id>/', views.editar_producto, name='editar_producto'),
    path('producto/eliminar/<int:id>/', views.eliminar_producto, name='eliminar_producto'),

    #  PAGOS
    path('pago/<int:pedido_id>/', views.crear_pago, name='pago'),
    path('crear-pago/<int:pedido_id>/', views.crear_pago, name='crear_pago'),
    path('confirmar_pago/', views.confirmar_pago, name='confirmar_pago'),
    path('comprobante/<int:pedido_id>/', views.generar_comprobante, name='comprobante'),
    path('comprobante/<int:pago_id>/', views.comprobante_pago, name='comprobante_pago'),
    path('comprobante-pdf/<int:pedido_id>/', views.generar_comprobante, name='comprobante_pdf'),
    path('comprobante/<int:pago_id>/', views.comprobante_pago, name='comprobante_pago'),

    

    #  MESAS
    path('mesas/', views.lista_mesas, name='lista_mesas'),
    path('mesa/eliminar/<int:id>/', views.eliminar_mesa, name='eliminar_mesa'),
    path('mesa/qr/<int:id>/', views.descargar_qr, name='descargar_qr'),

    #  COCINA
    path('cocina/', views.cocina, name='cocina'),
    path('cocina/estado/<int:pedido_id>/', views.cambiar_estado, name='cambiar_estado'),
    path('entregar/<int:pedido_id>/', views.entregar_pedido, name='entregar_pedido'),
    path('api/pedidos/', views.api_pedidos, name='api_pedidos'),
    path('api/historial/', views.historial_por_fecha, name='historial_por_fecha'),  # <-- NUEVA
    path('seguimiento/<int:pedido_id>/', views.seguimiento_pedido, name='seguimiento_pedido'),
    #  RECUPERACIÓN DE CONTRASEÑA
    path('reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        html_email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done')
    ), name='password_reset'),

    path('reset_done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete')
    ), name='password_reset_confirm'),

    path('reset_complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),

    #  PERFIL
    path('perfil-admin/', views.perfil_admin, name='perfil_admin'),
    path('editar-perfil/', views.editar_perfil, name='editar_perfil'),
    
    #  REPORTES
    path('dashboard/', reportes.dashboard_ventas, name='dashboard'),
    path('reportes/excel/', reportes.reporte_ventas_excel, name='reporte_ventas_excel'),
    path('reportes/pdf/', reportes.reporte_ventas_pdf, name='reporte_ventas_pdf'),

    #  CONTACTO
    path('contacto/', views.contacto_unificado, name='contacto'),

    # urls.py
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:id>/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:id>/', views.eliminar_usuario, name='eliminar_usuario'),

    path('chat/asistente/', views.chat_asistente, name='chat_asistente'),

    path('api/pedido/<int:pedido_id>/', views.api_pedido_detalle, name='api_pedido_detalle'),

    path('promociones/', views.lista_promociones, name='lista_promociones'),
    path('promociones/crear/', views.crear_promocion, name='crear_promocion'),
    path('promociones/editar/<int:id>/', views.editar_promocion, name='editar_promocion'),
    path('promociones/eliminar/<int:id>/', views.eliminar_promocion, name='eliminar_promocion'),
    path('promociones/cliente/', views.promociones_cliente, name='promociones_cliente'),

    path('resetear/', views.resetear_productos, name='resetear_productos'),
    # PLATO PERSONALIZADO
    path('agregar-promocion/<int:promo_id>/', views.agregar_promocion_carrito, name='agregar_promocion_carrito'),
    path('validar-email/', views.validar_email, name='validar_email'),
    path('validar-email-editar/', views.validar_email_editar, name='validar_email_editar'),


    path('personalizar/', views.personalizar_pedido, name='personalizar_pedido'),
    path('confirmar-pedido/', views.confirmar_pedido, name='confirmar_pedido'),
]