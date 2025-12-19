from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = 'Clear all sample data from the database'

    def handle(self, *args, **options):
        from kickzone_app.models import (
            User, Pitch, PitchAvailability, Booking, Payment, 
            Review, Tournament, TournamentTeam, Message, Promotion, SystemSetting
        )
        
        self.stdout.write('Clearing sample data...')
        
        with transaction.atomic():
            # Clear related data first (foreign key dependencies)
            Message.objects.filter(sender__username__startswith='player_').delete()
            Message.objects.filter(recipient__username__startswith='player_').delete()
            Message.objects.filter(sender__username__startswith='owner_').delete()
            Message.objects.filter(recipient__username__startswith='owner_').delete()
            
            TournamentTeam.objects.filter(captain__username__startswith='player_').delete()
            TournamentTeam.objects.filter(tournament__organizer__username__startswith='owner_').delete()
            
            Review.objects.filter(player__username__startswith='player_').delete()
            Review.objects.filter(pitch__owner__username__startswith='owner_').delete()
            
            Payment.objects.filter(booking__player__username__startswith='player_').delete()
            Payment.objects.filter(booking__pitch__owner__username__startswith='owner_').delete()
            
            Booking.objects.filter(player__username__startswith='player_').delete()
            Booking.objects.filter(pitch__owner__username__startswith='owner_').delete()
            
            PitchAvailability.objects.filter(pitch__owner__username__startswith='owner_').delete()
            
            Tournament.objects.filter(organizer__username__startswith='owner_').delete()
            Tournament.objects.filter(pitch__owner__username__startswith='owner_').delete()
            
            Pitch.objects.filter(owner__username__startswith='owner_').delete()
            
            Promotion.objects.all().delete()
            
            # Clear users (except admin)
            User.objects.filter(username__startswith='player_').delete()
            User.objects.filter(username__startswith='owner_').delete()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully cleared all sample data')
        )