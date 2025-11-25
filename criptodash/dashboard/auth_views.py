from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
import re


def validate_email(email):
    """Valida el formato del email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@require_http_methods(["GET", "POST"])
@csrf_protect
def custom_login(request):
    """Vista personalizada de login con MySQL"""
    if request.user.is_authenticated:
        return redirect('dashboard_index')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not username or not password:
            messages.error(request, 'Por favor ingresa usuario y contraseña')
            return render(request, 'dashboard/login.html')
        
        # Intentar login con usuario
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.first_name or user.username}!')
            next_url = request.GET.get('next', 'dashboard_index')
            return redirect(next_url)
        else:
            # Intentar login con email
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(request, username=user_obj.username, password=password)
                if user is not None:
                    login(request, user)
                    messages.success(request, f'¡Bienvenido {user.first_name or user.username}!')
                    next_url = request.GET.get('next', 'dashboard_index')
                    return redirect(next_url)
            except User.DoesNotExist:
                pass
            
            messages.error(request, 'Usuario o contraseña incorrectos')
            return render(request, 'dashboard/login.html', {'username': username})
    
    return render(request, 'dashboard/login.html')


@require_http_methods(["GET", "POST"])
@csrf_protect
def custom_register(request):
    """Vista personalizada de registro"""
    if request.user.is_authenticated:
        return redirect('dashboard_index')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        first_name = request.POST.get('first_name', '').strip()
        
        # Validaciones
        if not all([username, email, password1, password2]):
            messages.error(request, 'Todos los campos son obligatorios')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
        
        if len(username) < 3:
            messages.error(request, 'El usuario debe tener al menos 3 caracteres')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
        
        if not validate_email(email):
            messages.error(request, 'El email no es válido')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
        
        if len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
        
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
        
        # Verificar si el usuario ya existe
        if User.objects.filter(username=username).exists():
            messages.error(request, 'El usuario ya existe')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El email ya está registrado')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
        
        # Crear usuario
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name
            )
            # Login automático después del registro
            user = authenticate(request, username=username, password=password1)
            login(request, user)
            messages.success(request, f'¡Bienvenido {first_name or username}! Tu cuenta ha sido creada.')
            return redirect('dashboard_index')
        except Exception as e:
            messages.error(request, f'Error al crear la cuenta: {str(e)}')
            return render(request, 'dashboard/register.html', {
                'username': username,
                'email': email,
                'first_name': first_name
            })
    
    return render(request, 'dashboard/register.html')


@require_http_methods(["GET"])
@login_required(login_url='custom_login')
def custom_logout(request):
    """Vista para cerrar sesión"""
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('custom_login')


@login_required(login_url='custom_login')
def profile(request):
    """Vista del perfil del usuario"""
    return render(request, 'dashboard/profile.html', {'user': request.user})
