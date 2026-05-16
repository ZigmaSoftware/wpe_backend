#!/usr/bin/env python
"""
Create superuser script for WPE Django Project
This script creates a superuser with username 'dev' and password 'dev@123'

Usage:
    python manage.py shell < create_superuser.py

    OR run from manage.py:

    python manage.py shell -c "exec(open('create_superuser.py').read())"
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_system.settings')
django.setup()

from django.contrib.auth.models import User

def create_superuser():
    """Create or update superuser"""

    username = 'dev'
    email = 'dev@example.com'
    password = 'dev@123'

    # Check if user already exists
    try:
        user = User.objects.get(username=username)
        print(f'✓ User "{username}" already exists.')
        print(f'  Updating password to "dev@123"...')
        user.set_password(password)
        user.save()
        print(f'✓ Password updated successfully!')

    except User.DoesNotExist:
        print(f'✓ Creating new superuser "{username}"...')
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f'✓ Superuser "{username}" created successfully!')

    # Display user information
    user = User.objects.get(username=username)
    print('\n' + '='*50)
    print('SUPERUSER INFORMATION')
    print('='*50)
    print(f'Username:    {user.username}')
    print(f'Email:       {user.email}')
    print(f'Password:    dev@123')
    print(f'Is Staff:    {user.is_staff}')
    print(f'Is Superuser: {user.is_superuser}')
    print('='*50)
    print('\n✓ You can now login to Django admin at:')
    print('  http://localhost:8000/admin/')
    print('\nLogin credentials:')
    print('  Username: dev')
    print('  Password: dev@123')
    print('\n')

if __name__ == '__main__':
    create_superuser()
