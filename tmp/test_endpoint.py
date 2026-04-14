import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth.models import User
# Create a test user if not exists
try:
    user = User.objects.get(username='testuser')
except User.DoesNotExist:
    user = User.objects.create_user('testuser', 'test@example.com', 'testpass')
    user.is_staff = True
    user.save()
client = Client()
client.force_login(user)
response = client.post('/whale-insights/learn-patterns/')
print(f'Status: {response.status_code}')
print(f'Content: {response.content.decode()}')
import json
data = json.loads(response.content)
print(f'Status field: {data.get("status")}')
print(f'Message: {data.get("message")}')
print(f'Patterns count: {data.get("patterns_count")}')