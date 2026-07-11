from django import forms
from .models import Producto, PerfilAdmin

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = '__all__'

        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'disponible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }



class PerfilForm(forms.ModelForm):
    class Meta:
        model = PerfilAdmin
        fields = ['foto', 'telefono', 'direccion']

