from datetime import datetime
from time import timezone
from django.utils import timezone
import stripe
from django.db import connection
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
        anterior_mesa = request.session.get('mesa_id')
        
        if mesa_id:
            # Si escanea un QR de otra mesa, vaciar el carrito sin confirmar de la mesa anterior
            if anterior_mesa and str(anterior_mesa) != str(mesa_id):
                request.session['carrito'] = {}
                request.session.modified = True
            request.session['mesa_id'] = mesa_id
        else:
            mesa_id = anterior_mesa
        
        if not mesa_id:
            messages.error(request, "No se identificó la mesa")
            return redirect('login')
        
        request.session['cliente'] = True
        
        categorias = Categoria.objects.all()
        productos = Producto.objects.all()
        
        carrito = request.session.get('carrito', {})
        total_items = sum(item.get('cantidad', 0) for item in carrito.values())
        
        return render(request, 'menu.html', {
            'categorias': categorias,
            'productos': productos,
            'mesa_id': mesa_id,
            'total_items': total_items,
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
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    
    if request.user.rol not in ['cocinero', 'admin']:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        # Obtener pedidos NO entregados
        pedidos = Pedido.objects.exclude(estado='entregado').order_by('-fecha_hora')
        
        data = []
        for p in pedidos:
            productos = []
            
            # Obtener detalles del pedido
            detalles = DetallePedido.objects.filter(pedido=p)
            for d in detalles:
                try:
                    # Verificar que el producto existe
                    if d.producto:
                        precio_unit = float(d.producto.precio) if d.producto.precio else 0
                        productos.append({
                            "nombre": d.producto.nombre or "Producto sin nombre",
                            "descripcion": d.producto.descripcion or "",
                            "cantidad": d.cantidad or 1,
                            "precio": precio_unit,
                            "subtotal": round(precio_unit * (d.cantidad or 1), 2)
                        })
                except Exception as e:
                    print(f"Error en detalle {d.id}: {e}")
                    # Saltar este detalle si da error
                    continue
            
            # Si no tiene productos, agregar uno por defecto
            if not productos:
                productos.append({
                    "nombre": "Producto no disponible",
                    "descripcion": "",
                    "cantidad": 1,
                    "precio": 0,
                    "subtotal": 0
                })
            
            # Datos del pedido personalizado
            pers_data = None
            try:
                if hasattr(p, 'personalizado') and p.personalizado:
                    pers = p.personalizado
                    pers_data = {
                        "base": pers.base or "",
                        "acompanamientos": pers.acompañamientos or "",
                        "salsas": pers.salsas or "",
                        "instrucciones": pers.instrucciones or "",
                        "precio_extra": float(pers.precio_extra) if pers.precio_extra else 0
                    }
            except Exception:
                pers_data = None

            # Obtener hora de entrega formateada
            hora_entrega = ""
            if p.hora_entrega:
                try:
                    hora_entrega = p.hora_entrega.strftime('%H:%M')
                except:
                    hora_entrega = str(p.hora_entrega)

            data.append({
                "id": p.id,
                "mesa": p.mesa.numero if p.mesa else 0,
                "estado": p.estado or 'pendiente',
                "es_domicilio": p.es_domicilio if hasattr(p, 'es_domicilio') else False,
                "direccion_entrega": p.direccion_entrega or "",
                "hora_entrega": hora_entrega,
                "instrucciones_adicionales": p.instrucciones_adicionales or "",
                "es_personalizado": p.es_personalizado if hasattr(p, 'es_personalizado') else False,
                "personalizado": pers_data,
                "productos": productos,
                "total": float(p.total) if p.total else 0,
                "fecha_hora": p.fecha_hora.strftime('%Y-%m-%d %H:%M:%S') if p.fecha_hora else ""
            })
        
        return JsonResponse(data, safe=False)
        
    except Exception as e:
        print(f" Error en api_pedidos: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e), 'detalle': traceback.format_exc()}, status=500)

def api_pedido_detalle(request, pedido_id):
    """
    API pública para que el cliente vea su pedido en tiempo real sin fallos.
    """
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        productos = []
        
        #  CAMBIADO: usar DetallePedido.objects.filter en lugar de detallepedido_set
        for d in DetallePedido.objects.filter(pedido=pedido):
            try:
                if d.producto:
                    precio_unit = float(d.producto.precio) if d.producto.precio else 0
                    productos.append({
                        "nombre": d.producto.nombre or "Sin nombre",
                        "descripcion": d.producto.descripcion or "",
                        "cantidad": d.cantidad or 1,
                        "precio": precio_unit,
                        "subtotal": round(precio_unit * (d.cantidad or 1), 2)
                    })
            except Exception:
                continue
        
        if not productos:
            productos.append({
                "nombre": "Producto no disponible",
                "descripcion": "",
                "cantidad": 1,
                "precio": 0,
                "subtotal": 0
            })
        
        pers_data = None
        try:
            if hasattr(pedido, 'personalizado') and pedido.personalizado:
                pers = pedido.personalizado
                pers_data = {
                    "base": pers.base or "",
                    "acompanamientos": pers.acompañamientos or "",
                    "salsas": pers.salsas or "",
                    "instrucciones": pers.instrucciones or "",
                    "precio_extra": float(pers.precio_extra) if pers.precio_extra else 0
                }
        except Exception:
            pers_data = None

        hora_str = ""
        if pedido.hora_entrega:
            try:
                hora_str = pedido.hora_entrega.strftime('%H:%M')
            except Exception:
                hora_str = str(pedido.hora_entrega)

        data = {
            "id": pedido.id,
            "mesa": pedido.mesa.numero if pedido.mesa else 0,
            "estado": pedido.estado or 'pendiente',
            "es_domicilio": pedido.es_domicilio if hasattr(pedido, 'es_domicilio') else False,
            "direccion_entrega": pedido.direccion_entrega or "",
            "hora_entrega": hora_str,
            "instrucciones_adicionales": pedido.instrucciones_adicionales or "",
            "es_personalizado": pedido.es_personalizado if hasattr(pedido, 'es_personalizado') else False,
            "personalizado": pers_data,
            "productos": productos,
            "total": float(pedido.total) if pedido.total else 0,
            "fecha_hora": pedido.fecha_hora.strftime('%Y-%m-%d %H:%M:%S') if pedido.fecha_hora else ""
        }
        return JsonResponse(data, safe=False)
        
    except Exception as e:
        print(f" Error en api_pedido_detalle: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)

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

def cliente_required(view_func):
    """Decorador para vistas de clientes (QR) o usuarios autenticados"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get('cliente') or (request.user and request.user.is_authenticated):
            return view_func(request, *args, **kwargs)
        return redirect('login')
    return wrapper

@cliente_required
def confirmar_pedido(request):
    carrito = request.session.get('carrito', {})
    mesa_id = request.session.get('mesa_id')
    
    # Si es usuario autenticado (ej. admin probando), asignar mesa por defecto si falta
    if not mesa_id and request.user.is_authenticated:
        mesa_obj = Mesa.objects.first()
        if not mesa_obj:
            mesa_obj = Mesa.objects.create(numero=1)
        mesa_id = mesa_obj.id
        request.session['mesa_id'] = mesa_id
        request.session['cliente'] = True

    if not carrito and not request.POST.get('base_personalizado'):
        messages.error(request, 'No hay productos en el carrito')
        return redirect('menu')
    
    if not mesa_id:
        messages.error(request, 'No se identificó la mesa')
        return redirect('login')
    
    mesa = get_object_or_404(Mesa, id=mesa_id)
    
    tipo_entrega = request.POST.get('tipo_entrega', 'local')
    direccion = request.POST.get('direccion', '')
    hora_entrega = request.POST.get('hora_entrega', '')
    instrucciones_domicilio = request.POST.get('instrucciones_domicilio', '')
    
    pedido = Pedido.objects.create(
        mesa=mesa,
        es_domicilio=(tipo_entrega == 'domicilio'),
        direccion_entrega=direccion if tipo_entrega == 'domicilio' else '',
        hora_entrega=hora_entrega if tipo_entrega == 'domicilio' and hora_entrega else None,
        instrucciones_adicionales=instrucciones_domicilio if tipo_entrega == 'domicilio' else ''
    )
    
    total = 0.0
    categoria_personalizada, _ = Categoria.objects.get_or_create(nombre="Personalizados")
    has_custom = False

    # 1. Procesar items del carrito de la sesión
    for key, item in carrito.items():
        if item.get('es_personalizado'):
            has_custom = True
            nombre_base = item.get('base', 'Personalizado')
            precio_item = float(item.get('precio', 0))
            desc_item = item.get('descripcion', '')
            
            producto, created = Producto.objects.get_or_create(
                nombre=f"Personalizado ({nombre_base})",
                defaults={
                    'descripcion': desc_item,
                    'precio': precio_item,
                    'categoria': categoria_personalizada
                }
            )
            if not created:
                producto.precio = precio_item
                producto.descripcion = desc_item
                producto.save()
            
            cant = int(item.get('cantidad', 1))
            DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=cant
            )
            
            total += precio_item * cant
            
            if not hasattr(pedido, 'personalizado'):
                acomps = item.get('acompanamientos', [])
                salsas_list = item.get('salsas', [])
                acomps_str = ', '.join(acomps) if isinstance(acomps, list) else str(acomps)
                salsas_str = ', '.join(salsas_list) if isinstance(salsas_list, list) else str(salsas_list)

                PedidoPersonalizado.objects.create(
                    pedido=pedido,
                    base=nombre_base,
                    acompañamientos=acomps_str,
                    salsas=salsas_str,
                    instrucciones=item.get('instrucciones', ''),
                    precio_extra=float(item.get('precio_extra', 0))
                )
        else:
            try:
                producto = Producto.objects.get(id=int(key))
                cantidad = int(item.get('cantidad', 1))
                
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto=producto,
                    cantidad=cantidad
                )
                total += float(producto.precio) * cantidad
            except (Producto.DoesNotExist, ValueError):
                continue

    # 2. Procesar plato personalizado
    inline_base = request.POST.get('base_personalizado', '').strip()
    if inline_base:
        has_custom = True
        inline_acomps = request.POST.getlist('acompanamientos')
        inline_salsas = request.POST.getlist('salsas_personalizado')
        inline_instr = request.POST.get('instrucciones_personalizado', '').strip()

        precios_base = {
            'Pollo': 6.00,
            'Carne': 7.00,
            'Cerdo': 6.50,
            'Pescado': 8.00,
            'Vegetariano': 5.00,
            'Mixto': 8.50,
        }
        base_price = precios_base.get(inline_base, 5.00)
        extra_price = (len(inline_acomps) * 2.00) + (len(inline_salsas) * 1.00)
        custom_total = base_price + extra_price

        desc_partes = [f"Base: {inline_base} (${base_price:.2f})"]
        if inline_acomps:
            desc_partes.append(f"Acompañamientos (+${len(inline_acomps)*2:.2f}): {', '.join(inline_acomps)}")
        if inline_salsas:
            desc_partes.append(f"Salsas (+${len(inline_salsas)*1:.2f}): {', '.join(inline_salsas)}")
        if inline_instr:
            desc_partes.append(f"Indicaciones: {inline_instr}")

        desc_completa = " | ".join(desc_partes)

        producto_custom, created = Producto.objects.get_or_create(
            nombre=f"Personalizado ({inline_base})",
            defaults={
                'descripcion': desc_completa,
                'precio': custom_total,
                'categoria': categoria_personalizada
            }
        )
        if not created:
            producto_custom.precio = custom_total
            producto_custom.descripcion = desc_completa
            producto_custom.save()

        DetallePedido.objects.create(
            pedido=pedido,
            producto=producto_custom,
            cantidad=1
        )

        total += custom_total

        if not hasattr(pedido, 'personalizado'):
            PedidoPersonalizado.objects.create(
                pedido=pedido,
                base=inline_base,
                acompañamientos=', '.join(inline_acomps),
                salsas=', '.join(inline_salsas),
                instrucciones=inline_instr,
                precio_extra=extra_price
            )

    pedido.es_personalizado = has_custom

    # ==========  APLICAR DESCUENTO DE PROMOCIÓN ==========
    promocion_data = request.session.get('promocion_aplicada')
    if promocion_data:
        if promocion_data['tipo'] == 'porcentaje':
            total = total * (1 - promocion_data['valor'] / 100)
        else:
            total = total - promocion_data['valor']
        total = max(0, round(total, 2))
        # Eliminar la promoción de la sesión después de aplicarla
        del request.session['promocion_aplicada']
    # =====================================================

    pedido.total = round(total, 2)
    pedido.save()
    
    # Vaciar el carrito
    request.session['carrito'] = {}
    request.session['pedido_id'] = pedido.id
    request.session['cliente'] = True
    request.session.modified = True
    
    messages.success(request, f' Pedido #{pedido.id} confirmado por ${total:.2f}')
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
    pedido = get_object_or_404(Pedido, id=pedido_id)  # ← CAMBIADO
    
    # Verificar si el pedido tiene productos
    if not pedido.tiene_productos():
        messages.error(request, ' Este pedido no tiene productos. Por favor, agrega productos antes de pagar.')
        return redirect('ver_carrito')
    
    # Calcular el total actualizado
    pedido.calcular_total()
    
    # Obtener los detalles del pedido
    detalles = pedido.detalles.all()
    
    return render(request, 'pago.html', {
        'pedido': pedido,
        'detalles': detalles,
        'metodos': Pago.METODOS
    })

@cliente_required
def confirmar_pago(request):
    if request.method == "POST":
        try:
            pedido_id = request.POST.get('pedido_id')
            metodo = request.POST.get('metodo', 'tarjeta')
            pedido = get_object_or_404(Pedido, id=pedido_id)  # ← CAMBIADO
            
            # Verificar si el pedido tiene productos
            if not pedido.tiene_productos():
                messages.error(request, ' No se puede pagar un pedido sin productos.')
                return redirect('ver_carrito')
            
            # Calcular total actualizado antes de pagar
            total = pedido.calcular_total()
            
            if total == 0:
                messages.error(request, ' El total del pedido es $0.00. No se puede procesar el pago.')
                return redirect('ver_carrito')
            
            # Crear o actualizar el pago
            pago, created = Pago.objects.update_or_create(
                pedido=pedido,
                defaults={
                    'metodo': metodo,
                    'estado': 'aprobado',
                    'monto': total,
                    'referencia': f"SIM-{pedido.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                }
            )
            
            # Limpiar carrito
            request.session['carrito'] = {}
            request.session.modified = True
            
            messages.success(request, f' Pago de ${total:.2f} verificado exitosamente.')
            return redirect('comprobante_pago', pago_id=pago.id)
            
        except Exception as e:
            print(f" Error en confirmar_pago: {e}")
            import traceback
            traceback.print_exc()
            
            messages.error(request, f' Error al procesar el pago: {str(e)}')
            return redirect('ver_carrito')
    
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
    productos = Producto.objects.all()
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo_descuento = request.POST.get('tipo_descuento', 'porcentaje')
        valor_descuento_raw = request.POST.get('valor_descuento', '0')
        fecha_inicio_raw = request.POST.get('fecha_inicio', '')
        fecha_fin_raw = request.POST.get('fecha_fin', '')
        productos_ids = request.POST.getlist('productos')
        #  AGREGAR ESTO
        activo = request.POST.get('activo') == 'on'  # Si viene del checkbox

        if not nombre:
            messages.error(request, "El nombre de la promoción es obligatorio.")
            return render(request, 'promociones/crear.html', {'productos': productos})

        try:
            valor_descuento = float(valor_descuento_raw)
            if valor_descuento <= 0:
                messages.error(request, "El valor del descuento debe ser mayor a 0.")
                return render(request, 'promociones/crear.html', {'productos': productos})
            if tipo_descuento == 'porcentaje' and valor_descuento > 100:
                messages.error(request, "El porcentaje de descuento no puede exceder el 100%.")
                return render(request, 'promociones/crear.html', {'productos': productos})
        except ValueError:
            messages.error(request, "Ingresa un valor de descuento numérico válido.")
            return render(request, 'promociones/crear.html', {'productos': productos})

        if not fecha_inicio_raw or not fecha_fin_raw:
            messages.error(request, "Las fechas de inicio y fin son obligatorias.")
            return render(request, 'promociones/crear.html', {'productos': productos})

        if fecha_fin_raw <= fecha_inicio_raw:
            messages.error(request, "La fecha de fin debe ser posterior a la fecha de inicio.")
            return render(request, 'promociones/crear.html', {'productos': productos})

        #  CREAR CON activo=True
        promocion = Promocion.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            tipo_descuento=tipo_descuento,
            valor_descuento=valor_descuento,
            fecha_inicio=fecha_inicio_raw,
            fecha_fin=fecha_fin_raw,
            activo=True  # 👈 ESTO ES LO QUE FALTA
        )
        
        if 'imagen' in request.FILES:
            promocion.imagen = request.FILES['imagen']
            promocion.save()

        promocion.productos.set(productos_ids)
        messages.success(request, ' Promoción creada exitosamente.')
        return redirect('lista_promociones')
    
    return render(request, 'promociones/crear.html', {'productos': productos})

@admin_required
def editar_promocion(request, id):
    promocion = get_object_or_404(Promocion, id=id)
    productos = Producto.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo_descuento = request.POST.get('tipo_descuento', 'porcentaje')
        valor_descuento_raw = request.POST.get('valor_descuento', '0')
        fecha_inicio_raw = request.POST.get('fecha_inicio', '')
        fecha_fin_raw = request.POST.get('fecha_fin', '')
        productos_ids = request.POST.getlist('productos')
        # ESTO YA ESTÁ BIEN, PERO VERIFICA:
        activo = request.POST.get('activo') == 'on'  # True si está marcado

        if not nombre:
            messages.error(request, "El nombre de la promoción es obligatorio.")
            return render(request, 'promociones/editar.html', {'promocion': promocion, 'productos': productos})

        try:
            valor_descuento = float(valor_descuento_raw)
            if valor_descuento <= 0:
                messages.error(request, "El valor del descuento debe ser mayor a 0.")
                return render(request, 'promociones/editar.html', {'promocion': promocion, 'productos': productos})
            if tipo_descuento == 'porcentaje' and valor_descuento > 100:
                messages.error(request, "El porcentaje de descuento no puede exceder el 100%.")
                return render(request, 'promociones/editar.html', {'promocion': promocion, 'productos': productos})
        except ValueError:
            messages.error(request, "Ingresa un valor de descuento numérico válido.")
            return render(request, 'promociones/editar.html', {'promocion': promocion, 'productos': productos})

        if not fecha_inicio_raw or not fecha_fin_raw:
            messages.error(request, "Las fechas de inicio y fin son obligatorias.")
            return render(request, 'promociones/editar.html', {'promocion': promocion, 'productos': productos})

        if fecha_fin_raw <= fecha_inicio_raw:
            messages.error(request, "La fecha de fin debe ser posterior a la fecha de inicio.")
            return render(request, 'promociones/editar.html', {'promocion': promocion, 'productos': productos})

        promocion.nombre = nombre
        promocion.descripcion = descripcion
        promocion.tipo_descuento = tipo_descuento
        promocion.valor_descuento = valor_descuento
        promocion.fecha_inicio = fecha_inicio_raw
        promocion.fecha_fin = fecha_fin_raw
        promocion.activo = activo 

        if 'imagen' in request.FILES:
            promocion.imagen = request.FILES['imagen']

        promocion.productos.set(productos_ids)
        promocion.save()
        
        messages.success(request, ' Promoción actualizada correctamente.')
        return redirect('lista_promociones')
    
    return render(request, 'promociones/editar.html', {
        'promocion': promocion,
        'productos': productos
    })
@admin_required
def eliminar_promocion(request, id):
    promocion = get_object_or_404(Promocion, id=id)
    promocion.delete()
    messages.success(request, ' Promoción eliminada.')
    return redirect('lista_promociones')


def promociones_cliente(request):
    ahora = timezone.now()
    promociones = Promocion.objects.filter(
        activo=True,
        fecha_inicio__lte=ahora,
        fecha_fin__gte=ahora
    )
    return render(request, 'promociones/cliente.html', {'promociones': promociones})

@cliente_required
def agregar_promocion_carrito(request, promo_id):
    """Agrega todos los productos de una promoción al carrito"""
    promocion = get_object_or_404(Promocion, id=promo_id)
    
    # Verificar que la promoción está activa
    ahora = timezone.now()
    if not (promocion.activo and promocion.fecha_inicio <= ahora <= promocion.fecha_fin):
        messages.error(request, "Esta promoción ya no está activa")
        return redirect('promociones_cliente')
    
    carrito = request.session.get('carrito', {})
    productos_promo = promocion.productos.all()
    
    if not productos_promo.exists():
        messages.error(request, "Esta promoción no tiene productos asociados")
        return redirect('promociones_cliente')
    
    # Agregar cada producto de la promoción al carrito
    for producto in productos_promo:
        if str(producto.id) in carrito:
            carrito[str(producto.id)]['cantidad'] += 1
        else:
            carrito[str(producto.id)] = {
                'id': producto.id,
                'nombre': producto.nombre,
                'descripcion': producto.descripcion,
                'precio': float(producto.precio),
                'cantidad': 1,
                'imagen': producto.imagen.url if producto.imagen else ''
            }
    
    request.session['carrito'] = carrito
    request.session.modified = True
    
    # Aplicar descuento global en el carrito (opcional)
    # Si quieres aplicar el descuento a todo el carrito
    request.session['promocion_aplicada'] = {
        'id': promocion.id,
        'nombre': promocion.nombre,
        'tipo': promocion.tipo_descuento,
        'valor': float(promocion.valor_descuento)
    }
    
    messages.success(request, f'¡Promoción "{promocion.nombre}" agregada al carrito!')
    return redirect('ver_carrito')


@cliente_required
def pedido_personalizado(request):
    if request.method == 'POST':
        base = request.POST.get('base_personalizado', '').strip()
        acompanamientos = request.POST.getlist('acompanamientos')
        salsas = request.POST.getlist('salsas_personalizado')
        instrucciones = request.POST.get('instrucciones_personalizado', '').strip()
        
        if not base:
            messages.error(request, " Por favor selecciona una base/proteína para tu plato.")
            return render(request, 'pedido_personalizado.html')

        # Tabla de precios base
        precios_base = {
            'Pollo': 6.00,
            'Carne': 7.00,
            'Cerdo': 6.50,
            'Pescado': 8.00,
            'Vegetariano': 5.00,
            'Mixto': 8.50,
        }
        
        precio_base = precios_base.get(base, 5.00)
        precio_extra = (len(acompanamientos) * 2.00) + (len(salsas) * 1.00)
        total = precio_base + precio_extra
        
        carrito = request.session.get('carrito', {})
        
        max_id = 0
        for key in carrito.keys():
            try:
                val = int(key)
                if val > max_id:
                    max_id = val
            except ValueError:
                pass
        nuevo_id = max_id + 1000
        
        desc_partes = [f"Base: {base} (${precio_base:.2f})"]
        if acompanamientos:
            desc_partes.append(f"Acompañamientos (+${len(acompanamientos)*2:.2f}): {', '.join(acompanamientos)}")
        if salsas:
            desc_partes.append(f"Salsas (+${len(salsas)*1:.2f}): {', '.join(salsas)}")
        if instrucciones:
            desc_partes.append(f"Indicaciones: {instrucciones}")
            
        desc_completa = " | ".join(desc_partes)
        
        carrito[str(nuevo_id)] = {
            'id': str(nuevo_id),
            'nombre': f"Plato Personalizado ({base})",
            'descripcion': desc_completa,
            'precio': float(total),
            'cantidad': 1,
            'imagen': '',
            'es_personalizado': True,
            'instrucciones': instrucciones,
            'base': base,
            'acompanamientos': acompanamientos,
            'salsas': salsas,
            'precio_extra': float(precio_extra)
        }
        
        request.session['carrito'] = carrito
        request.session.modified = True
        
        messages.success(request, f' Plato personalizado ({base}) agregado por ${total:.2f}')
        return redirect('ver_carrito')
    
    return render(request, 'pedido_personalizado.html')


def resetear_productos(request):
    try:
        from Aplicacion.Menud.models import Producto
        
        # Eliminar productos personalizados
        eliminados = Producto.objects.filter(nombre__contains="Personalizado").delete()
        
        # Resetear secuencia
        with connection.cursor() as c:
            c.execute("SELECT setval('Menud_producto_id_seq', COALESCE((SELECT MAX(id) FROM Menud_producto), 1), false);")
        
        return HttpResponse(f" Listo! Eliminados {eliminados[0]} productos. Secuencia reseteada.")
    except Exception as e:
        return HttpResponse(f" Error: {e}")

def validar_email(request):
    email = request.GET.get('email', '')
    existe = User.objects.filter(email=email).exists()
    return JsonResponse({'existe': existe})

def validar_email_editar(request):
    email = request.GET.get('email', '')
    usuario_id = request.GET.get('usuario_id', '')
    existe = User.objects.filter(email=email).exclude(id=usuario_id).exists()
    return JsonResponse({'existe': existe})