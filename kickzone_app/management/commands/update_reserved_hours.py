from django.core.management.base import BaseCommand
from kickzone_app.models import User

class Command(BaseCommand):
    help = 'Update reserved_hours field for all users based on their bookings'

    def handle(self, *args, **options):
        updated_count = 0
        
        for user in User.objects.all():
            old_hours = user.reserved_hours
            user.update_reserved_hours()
            new_hours = user.reserved_hours
            
            if old_hours != new_hours:
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Updated {user.username}: {old_hours} -> {new_hours} hours')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} users')
        )