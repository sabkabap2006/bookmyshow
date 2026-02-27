import os
import random
import string
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Creates a secure master admin account'

    def handle(self, *args, **kwargs):
        if User.objects.filter(username='admin_master').exists():
            self.stdout.write(self.style.WARNING("Admin user 'admin_master' already exists."))
            return
            
        password = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=16))
        
        # This automatically uses Django's default secure PBKDF2 hashing algorithm
        User.objects.create_superuser('admin_master', 'admin@bookmyshow.local', password)
        
        self.stdout.write(self.style.SUCCESS(f"Successfully created superuser 'admin_master'"))
        self.stdout.write(self.style.SUCCESS(f"RAW_PASSWORD={password}"))
