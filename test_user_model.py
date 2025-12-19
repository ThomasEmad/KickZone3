#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, '/test/path/backend')

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kickzone.settings')

# Setup Django
django.setup()

# Now test the User models
from django.contrib.auth.models import User as DjangoUser
from kickzone_app.models import User as CustomUser

print("=== Testing User Models ===")
print(f"Django User model: {DjangoUser}")
print(f"Django User._meta.app_label: {DjangoUser._meta.app_label}")
print(f"Django User._meta.model_name: {DjangoUser._meta.model_name}")
print()

print(f"Custom User model: {CustomUser}")
print(f"Custom User._meta.app_label: {CustomUser._meta.app_label}")
print(f"Custom User._meta.model_name: {CustomUser._meta.model_name}")
print()

print("=== Testing User.objects ===")
try:
    django_users = DjangoUser.objects.all()
    print(f"Django User.objects.all() works: {len(django_users)} users")
except Exception as e:
    print(f"Django User.objects.all() failed: {e}")

try:
    custom_users = CustomUser.objects.all()
    print(f"Custom User.objects.all() works: {len(custom_users)} users")
except Exception as e:
    print(f"Custom User.objects.all() failed: {e}")

