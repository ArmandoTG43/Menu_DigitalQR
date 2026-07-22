from datetime import datetime
from time import timezone
from django.utils import timezone
import stripe
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from .models import Categoria, PedidoPersonalizado, Producto, Mesa, Pedido, DetallePedido, Pago, Promocion
from .forms import ProductoForm
from django.http import JsonResponse
from django.conf import settings
from django.http import FileResponse
stripe.api_key = settings.STRIPE_SECRET_KEY
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import PerfilAdmin
from .forms import PerfilForm
from django.contrib.auth import get_user_model
User = get_user_model()
from functools import wraps
from django.contrib.auth.hashers import make_password
import json
import requests
from django.views.decorators.csrf import csrf_exempt
from .models import Usuario 

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.rol == 'admin':
            return view_func(request, *args, **kwargs)
        messages.error(request, "Acceso denegado. Solo administradores.")
        return redirect('login')
    return wrapper


@login_required
@admin_required
def lista_usuarios(request):
    usuarios = Usuario.objects.all().order_by('-date_joined')
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios})

@login_required
@admin_required
def crear_usuario(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        rol = request.POST.get('rol')
        
        if Usuario.objects.filter(username=username).exists():
            messages.error(request, "El usuario ya existe")
            return redirect('crear_usuario')
        
        usuario = Usuario.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            rol=rol
        )
        
        if rol == 'admin':
            usuario.is_staff = True
            usuario.is_superuser = True
            usuario.save()
        
        messages.success(request, f"Usuario {username} creado exitosamente")
        return redirect('lista_usuarios')
    
    return render(request, 'usuarios/crear.html')

@login_required
@admin_required
def editar_usuario(request, id):
    usuario = get_object_or_404(Usuario, id=id)
    
    if request.method == 'POST':
        usuario.username = request.POST.get('username')
        usuario.email = request.POST.get('email')
        nuevo_rol = request.POST.get('rol')
        
        if usuario.rol != nuevo_rol:
            usuario.rol = nuevo_rol
            if nuevo_rol == 'admin':
                usuario.is_staff = True
                usuario.is_superuser = True
            else:
                usuario.is_staff = False
                usuario.is_superuser = False
        
        password = request.POST.get('password')
        if password:
            usuario.password = make_password(password)
        
        usuario.save()
        messages.success(request, "Usuario actualizado correctamente")
        return redirect('lista_usuarios')
    
    return render(request, 'usuarios/editar.html', {'usuario': usuario})

@login_required
@admin_required
def eliminar_usuario(request, id):
    usuario = get_object_or_404(Usuario, id=id)
    
    if request.method == 'POST':
        if usuario == request.user:
            messages.error(request, "No puedes eliminarte a ti mismo")
            return redirect('lista_usuarios')
        usuario.delete()
        messages.success(request, "Usuario eliminado correctamente")
        return redirect('lista_usuarios')
    
    return render(request, 'usuarios/eliminar.html', {'usuario': usuario})

def admin_required(view_func):
    """Decorador para vistas solo de administrador"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get('cliente'):
            return redirect('menu')
        if request.user.is_authenticated and hasattr(request.user, 'rol') and request.user.rol == 'admin':
            return view_func(request, *args, **kwargs)
        return redirect('login')
    return wrapper

def cocinero_required(view_func):
    """Decorador para vistas solo de cocinero"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, 'rol') and request.user.rol == 'cocinero':
            return view_func(request, *args, **kwargs)
        return redirect('login')
    return wrapper

