from django.core.management.base import BaseCommand
from kickzone_app.models import Booking


class Command(BaseCommand):
    help = 'Update expired bookings from pending to completed status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get current time info
        from django.utils import timezone
        from datetime import datetime
        
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        
        if verbose:
            self.stdout.write(f"Current date: {current_date}")
            self.stdout.write(f"Current time: {current_time}")
        
        # Find bookings that should be completed
        from django.db.models import Q
        expired_bookings = Booking.objects.filter(
            status='pending'
        ).filter(
            # Date has passed OR (date is today AND end time has passed)
            Q(date__lt=current_date) |
            Q(date=current_date, end_time__lte=current_time)
        ).select_related('pitch', 'player')
        
        expired_count = expired_bookings.count()
        
        if expired_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No expired bookings found.')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'Found {expired_count} expired bookings:')
        )
        
        if verbose:
            for booking in expired_bookings:
                self.stdout.write(
                    f"  - {booking.pitch.name} | {booking.player.username} | "
                    f"Date: {booking.date} | Time: {booking.start_time}-{booking.end_time} | "
                    f"Status: {booking.status}"
                )
        
        if not dry_run:
            updated_count = Booking.update_expired_bookings()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} bookings to completed status.'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'In live mode, {expired_count} bookings would be updated.'
                )
            )