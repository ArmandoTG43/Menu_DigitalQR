# reset_db.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Sistema.settings')
django.setup()

from Aplicacion.Menud.models import Pedido, DetallePedido, Pago, Producto, Mesa

def resetear_sistema():
    print("="*60)
    print("🔥 REINICIANDO SISTEMA...")
    print("="*60)
    
    # 1. Eliminar datos existentes
    print("\n🗑️ ELIMINANDO DATOS CORRUPTOS...")
    pagos = Pago.objects.count()
    detalles = DetallePedido.objects.count()
    pedidos = Pedido.objects.count()
    
    Pago.objects.all().delete()
    DetallePedido.objects.all().delete()
    Pedido.objects.all().delete()
    
    print(f"   ✅ {pagos} pagos eliminados")
    print(f"   ✅ {detalles} detalles eliminados")
    print(f"   ✅ {pedidos} pedidos eliminados")
    
    # 2. Verificar productos
    print("\n VERIFICANDO PRODUCTOS...")
    if Producto.objects.count() == 0:
        productos_data = [
            {"nombre": "Hamburguesa Clásica", "precio": 12.00},
            {"nombre": "Hamburguesa Doble", "precio": 15.00},
            {"nombre": "Papas Fritas", "precio": 5.00},
            {"nombre": "Cerveza Artesanal", "precio": 8.50},
            {"nombre": "Refresco", "precio": 3.50},
            {"nombre": "Ensalada César", "precio": 10.00},
        ]
        for p in productos_data:
            Producto.objects.create(**p)
        print(f"    {len(productos_data)} productos creados")
    else:
        print(f"    {Producto.objects.count()} productos existentes")
    
    # 3. Crear mesa
    mesa, created = Mesa.objects.get_or_create(numero=1, defaults={'capacidad': 4})
    print(f"\n Mesa #{mesa.numero} {'creada' if created else 'ya existe'}")
    
    # 4. Crear pedido de prueba
    pedido = Pedido.objects.create(
        mesa=mesa,
        estado='pendiente',
        total=0.00
    )
    print(f"\n Pedido #{pedido.id} creado")
    
    # 5. Agregar productos al pedido
    print("\n AGREGANDO PRODUCTOS AL PEDIDO:")
    productos = Producto.objects.all()[:3]
    total = 0
    for i, p in enumerate(productos, 1):
        detalle = DetallePedido.objects.create(
            pedido=pedido,
            producto=p,
            cantidad=i,
            precio_unitario=p.precio
        )
        subtotal = i * p.precio
        total += subtotal
        print(f"   ✅ {p.nombre} x{i} = ${subtotal:.2f}")
    
    # 6. Actualizar total
    pedido.total = total
    pedido.save()
    
    print("\n" + "="*60)
    print("¡SISTEMA REINICIADO CORRECTAMENTE!")
    print("="*60)
    print(f"\nPEDIDO NUEVO: #{pedido.id}")
    print(f" TOTAL: ${total:.2f}")
    print(f"🔗 URL DE PAGO: https://menu-digitalqr.onrender.com/crear-pago/{pedido.id}/")
    print("="*60)

if __name__ == "__main__":
    resetear_sistema()