def cliente_required(view_func):
    """Decorador para vistas solo de clientes (QR)"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get('cliente'):
            return view_func(request, *args, **kwargs)
        return redirect('login')
    return wrapper


@login_required
def editar_perfil(request):
    perfil = PerfilAdmin.objects.get(usuario=request.user)

    if request.method == "POST":
        form = PerfilForm(request.POST, request.FILES, instance=perfil)

        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil editado')
            return redirect('perfil_admin')
    else:
        form = PerfilForm(instance=perfil)

    return render(request, 'editar_perfil.html', {
        'form': form,
        'perfil': perfil
    })

@login_required
def perfil_admin(request):
    perfil, created = PerfilAdmin.objects.get_or_create(usuario=request.user)
    return render(request, 'perfil_admin.html', {'perfil': perfil})

def home_unificado(request):
    
    # Si es cliente (viene de QR)
    if request.session.get('cliente'):
        mesa_id = request.session.get('mesa_id')
        return render(request, 'home.html', {
            'es_cliente': True,
            'mesa_id': mesa_id
        })
    # Si es admin
    return render(request, 'home.html', {
        'es_cliente': False
    })
def menu_unificado(request, mesa_id=None):
    # Caso 1: Es cliente (viene del QR o tiene sesión de cliente)
    if mesa_id or request.session.get('cliente'):
        if not mesa_id:
            mesa_id = request.session.get('mesa_id')
        
        if not mesa_id:
            messages.error(request, "No se identificó la mesa")
            return redirect('login')
        
        request.session['cliente'] = True
        request.session['mesa_id'] = mesa_id
        
        categorias = Categoria.objects.all()
        productos = Producto.objects.all()
        
        carrito = request.session.get('carrito', {})
        total_items = sum(item.get('cantidad', 0) for item in carrito.values())
        
        return render(request, 'menu.html', {
            'categorias': categorias,
            'productos': productos,
            'mesa_id': mesa_id,
            'total_items': total_items,  # 👈 ENVIAR AL TEMPLATE
        })
    
    # Caso 2: Administrador o cocinero
    else:
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.rol not in ['admin', 'cocinero']:
            return redirect('login')
        
        categoria_id = request.GET.get('categoria')
        productos = Producto.objects.all()
        if categoria_id:
            productos = productos.filter(categoria_id=categoria_id)
        categorias = Categoria.objects.all()
        
        #  TAMBIÉN ENVIAR total_items PARA ADMIN/COCINERO (si tienen carrito)
        carrito = request.session.get('carrito', {})
        total_items = sum(item.get('cantidad', 0) for item in carrito.values())
        
        return render(request, 'menu.html', {
            'productos': productos,
            'categorias': categorias,
            'total_items': total_items,  # 👈 TAMBIÉN AQUÍ
        })
    
@admin_required
def lista_mesas(request):
    if request.method == 'POST':
        numero = request.POST.get('numero')
        if numero:
            if not Mesa.objects.filter(numero=numero).exists():
                Mesa.objects.create(numero=numero)
        messages.success(request, 'Mesa creada correctamente')
        return redirect('lista_mesas')
    mesas = Mesa.objects.all()
    return render(request, 'mesas.html', {'mesas': mesas})

@admin_required
def eliminar_mesa(request, id):
    mesa = get_object_or_404(Mesa, id=id)
    mesa.delete()
    messages.success(request, 'Mesa eliminada correctamente')
    return redirect('lista_mesas')

@admin_required
def descargar_qr(request, id):
    mesa = get_object_or_404(Mesa, id=id)
    return FileResponse(mesa.qr_codigo.open(), as_attachment=True, filename=f"mesa_{mesa.numero}.png")

@login_required
def cocina(request):
    # Permitir admin y cocinero
    if request.user.rol not in ['admin', 'cocinero']:
        return redirect('login')
    pedidos = Pedido.objects.exclude(estado="entregado")
    return render(request, 'cocina.html', {
        'pedidos': pedidos,
        'es_admin': request.user.rol == 'admin'
    })

@cocinero_required  
def cambiar_estado(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if pedido.estado == "pendiente":
        pedido.estado = "en_preparacion"
    elif pedido.estado == "en_preparacion":
        pedido.estado = "listo"
    pedido.save()
    return redirect('cocina')

@cocinero_required
def entregar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    pedido.estado = "entregado"
    pedido.save()
    if request.session.get('pedido_id') == pedido.id:
        del request.session['pedido_id']
    return redirect('cocina')

@admin_required
def agregar_producto(request):
    form = ProductoForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Plato registrado correctamente')
        return redirect('menu')
    categorias = Categoria.objects.all()
    return render(request, 'producto_form.html', {
        'form': form,
        'categorias': categorias
    })

@admin_required
def editar_producto(request, id):
    producto = get_object_or_404(Producto, id=id)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if form.is_valid():
        form.save()
        messages.success(request, 'Plato editado correctamente')
        return redirect('menu')
    return render(request, 'producto_form.html', {'form': form})

@admin_required
def eliminar_producto(request, id):
    producto = get_object_or_404(Producto, id=id)
    if request.method == 'POST':
        producto.delete()
        messages.success(request, 'Plato eliminado correctamente')
        return redirect('menu')
    return render(request, 'confirmar_eliminar.html', {'producto': producto})

def contacto_unificado(request):
    """Contacto visible para admin y clientes"""
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        mensaje = request.POST.get('mensaje')
        # Procesar mensaje
        messages.success(request, 'Mensaje enviado correctamente')
        return redirect('contacto')
    
    # Si es cliente
    if request.session.get('cliente'):
        return render(request, 'contacto.html', {
            'es_cliente': True,
            'mesa_id': request.session.get('mesa_id')
        })
    
    # Si es admin
    return render(request, 'contacto.html', {
        'es_cliente': False
    })

@login_required
def api_pedidos(request):
    # Verificar autenticación
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    
    # Verificar rol (cocinero o admin)
    if request.user.rol not in ['cocinero', 'admin']:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    pedidos = Pedido.objects.all().order_by('-fecha_hora')
    data = []
    for p in pedidos:
        productos = []
        for d in p.detallepedido_set.all():
            productos.append({
                "nombre": d.producto.nombre,
                "cantidad": d.cantidad
            })
        data.append({
            "id": p.id,
            "mesa": p.mesa.numero,
            "estado": p.estado,
            "productos": productos,
            "total": float(p.total),
            "fecha_hora": p.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')
        })
    return JsonResponse(data, safe=False)

def api_pedido_detalle(request, pedido_id):
    """
    API pública para que el cliente vea su pedido.
    NO requiere autenticación.
    """
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        productos = []
        for d in pedido.detallepedido_set.all():
            productos.append({
                "nombre": d.producto.nombre,
                "cantidad": d.cantidad
            })
        data = {
            "id": pedido.id,
            "mesa": pedido.mesa.numero,
            "estado": pedido.estado,
            "productos": productos,
            "total": float(pedido.total),
            "fecha_hora": pedido.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')
        }
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def generar_comprobante(request, pedido_id):
    pedido = Pedido.objects.get(id=pedido_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}.pdf"'
    doc = SimpleDocTemplate(response)
    styles = getSampleStyleSheet()
    contenido = []
    contenido.append(Paragraph(f"Pedido #{pedido.id}", styles['Title']))
    contenido.append(Paragraph(f"Mesa: {pedido.mesa.numero}", styles['Normal']))
    contenido.append(Paragraph(f"Total: ${pedido.total}", styles['Normal']))
    contenido.append(Paragraph("Estado: Pagado", styles['Normal']))
    doc.build(contenido)
    return response


@cliente_required
def confirmar_pedido(request):
    carrito = request.session.get('carrito', {})
    mesa_id = request.session.get('mesa_id')
    
    if not carrito or not mesa_id:
        return redirect('menu')
    
    # Obtener datos del formulario
    tipo_entrega = request.POST.get('tipo_entrega', 'local')
    direccion = request.POST.get('direccion', '')
    hora_entrega = request.POST.get('hora_entrega', '')
    instrucciones_domicilio = request.POST.get('instrucciones_domicilio', '')
    
    es_personalizado = request.POST.get('es_personalizado') == '1'
    base_personalizado = request.POST.get('base_personalizado', '')
    acompanamientos = request.POST.get('acompanamientos', '')
    salsas_personalizado = request.POST.get('salsas_personalizado', '')
    instrucciones_personalizado = request.POST.get('instrucciones_personalizado', '')
    
    mesa = get_object_or_404(Mesa, id=mesa_id)
    
    pedido = Pedido.objects.create(
        mesa=mesa,
        es_domicilio=(tipo_entrega == 'domicilio'),
        direccion_entrega=direccion if tipo_entrega == 'domicilio' else '',
        hora_entrega=hora_entrega if tipo_entrega == 'domicilio' and hora_entrega else None,
        instrucciones_adicionales=instrucciones_domicilio if tipo_entrega == 'domicilio' else '',
        es_personalizado=es_personalizado
    )
    
    total = 0
    
    # 🔥 1. Agregar productos del carrito
    for id, item in carrito.items():
        producto = Producto.objects.get(id=id)
        DetallePedido.objects.create(
            pedido=pedido,
            producto=producto,
            cantidad=item['cantidad']
        )
        total += producto.precio * item['cantidad']
    
    # 🔥 2. Si es personalizado, agregar extras con precio
    if es_personalizado:
        precio_extra = 0
        
        # Precio de la base
        precios_base = {
            'Pollo': 6.00,
            'Carne': 7.00,
            'Cerdo': 6.50,
            'Pescado': 8.00,
            'Vegetariano': 5.00,
            'Mixto': 8.50,
        }
        base_seleccionada = base_personalizado
        if base_seleccionada in precios_base:
            precio_extra += precios_base[base_seleccionada]
        
        # Precio de acompañamientos (cada uno $2.00 extra)
        if acompanamientos:
            acompanamientos_list = request.POST.getlist('acompanamientos')
            precio_extra += len(acompanamientos_list) * 2.00
        
        # Precio de salsas (cada una $1.00 extra)
        if salsas_personalizado:
            salsas_list = request.POST.getlist('salsas_personalizado')
            precio_extra += len(salsas_list) * 1.00
        
        # Agregar el precio extra al total
        total += precio_extra
        
        # Guardar el detalle personalizado
        PedidoPersonalizado.objects.create(
            pedido=pedido,
            instrucciones=instrucciones_personalizado,
            base=base_personalizado,
            acompañamientos=acompanamientos,
            salsas=salsas_personalizado,
            precio_extra=precio_extra  # 🔥 Guardar el precio extra
        )
        
        # Agregar un item al carrito para que se vea en la cocina
        # Crear un producto virtual "Plato Personalizado"
        producto_personalizado, created = Producto.objects.get_or_create(
            nombre=f"🍽️ Plato Personalizado - {base_personalizado}",
            defaults={
                'descripcion': f"Base: {base_personalizado}, Acompañamientos: {acompanamientos}, Salsas: {salsas_personalizado}",
                'precio': precio_extra,
                'categoria': Categoria.objects.first() or Categoria.objects.create(nombre="Personalizados")
            }
        )
        
        DetallePedido.objects.create(
            pedido=pedido,
            producto=producto_personalizado,
            cantidad=1
        )
    
    pedido.total = total
    pedido.save()
    
    request.session['carrito'] = {}
    request.session['pedido_id'] = pedido.id
    
    return redirect('crear_pago', pedido_id=pedido.id)

@cliente_required
def agregar_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    producto = Producto.objects.get(id=producto_id)
    
    if str(producto_id) in carrito:
        carrito[str(producto_id)]['cantidad'] += 1
    else:
        carrito[str(producto_id)] = {
            'id': producto.id,
            'nombre': producto.nombre,
            'descripcion': producto.descripcion,
            'precio': float(producto.precio),
            'cantidad': 1,
            'imagen': producto.imagen.url if producto.imagen else ''
        }
    
    request.session['carrito'] = carrito
    
    # Si es petición AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        total_items = sum(item['cantidad'] for item in carrito.values())
        return JsonResponse({
            'success': True,
            'mensaje': f'{producto.nombre} agregado al carrito',
            'count': total_items
        })
    
    # Si no, redirigir normalmente
    messages.success(request, f' {producto.nombre} agregado al carrito')
    return redirect('menu')

@cliente_required
def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    productos = []
    total = 0
    for key, item in carrito.items():
        precio = item.get('precio', 0)
        cantidad = item.get('cantidad', 0)
        subtotal = precio * cantidad
        productos.append({
            'id': key,
            'nombre': item.get('nombre', ''),
            'descripcion': item.get('descripcion', ''),
            'cantidad': cantidad,
            'precio': precio,
            'subtotal': subtotal,
            'imagen': item.get('imagen', '')
        })
        total += subtotal
    return render(request, 'carrito.html', {
        'productos': productos,
        'total': total
    })

def carrito_contador(request):
    carrito = request.session.get('carrito', {})
    total_items = sum(item.get('cantidad', 0) for item in carrito.values())
    return {'total_items': total_items}

@cliente_required
def eliminar_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    if str(producto_id) in carrito:
        del carrito[str(producto_id)]
    request.session['carrito'] = carrito
    messages.success(request, 'Producto eliminado del carrito')
    return redirect('ver_carrito')

@cliente_required
def restar_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    if str(producto_id) in carrito:
        carrito[str(producto_id)]['cantidad'] -= 1
        if carrito[str(producto_id)]['cantidad'] <= 0:
            del carrito[str(producto_id)]
    request.session['carrito'] = carrito
    return redirect('ver_carrito')

@cliente_required
def crear_pago(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    # Solo mostramos la pantalla de pago (sin Stripe)
    return render(request, 'pago.html', {
        'pedido': pedido,
        'metodos': Pago.METODOS  # para mostrar opciones en el template
    })

@cliente_required
def confirmar_pago(request):
    if request.method == "POST":
        pedido_id = request.POST.get('pedido_id')
        metodo = request.POST.get('metodo', 'tarjeta')
        pedido = get_object_or_404(Pedido, id=pedido_id)

        # Crear el pago
        pago = Pago.objects.create(
            pedido=pedido,
            metodo=metodo,
            estado='aprobado',
            monto=pedido.total,
            referencia=f"SIM-{pedido.id}-{timezone.now().strftime('%Y%m%d%H%M')}"
        )


        return redirect('comprobante_pago', pago_id=pago.id)

    return redirect('ver_carrito')

@cliente_required
def comprobante_pago(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    return render(request, 'comprobante.html', {'pago': pago})

@cliente_required
def seguimiento_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    return render(request, 'seguimiento.html', {'pedido': pedido})


def registro(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        rol = request.POST.get('rol')  # Obtener el rol seleccionado
        
        # Validar que las contraseñas coincidan
        if password1 != password2:
            messages.error(request, "Las contraseñas no coinciden")
            return redirect('registro')
        
        # Validar que el usuario no exista
        if Usuario.objects.filter(username=username).exists():
            messages.error(request, "El usuario ya existe")
            return redirect('registro')
        
        # Validar que el email no exista
        if Usuario.objects.filter(email=email).exists():
            messages.error(request, "El correo ya está registrado")
            return redirect('registro')
        
        # Validar que el rol sea válido (solo admin o cocinero)
        if rol not in ['admin', 'cocinero']:
            messages.error(request, "Rol no válido")
            return redirect('registro')
        
        # Crear el usuario con el rol seleccionado
        user = Usuario.objects.create_user(
            username=username,
            email=email,
            password=password1,
            rol=rol  # Asignar el rol directamente
        )
        
        # Si es administrador, dar permisos de staff y superusuario
        if rol == 'admin':
            user.is_staff = True
            user.is_superuser = True
            user.save()
        
        # Mensaje según el rol
        if rol == 'admin':
            messages.success(request, "Cuenta de Administrador creada correctamente")
        else:
            messages.success(request, "Cuenta de Cocinero creada correctamente")
        
        return redirect('login')
    
    return render(request, 'registro.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            request.session.pop('cliente', None)
            
            # Redirigir según el rol
            if user.rol == 'admin':
                return redirect('home')
            elif user.rol == 'cocinero':
                return redirect('home')
            else:
                messages.info(request, "Los clientes deben usar el código QR de la mesa")
                return redirect('login')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('login')
    
def historial_por_fecha(request):
    """
    API para obtener pedidos entregados filtrados por fecha.
    GET ?fecha=YYYY-MM-DD
    Devuelve datos agrupados por mesa con productos sumados.
    """
    fecha_str = request.GET.get('fecha')
    if not fecha_str:
        return JsonResponse({'error': 'Se requiere parámetro fecha'}, status=400)
    
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}, status=400)
    
    # Obtener pedidos entregados en esa fecha
    pedidos = Pedido.objects.filter(
        estado='entregado',
        fecha_hora__date=fecha
    ).select_related('mesa').order_by('mesa__numero', 'fecha_hora')
    
    if not pedidos:
        return JsonResponse([], safe=False)
    
    # Agrupar por mesa
    mesas_dict = {}
    for pedido in pedidos:
        mesa_num = pedido.mesa.numero
        if mesa_num not in mesas_dict:
            mesas_dict[mesa_num] = {
                'productos': {},
                'total_mesa': 0.0,
                'pedidos_ids': []
            }
        
        mesas_dict[mesa_num]['pedidos_ids'].append(pedido.id)
        mesas_dict[mesa_num]['total_mesa'] += float(pedido.total)
        
        # Detalles del pedido
        detalles = DetallePedido.objects.filter(pedido=pedido).select_related('producto')
        for det in detalles:
            nombre = det.producto.nombre
            precio = float(getattr(det.producto, 'precio', 0.0))
            if nombre not in mesas_dict[mesa_num]['productos']:
                mesas_dict[mesa_num]['productos'][nombre] = {
                    'cantidad': 0,
                    'precio': precio
                }
            mesas_dict[mesa_num]['productos'][nombre]['cantidad'] += det.cantidad
    
    # Construir respuesta
    resultado = []
    for mesa_num, data in mesas_dict.items():
        productos_list = []
        for nombre, info in data['productos'].items():
            productos_list.append({
                'nombre': nombre,
                'cantidad': info['cantidad'],
                'precio': info['precio'],
                'subtotal': round(info['cantidad'] * info['precio'], 2)
            })
        productos_list.sort(key=lambda x: x['nombre'])
        
        resultado.append({
            'mesa': mesa_num,
            'productos': productos_list,
            'total_mesa': round(data['total_mesa'], 2),
            'pedidos_ids': data['pedidos_ids']
        })
    
    resultado.sort(key=lambda x: x['mesa'])
    return JsonResponse(resultado, safe=False)


@csrf_exempt
def chat_asistente(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mensaje = data.get('mensaje', '')

            if not mensaje:
                return JsonResponse({'respuesta': 'No escribiste nada. ¿En qué puedo ayudarte?'})

            mensaje_lower = mensaje.lower()
            respuesta = None

            # ========== 1. PREGUNTAS SOBRE EL SISTEMA EN GENERAL ==========
            if any(p in mensaje_lower for p in ['qué es', 'que es', 'sistema', 'plataforma', 'aplicación', 'app']):
                respuesta = " Freedom Lounge es un sistema web de menú virtual con códigos QR. Permite ver el menú, hacer pedidos, seguir su estado y pagar desde tu celular. ¡Todo sin esperar al mesero! 📱"

            elif any(p in mensaje_lower for p in ['cómo funciona', 'como funciona']):
                respuesta = " Escaneas el código QR de tu mesa, ves el menú, seleccionas tus platos, confirmas el pedido, haces seguimiento en tiempo real y pagas desde tu celular. ¡Fácil y rápido!"

            # ========== 2. PREGUNTAS SOBRE EL MENÚ ==========
            elif any(p in mensaje_lower for p in ['menú', 'carta', 'platos', 'comida', 'opciones']):
                if 'vegetariano' in mensaje_lower or 'vegano' in mensaje_lower:
                    respuesta = " Sí, tenemos opciones vegetarianas y veganas. Pregunta por nuestro menú especial del día."
                elif 'precio' in mensaje_lower or 'cuesta' in mensaje_lower or 'valor' in mensaje_lower:
                    respuesta = " Puedes ver todos los precios en el menú digital. Cada plato tiene su precio detallado. ¿Te ayudo con algún plato en particular?"
                elif 'recomienda' in mensaje_lower or 'sugiere' in mensaje_lower:
                    respuesta = " Te recomiendo probar nuestra Tapa Noruega  y los Nachos Freedom , son los más pedidos."
                elif 'infantil' in mensaje_lower or 'niño' in mensaje_lower or 'kids' in mensaje_lower:
                    respuesta = " El Menú Infantil cuesta $8.50 e incluye nuggets de pollo, papas fritas y un jugo "
                elif 'promociones' in mensaje_lower or 'descuento' in mensaje_lower or 'oferta' in mensaje_lower:
                    respuesta = " Hoy tenemos 2x1 en bebidas  y 15% de descuento en platos principales."
                elif 'más vendido' in mensaje_lower or 'top' in mensaje_lower:
                    respuesta = " Nuestro plato más vendido es la Tapa Noruega , seguido de los Nachos Freedom "
                else:
                    respuesta = " Puedes ver todo el menú digital con fotos, descripción y precios en la sección 'Menú'. ¿Quieres saber de algún plato en específico?"

            # ========== 3. PREGUNTAS SOBRE CÓDIGOS QR ==========
            elif any(p in mensaje_lower for p in ['qr', 'código', 'escanear', 'escaneas']):
                respuesta = "📷 Cada mesa tiene un código QR único. Solo escanéalo con la cámara de tu celular y accederás al menú digital automáticamente. ¡Sin apps adicionales!"

            # ========== 4. PREGUNTAS SOBRE PEDIDOS ==========
            elif any(p in mensaje_lower for p in ['pedido', 'orden', 'comanda']):
                if 'estado' in mensaje_lower or 'seguimiento' in mensaje_lower or 'tiempo' in mensaje_lower:
                    respuesta = " Puedes ver el estado de tu pedido en tiempo real: Recibido → En preparación → Listo → Entregado. ¡Siempre sabrás en qué etapa está!"
                elif 'cancelar' in mensaje_lower or 'anular' in mensaje_lower:
                    respuesta = " Si quieres cancelar tu pedido, por favor consulta directamente con nuestro personal de atención. Ellos te ayudarán."
                elif 'historial' in mensaje_lower:
                    respuesta = " Puedes ver el historial de tus pedidos en la sección 'Mi Pedido' o consultando con el administrador."
                else:
                    respuesta = " Para hacer un pedido: 1. Escanea el QR de tu mesa 2. Selecciona tus platos 3. Confirma el pedido. ¡Llega directo a cocina!"

            # ========== 5. PREGUNTAS SOBRE MESAS ==========
            elif any(p in mensaje_lower for p in ['mesa', 'mesas']):
                respuesta = "🪑 Cada mesa tiene su propio código QR. El administrador puede crear, modificar o eliminar mesas desde el panel de administración."

            # ========== 6. PREGUNTAS SOBRE PAGOS ==========
            elif any(p in mensaje_lower for p in ['pago', 'pagar', 'factura', 'comprobante', 'recibo']):
                if 'método' in mensaje_lower or 'como pagar' in mensaje_lower:
                    respuesta = " Puedes pagar con tarjeta de crédito/débito, transferencia bancaria o en efectivo en el local. ¡Tú eliges!"
                elif 'comprobante' in mensaje_lower:
                    respuesta = " Después de pagar, puedes descargar tu comprobante en PDF desde la sección de comprobante del pedido."
                else:
                    respuesta = " El pago se realiza desde tu celular después de confirmar el pedido. Puedes pagar con tarjeta o transferencia."

            # ========== 7. PREGUNTAS SOBRE REPORTES ==========
            elif any(p in mensaje_lower for p in ['reporte', 'ventas', 'estadísticas', 'gráfico']):
                respuesta = " El administrador puede ver reportes de ventas, productos más vendidos y exportarlos a Excel o PDF en la sección 'Reportes'."

            # ========== 8. PREGUNTAS SOBRE COCINA ==========
            elif any(p in mensaje_lower for p in ['cocina', 'cocinero', 'preparación']):
                respuesta = " En la cocina se ven los pedidos en tiempo real. El cocinero puede cambiar el estado: pendiente → en preparación → listo → entregado."

            # ========== 9. PREGUNTAS SOBRE USUARIOS ==========
            elif any(p in mensaje_lower for p in ['usuario', 'login', 'contraseña', 'cuenta']):
                if 'recuperar' in mensaje_lower or 'olvidé' in mensaje_lower:
                    respuesta = " Si olvidaste tu contraseña, usa la opción 'Recuperar contraseña' en el login. Te enviaremos instrucciones a tu correo."
                else:
                    respuesta = " Solo el administrador puede crear y gestionar usuarios. Los roles disponibles son: Administrador, Cocinero y Cliente (via QR)."

            # ========== 10. PREGUNTAS SOBRE HORARIOS ==========
            elif any(p in mensaje_lower for p in ['horario', 'horas', 'abierto', 'cierran']):
                respuesta = " Atendemos de lunes a domingo de 12:00 a 22:00 horas. ¡Te esperamos!"

            # ========== 11. PREGUNTAS SOBRE CONTACTO ==========
            elif any(p in mensaje_lower for p in ['contacto', 'dirección', 'ubicación', 'teléfono', 'llamar']):
                respuesta = " Estamos en Latacunga, Ecuador. Puedes contactarnos a través de la sección 'Contactos' en el menú principal."

            # ========== 12. PREGUNTAS SOBRE EL ASISTENTE ==========
            elif any(p in mensaje_lower for p in ['quién eres', 'que eres', 'asistente', 'bot']):
                respuesta = " Soy el asistente virtual de Freedom Lounge. Estoy aquí para ayudarte con el menú, pedidos, pagos y cualquier duda sobre el sistema. ¡Pregúntame lo que quieras!"

            # ========== 13. SALUDOS ==========
            elif any(p in mensaje_lower for p in ['hola', 'buenos días', 'buenas tardes', 'buenas noches', 'hey']):
                respuesta = "¡Hola! 👋 ¿Cómo estás? ¿En qué puedo ayudarte hoy?"

            # ========== 14. SI NO ENCUENTRA COINCIDENCIA ==========
            if respuesta is None:
                respuesta = " No estoy seguro de entender tu pregunta. ¿Puedes ser más específico? Estoy aquí para ayudarte con el menú, pedidos, mesas, pagos y más."

            if respuesta is None:
                try:
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}'
                    }

                    payload = {
                        'model': 'deepseek-chat',
                        'messages': [
                            {'role': 'system', 'content': (
                                'Eres un asistente virtual del restaurante Freedom Lounge Latacunga. '
                                'Responde preguntas sobre el sistema: menú digital, códigos QR, pedidos, '
                                'seguimiento, pagos, mesas, reportes, cocina y usuarios. Sé amable y breve.'
                            )},
                            {'role': 'user', 'content': mensaje}
                        ],
                        'max_tokens': 300,
                        'temperature': 0.7
                    }

                    response = requests.post(
                        settings.DEEPSEEK_API_URL,
                        headers=headers,
                        json=payload,
                        timeout=8
                    )

                    if response.status_code == 200:
                        respuesta_api = response.json()
                        contenido = respuesta_api['choices'][0]['message']['content']
                        return JsonResponse({'respuesta': contenido})

                except Exception as e:
                    # Si falla, usamos la respuesta del fallback
                    pass

            if respuesta:
                return JsonResponse({'respuesta': respuesta})
            else:
                return JsonResponse({
                    'respuesta': ' Lo siento, no encontré información sobre eso. Por favor, consulta directamente con nuestro personal, ellos te atenderán con gusto.'
                })

        except Exception as e:
            return JsonResponse({
                'respuesta': ' Ocurrió un error inesperado. Por favor, intenta de nuevo más tarde.'
            })

    return JsonResponse({'error': 'Método no permitido'}, status=405)



@admin_required
def lista_promociones(request):
    promociones = Promocion.objects.all().order_by('-created_at')
    return render(request, 'promociones/lista.html', {'promociones': promociones})

@admin_required
def crear_promocion(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        tipo_descuento = request.POST.get('tipo_descuento')
        valor_descuento = request.POST.get('valor_descuento')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        productos_ids = request.POST.getlist('productos')
        
        promocion = Promocion.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            tipo_descuento=tipo_descuento,
            valor_descuento=valor_descuento,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            activo=True
        )
        promocion.productos.set(productos_ids)
        
        messages.success(request, 'Promoción creada exitosamente')
        return redirect('lista_promociones')
    
    productos = Producto.objects.all()
    return render(request, 'promociones/crear.html', {'productos': productos})

@admin_required
def editar_promocion(request, id):
    promocion = get_object_or_404(Promocion, id=id)
    if request.method == 'POST':
        promocion.nombre = request.POST.get('nombre')
        promocion.descripcion = request.POST.get('descripcion')
        promocion.tipo_descuento = request.POST.get('tipo_descuento')
        promocion.valor_descuento = request.POST.get('valor_descuento')
        promocion.fecha_inicio = request.POST.get('fecha_inicio')
        promocion.fecha_fin = request.POST.get('fecha_fin')
        promocion.activo = request.POST.get('activo') == 'on'
        promocion.productos.set(request.POST.getlist('productos'))
        promocion.save()
        
        messages.success(request, 'Promoción actualizada')
        return redirect('lista_promociones')
    
    productos = Producto.objects.all()
    return render(request, 'promociones/editar.html', {
        'promocion': promocion,
        'productos': productos
    })

@admin_required
@admin_required
def eliminar_promocion(request, id):
    promocion = get_object_or_404(Promocion, id=id)
    if request.method == 'POST':
        promocion.delete()
        messages.success(request, 'Promoción eliminada')
        return redirect('lista_promociones')
    # Si es GET, también elimina (para que funcione con el enlace directo)
    promocion.delete()
    messages.success(request, 'Promoción eliminada')
    return redirect('lista_promociones')


def promociones_cliente(request):
    ahora = timezone.now()
    promociones = Promocion.objects.filter(
        activo=True,
        fecha_inicio__lte=ahora,
        fecha_fin__gte=ahora
    )
    return render(request, 'promociones/cliente.html', {'promociones': promociones})

# views.py - Agrega esta función

@cliente_required
def pedido_personalizado(request):
    if request.method == 'POST':
        carrito = request.session.get('carrito', {})
        mesa_id = request.session.get('mesa_id')
        
        if not carrito or not mesa_id:
            messages.error(request, 'No hay productos en el carrito')
            return redirect('menu')
        
        # Obtener datos del formulario
        instrucciones = request.POST.get('instrucciones', '')
        base = request.POST.get('base', '')
        acompañamientos = request.POST.get('acompañamientos', '')
        salsas = request.POST.get('salsas', '')
        
        mesa = get_object_or_404(Mesa, id=mesa_id)
        pedido = Pedido.objects.create(
            mesa=mesa,
            es_personalizado=True,
            instrucciones_adicionales=instrucciones
        )
        
        # Agregar productos al pedido
        total = 0
        for id, item in carrito.items():
            producto = Producto.objects.get(id=id)
            DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=item['cantidad']
            )
            total += producto.precio * item['cantidad']
        
        # Crear el detalle personalizado
        PedidoPersonalizado.objects.create(
            pedido=pedido,
            instrucciones=instrucciones,
            base=base,
            acompañamientos=acompañamientos,
            salsas=salsas
        )
        
        pedido.total = total
        pedido.save()
        
        request.session['carrito'] = {}
        request.session['pedido_id'] = pedido.id
        
        messages.success(request, '¡Pedido personalizado creado!')
        return redirect('crear_pago', pedido_id=pedido.id)
    
    return render(request, 'pedido_personalizado.html')