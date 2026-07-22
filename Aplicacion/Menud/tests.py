from django.test import TestCase, Client
from django.urls import reverse
from Aplicacion.Menud.models import Mesa, Pedido, Producto, Categoria, Usuario, Pago

class MenudTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.mesa1 = Mesa.objects.create(numero=1)
        self.mesa2 = Mesa.objects.create(numero=2)
        self.admin = Usuario.objects.create_superuser(username='admin', email='admin@test.com', password='password123', rol='admin')
        
    def test_pedido_personalizado_precio_y_confirmacion(self):
        # 1. Simular sesión cliente QR
        session = self.client.session
        session['cliente'] = True
        session['mesa_id'] = self.mesa1.id
        session.save()
        
        # 2. Agregar plato personalizado con extras
        response = self.client.post(reverse('pedido_personalizado'), {
            'base_personalizado': 'Pollo',
            'acompanamientos': ['Papas fritas', 'Arroz'],
            'salsas_personalizado': ['Salsa picante'],
            'instrucciones_personalizado': 'Sin sal'
        })
        self.assertEqual(response.status_code, 302)
        
        # Verificar precio en carrito: Pollo ($6.00) + 2 acomp ($4.00) + 1 salsa ($1.00) = $11.00
        session = self.client.session
        carrito = session.get('carrito', {})
        self.assertEqual(len(carrito), 1)
        item = list(carrito.values())[0]
        self.assertEqual(item['precio'], 11.00)
        
        # 3. Confirmar pedido
        response_conf = self.client.post(reverse('confirmar_pedido'), {
            'tipo_entrega': 'local'
        })
        self.assertEqual(response_conf.status_code, 302)
        
        # Verificar que el pedido en DB tiene total 11.00 y carrito vacio
        pedido = Pedido.objects.last()
        self.assertIsNotNone(pedido)
        self.assertEqual(float(pedido.total), 11.00)
        self.assertEqual(len(self.client.session.get('carrito', {})), 0)
        
        # 4. Confirmar pago (sin error 500)
        response_pago = self.client.post(reverse('confirmar_pago'), {
            'pedido_id': pedido.id,
            'metodo': 'tarjeta'
        })
        self.assertEqual(response_pago.status_code, 302)
        pago = Pago.objects.filter(pedido=pedido).first()
        self.assertIsNotNone(pago)
        self.assertEqual(pago.estado, 'aprobado')
        
        # 5. Probar API de cocina
        self.client.login(username='admin', password='password123')
        response_api = self.client.get(reverse('api_pedidos'))
        self.assertEqual(response_api.status_code, 200)
        data = response_api.json()
        self.assertTrue(len(data) > 0)
        self.assertEqual(data[0]['total'], 11.00)

    def test_cambiar_mesa_qr_limpia_carrito(self):
        # 1. Escanear Mesa 1
        self.client.get(reverse('menu_cliente', kwargs={'mesa_id': self.mesa1.id}))
        
        # 2. Agregar item al carrito en Mesa 1
        self.client.post(reverse('pedido_personalizado'), {
            'base_personalizado': 'Carne',
            'acompanamientos': [],
            'salsas_personalizado': [],
            'instrucciones_personalizado': ''
        })
        self.assertEqual(len(self.client.session['carrito']), 1)
        self.assertEqual(self.client.session['mesa_id'], self.mesa1.id)
        
        # 3. Escanear Mesa 2 sin haber confirmado la Mesa 1
        self.client.get(reverse('menu_cliente', kwargs={'mesa_id': self.mesa2.id}))
        
        # 4. Verificar que el carrito de Mesa 1 se limpió y ahora la mesa activa es Mesa 2
        self.assertEqual(self.client.session['mesa_id'], self.mesa2.id)
        self.assertEqual(len(self.client.session['carrito']), 0)
