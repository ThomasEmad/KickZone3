from django.core.management.base import BaseCommand
from django.contrib.auth.models import User as DjangoUser
from faker import Faker
from faker.providers import BaseProvider
from kickzone_app.models import User, Pitch, PitchAvailability, Booking, Payment, Review, Tournament, TournamentTeam, Message, Promotion, SystemSetting
import random
from datetime import datetime, timedelta, time
from decimal import Decimal

class EgyptianPhoneProvider(BaseProvider):
    def egyptian_phone_number(self):
        """Generate an Egyptian phone number starting with 011, 012, 015, or 010"""
        prefixes = ['011', '012', '015', '010']
        prefix = self.random_element(prefixes)
        # Generate 8 digits after the prefix with fixed length
        number = prefix + str(self.random_number(digits=8, fix_len=True))
        return number[:20]  # Limit to 20 characters as per model field

class Command(BaseCommand):
    help = 'Generate sample data using Faker'

    def add_arguments(self, parser):
        parser.add_argument(
            '--promotions',
            type=int,
            default=5,
            help='Number of promotions to create'
        )

    def handle(self, *args, **options):
        fake = Faker()
        fake.add_provider(EgyptianPhoneProvider)

        # Create users
        self.stdout.write('Creating users...')
        users = self.create_users(fake, 20)  # Create 20 users
        self.stdout.write(f'Created {len(users)} users')

        # Create pitches
        self.stdout.write('Creating pitches...')
        pitches = self.create_pitches(fake, 15, users)  # Create 15 pitches
        self.stdout.write(f'Created {len(pitches)} pitches')

        # Create pitch availabilities
        self.stdout.write('Creating pitch availabilities...')
        self.create_pitch_availabilities(pitches)
        self.stdout.write('Created pitch availabilities')

        # Create bookings
        self.stdout.write('Creating bookings...')
        bookings = self.create_bookings(fake, 50, pitches, users)  # Create 50 bookings
        self.stdout.write(f'Created {len(bookings)} bookings')

        # Create payments
        self.stdout.write('Creating payments...')
        self.create_payments(fake, bookings)
        self.stdout.write('Created payments for bookings')

        # Create reviews
        self.stdout.write('Creating reviews...')
        self.create_reviews(fake, 30, pitches, users)  # Create 30 reviews
        self.stdout.write('Created reviews')

        # Create tournaments
        self.stdout.write('Creating tournaments...')
        tournaments = self.create_tournaments(fake, 10, pitches, users)  # Create 10 tournaments
        self.stdout.write(f'Created {len(tournaments)} tournaments')

        # Create tournament teams
        self.stdout.write('Creating tournament teams...')
        self.create_tournament_teams(fake, tournaments, users)
        self.stdout.write('Created tournament teams')

        # Create messages
        self.stdout.write('Creating messages...')
        self.create_messages(fake, 20, users)  # Create 20 messages
        self.stdout.write('Created messages')

        # Create promotions
        self.stdout.write('Creating promotions...')
        self.create_promotions(fake, options['promotions'])
        self.stdout.write(f'Created {options["promotions"]} promotions')

        # Create system settings
        self.stdout.write('Creating system settings...')
        self.create_system_settings()
        self.stdout.write('Created system settings')

        self.stdout.write(
            self.style.SUCCESS(
                'Successfully created all sample data'
            )
        )

    def create_users(self, fake, count):
        users = []
        
        # DEBUG: Add logging to understand the issue
        self.stdout.write(f'DEBUG: Custom User model being used: {User}')
        self.stdout.write(f'DEBUG: Custom User._meta.app_label: {User._meta.app_label}')
        self.stdout.write(f'DEBUG: Custom User._meta.model_name: {User._meta.model_name}')
        self.stdout.write(f'DEBUG: Django User model: {DjangoUser}')
        self.stdout.write(f'DEBUG: Django User._meta.app_label: {DjangoUser._meta.app_label}')
        self.stdout.write(f'DEBUG: Django User._meta.model_name: {DjangoUser._meta.model_name}')
        
        # Check if User model has the expected fields
        try:
            self.stdout.write(f'DEBUG: Custom User model fields: {[field.name for field in User._meta.get_fields()]}')
            self.stdout.write(f'DEBUG: Django User model fields: {[field.name for field in DjangoUser._meta.get_fields()]}')
        except Exception as e:
            self.stdout.write(f'DEBUG: Error getting User fields: {e}')
        
        # Create admin user
        admin = User.objects.create_user(
            username='admin',
            email='admin@kickzone.com',
            password='admin123',
            user_type='admin',
            phone_number='01234567890',
            is_staff=True,
            is_superuser=True
        )
        users.append(admin)
        
        # Create pitch owners
        for i in range(count // 4):
            username = f'owner_{i+1}_{fake.random_number(digits=4, fix_len=True)}'
            owner = User.objects.create_user(
                username=username,
                email=f'owner_{i+1}@example.com',
                password='password123',
                user_type='owner',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                phone_number=fake.egyptian_phone_number()
            )
            users.append(owner)
        
        # Create players
        for i in range(count - (count // 4) - 1):  # -1 for admin
            username = f'player_{i+1}_{fake.random_number(digits=4, fix_len=True)}'
            player = User.objects.create_user(
                username=username,
                email=f'player_{i+1}@example.com',
                password='password123',
                user_type='player',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                phone_number=fake.egyptian_phone_number()
            )
            users.append(player)
        
        return users

    def create_pitches(self, fake, count, users):
        pitches = []
        owners = [user for user in users if user.user_type == 'owner']
        
        pitch_names = [
            'City Football Arena', 'Metro Sports Complex', 'Greenfield Pitch',
            'Urban Soccer Center', 'Premier Football Field', 'Elite Sports Arena',
            'Community Sports Park', 'Champions Football Ground', 'Victory Pitch',
            'All-Star Sports Complex', 'Dynamic Football Field', 'Pro Soccer Arena',
            'National Sports Center', 'International Football Ground', 'World Cup Pitch'
        ]
        
        for i in range(count):
            owner = random.choice(owners)
            pitch = Pitch.objects.create(
                name=random.choice(pitch_names) + f' {i+1}',
                description=fake.text(max_nb_chars=200),
                location=fake.address(),
                latitude=Decimal(str(fake.latitude())),
                longitude=Decimal(str(fake.longitude())),
                surface_type=random.choice(['turf', 'grass', 'indoor', 'other']),
                size=random.choice(['5v5', '7v7', '11v11', 'Futsal']),
                price_per_hour=Decimal(str(round(random.uniform(20, 100), 2))),
                owner=owner
            )
            pitches.append(pitch)
        
        return pitches

    def create_pitch_availabilities(self, pitches):
        for pitch in pitches:
            for day in range(7):  # Monday to Sunday
                opening_time = time(random.randint(8, 10), 0)
                closing_time = time(random.randint(18, 22), 0)
                
                PitchAvailability.objects.create(
                    pitch=pitch,
                    day_of_week=day,
                    opening_time=opening_time,
                    closing_time=closing_time,
                    is_available=random.choice([True, True, True, False])  # 75% chance of being available
                )

    def create_bookings(self, fake, count, pitches, users):
        bookings = []
        players = [user for user in users if user.user_type == 'player']
        
        for _ in range(count):
            pitch = random.choice(pitches)
            player = random.choice(players)
            
            # Create a date within the next 30 days
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=30)
            booking_date = fake.date_between(start_date=start_date, end_date=end_date)
            
            # Get availability for the day
            day_of_week = booking_date.weekday()
            availability = pitch.availabilities.filter(day_of_week=day_of_week, is_available=True).first()
            
            if availability:
                # Create booking time within availability hours
                start_hour = availability.opening_time.hour
                end_hour = availability.closing_time.hour - 1
                
                if start_hour < end_hour:
                    start_time = time(random.randint(start_hour, end_hour), random.choice([0, 30]))
                    end_time = (datetime.combine(booking_date, start_time) + timedelta(hours=random.randint(1, 3))).time()
                    
                    # Calculate total price
                    hours = (datetime.combine(booking_date, end_time) - datetime.combine(booking_date, start_time)).total_seconds() / 3600
                    total_price = pitch.price_per_hour * Decimal(str(hours))
                    
                    booking = Booking.objects.create(
                        pitch=pitch,
                        player=player,
                        date=booking_date,
                        start_time=start_time,
                        end_time=end_time,
                        status=random.choice(['pending', 'confirmed', 'cancelled', 'completed']),
                        total_price=total_price
                    )
                    bookings.append(booking)
        
        return bookings

    def create_payments(self, fake, bookings):
        for booking in bookings:
            Payment.objects.create(
                booking=booking,
                amount=booking.total_price,
                status=random.choice(['pending', 'completed', 'failed', 'refunded']),
                payment_method=random.choice(['credit_card', 'paypal', 'stripe', 'cash']),
                transaction_id=fake.uuid4() if random.random() > 0.3 else None
            )

    def create_reviews(self, fake, count, pitches, users):
        players = [user for user in users if user.user_type == 'player']
        
        for _ in range(count):
            pitch = random.choice(pitches)
            player = random.choice(players)
            
            # Only create review if player has booked this pitch
            if Booking.objects.filter(player=player, pitch=pitch, status='completed').exists():
                Review.objects.create(
                    pitch=pitch,
                    player=player,
                    rating=random.randint(1, 5),
                    comment=fake.text(max_nb_chars=300) if random.random() > 0.3 else None
                )

    def create_tournaments(self, fake, count, pitches, users):
        tournaments = []
        owners = [user for user in users if user.user_type == 'owner']
        
        tournament_names = [
            'Champions Cup', 'Premier League', 'World Cup Qualifiers',
            'National Championship', 'International Tournament', 'Regional Cup',
            'City League', 'State Championship', 'National Cup', 'International Cup'
        ]
        
        for i in range(count):
            organizer = random.choice(owners)
            pitch = random.choice(pitches)
            
            start_date = fake.date_between(start_date='today', end_date='+60d')
            end_date = start_date + timedelta(days=random.randint(1, 7))
            
            tournament = Tournament.objects.create(
                name=f'{random.choice(tournament_names)} {i+1}',
                description=fake.text(max_nb_chars=300),
                pitch=pitch,
                organizer=organizer,
                date=start_date,
                start_time=time(random.randint(9, 12), 0),
                end_time=time(random.randint(17, 20), 0),
                max_teams=random.randint(4, 16),
                registration_fee=Decimal(str(round(random.uniform(0, 100), 2))),
                registration_deadline=start_date - timedelta(days=random.randint(7, 30))
            )
            tournaments.append(tournament)
        
        return tournaments

    def create_tournament_teams(self, fake, tournaments, users):
        players = [user for user in users if user.user_type == 'player']
        
        for tournament in tournaments:
            num_teams = random.randint(2, min(tournament.max_teams or 8, 8))
            
            for i in range(num_teams):
                captain = random.choice(players)
                
                team = TournamentTeam.objects.create(
                    tournament=tournament,
                    name=f'{fake.company()} FC {i+1}',
                    captain=captain,
                    contact_email=fake.email(),
                    contact_phone=fake.egyptian_phone_number()
                )

    def create_messages(self, fake, count, users):
        for _ in range(count):
            sender = random.choice(users)
            recipient = random.choice(users)
            
            # Don't send message to self
            while recipient == sender:
                recipient = random.choice(users)
            
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                content=fake.text(max_nb_chars=500),
                is_read=random.choice([True, False])
            )

    def create_promotions(self, fake, count):
        for i in range(count):
            Promotion.objects.create(
                code=fake.unique.lexify(text='??????').upper(),
                description=fake.sentence(),
                discount_percentage=random.randint(10, 50),
                max_uses=random.randint(10, 100),
                current_uses=random.randint(0, 20),
                valid_from=fake.date_time_between(start_date='-30d', end_date='now'),
                valid_until=fake.date_time_between(start_date='now', end_date='+90d')
            )

    def create_system_settings(self):
        settings = [
            {'key': 'site_name', 'value': 'KickZone', 'description': 'Name of the football booking site'},
            {'key': 'contact_email', 'value': 'support@kickzone.com', 'description': 'Support email address'},
            {'key': 'contact_phone', 'value': '01234567890', 'description': 'Support phone number'},
            {'key': 'currency', 'value': 'EGP', 'description': 'Default currency for bookings'},
            {'key': 'booking_cancellation_hours', 'value': '24', 'description': 'Hours before booking that cancellation is free'},
            {'key': 'min_booking_hours', 'value': '1', 'description': 'Minimum booking duration in hours'},
            {'key': 'max_booking_hours', 'value': '4', 'description': 'Maximum booking duration in hours'},
        ]
        
        for setting in settings:
            SystemSetting.objects.get_or_create(
                key=setting['key'],
                defaults={
                    'value': setting['value'],
                    'description': setting['description']
                }
            )
