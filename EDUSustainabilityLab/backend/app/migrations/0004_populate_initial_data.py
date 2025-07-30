from django.db import migrations
from django.contrib.auth.models import User, Group, Permission
import os
from django.utils import timezone

def load_initial_data(apps, schema_editor):
    # Get superuser username from environment variables
    superuser_username = os.getenv('DJANGO_SUPERUSER_USERNAME')
    superuser_password = os.getenv('DJANGO_SUPERUSER_PASSWORD')  # Ensure this is set in your environment
    superuser_email = os.getenv('DJANGO_SUPERUSER_EMAIL')  # Ensure this is set in your environment
    
    # Check if superuser already exists
    if not User.objects.filter(username=superuser_username).exists():
        # Create superuser if it doesn't exist
        user = User.objects.create_superuser(
            username=superuser_username,
            email=superuser_email,
            password=superuser_password,
            last_login = timezone.now()
        )
        user.save()

    # Create groups
    Group.objects.bulk_create([
        Group(id=1, name='Pending'),
        Group(id=2, name='Administrator'),
        Group(id=3, name='Educator')
    ])

    # Get the superuser object
    user = User.objects.get(username=superuser_username)
    
    # Create the "Administrator" group and assign permissions
    admin_group, created = Group.objects.get_or_create(name='Administrator')

    # Assign all permissions to the admin group
    permissions = Permission.objects.all()
    admin_group.permissions.set(permissions)

    # Add the user to the "Administrator" group
    user.groups.add(admin_group)

class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_alter_activity_description"),  # Adjust the dependency as necessary
    ]

    operations = [
        migrations.RunPython(load_initial_data),
    ]
