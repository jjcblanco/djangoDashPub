import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from dashboard.views.bot_views import bot_dashboard

def test_view():
    factory = RequestFactory()
    user = User.objects.first()
    if not user:
        user = User.objects.create_user(username='testuser', password='password')
    
    request = factory.get('/bots/')
    request.user = user
    
    try:
        response = bot_dashboard(request)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 500:
            content = response.content.decode('utf-8', errors='ignore')
            with open('view_error_full.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print("Full error content written to view_error_full.html")
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open('view_exception.txt', 'w', encoding='utf-8') as f:
            f.write(error_msg)
        print(f"Exception caught and written to view_exception.txt: {e}")

if __name__ == "__main__":
    test_view()
