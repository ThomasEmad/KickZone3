from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from .validators import ValidationMixin, SafeTextValidator, PhoneNumberValidator, ImageFileValidator, PromotionCodeValidator
import re
import logging

# Configure model validation logger
model_validation_logger = logging.getLogger('kickzone.models.validation')


class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('player', 'Player'),
        ('owner', 'Pitch Owner'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='player')
    phone_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        validators=[PhoneNumberValidator()]
    )
    profile_image = models.ImageField(
        upload_to='profile_images/', 
        blank=True, 
        null=True,
        validators=[ImageFileValidator(max_size_mb=3)]
    )
    
    # Simplified profile fields
    Position = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        validators=[RegexValidator(regex=r'^[a-zA-Z\s]{2,50}$', message='Position must be 2-50 letters and spaces only.')]
    )
    Skill_Level = models.IntegerField(
        default=1, 
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    reserved_hours = models.IntegerField(default=0)
    
    # Presence tracking
    last_activity = models.DateTimeField(blank=True, null=True)
    is_online = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        """Comprehensive model-level validation"""
        super().clean()
        
        # Sanitize user data
        if self.username:
            self.username = self.username.strip().lower()
            if not ValidationMixin.validate_username(self.username):
                raise ValidationError({
                    'username': 'Username must be 3-30 characters long and contain only letters, numbers, and underscores.'
                })
        
        if self.first_name:
            self.first_name = ValidationMixin.sanitize_html(self.first_name.strip())
            if not ValidationMixin.validate_text_length(self.first_name, 1, 50):
                raise ValidationError({
                    'first_name': 'First name must be between 1 and 50 characters.'
                })
        
        if self.last_name:
            self.last_name = ValidationMixin.sanitize_html(self.last_name.strip())
            if not ValidationMixin.validate_text_length(self.last_name, 1, 50):
                raise ValidationError({
                    'last_name': 'Last name must be between 1 and 50 characters.'
                })
        
        if self.email:
            self.email = self.email.strip().lower()
            if not ValidationMixin.validate_email(self.email):
                raise ValidationError({
                    'email': 'Please enter a valid email address.'
                })
        
        if self.phone_number:
            clean_phone = re.sub(r'[^\d+]', '', self.phone_number)
            if not ValidationMixin.validate_phone_number(clean_phone):
                raise ValidationError({
                    'phone_number': 'Please enter a valid phone number (7-15 digits).'
                })
            self.phone_number = clean_phone
        
        if self.Position:
            self.Position = ValidationMixin.sanitize_html(self.Position.strip())
            if not re.match(r'^[a-zA-Z\s]{2,50}$', self.Position):
                raise ValidationError({
                    'Position': 'Position must be 2-50 characters and contain only letters and spaces.'
                })
        
        if self.Skill_Level is not None:
            if not ValidationMixin.validate_skill_level(self.Skill_Level):
                raise ValidationError({
                    'Skill_Level': 'Skill level must be between 1 and 100.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='User',
            entity_id=self.pk or 0,
            user_id=self.pk
        )
    
    def calculate_reserved_hours(self):
        """Calculate total reserved hours from confirmed and completed bookings"""
        from datetime import datetime, timedelta
        total_hours = 0
        
        # Get all confirmed and completed bookings for this user
        bookings = self.bookings.filter(status__in=['confirmed', 'completed'])
        
        for booking in bookings:
            # Calculate duration in hours
            start_datetime = datetime.combine(booking.date, booking.start_time)
            end_datetime = datetime.combine(booking.date, booking.end_time)
            duration_hours = (end_datetime - start_datetime).total_seconds() / 3600
            total_hours += duration_hours
        
        return int(total_hours)
    
    def update_reserved_hours(self):
        """Update the reserved_hours field based on current bookings"""
        self.reserved_hours = self.calculate_reserved_hours()
        self.save(update_fields=['reserved_hours'])
    
    def save(self, *args, **kwargs):
        # Update is_online based on last_activity
        if self.last_activity:
            from django.utils import timezone
            from datetime import timedelta
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            self.is_online = self.last_activity >= five_minutes_ago
        else:
            self.is_online = False
        super().save(*args, **kwargs)


class Pitch(models.Model):
    SURFACE_TYPE_CHOICES = (
        ('turf', 'Artificial Turf'),
        ('grass', 'Natural Grass'),
        ('indoor', 'Indoor'),
        ('other', 'Other'),
    )
    name = models.CharField(
        max_length=100,
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s\-_]{2,100}$', message='Name must be 2-100 characters with letters, numbers, spaces, hyphens, and underscores only.')]
    )
    description = models.TextField(
        blank=True, 
        null=True,
        validators=[SafeTextValidator(max_length=1000)]
    )
    location = models.CharField(
        max_length=255,
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s\-_,.]{5,255}$', message='Location must be 5-255 characters with valid address format.')]
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    surface_type = models.CharField(max_length=10, choices=SURFACE_TYPE_CHOICES)
    size = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\sx\-]{2,50}$', message='Size must be 2-50 characters with valid format.')]
    )
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(
        upload_to='pitch_images/', 
        blank=True, 
        null=True,
        validators=[ImageFileValidator(max_size_mb=5)]
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pitches')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for Pitch"""
        super().clean()
        
        # Sanitize text fields
        if self.name:
            self.name = self.name.strip()
            if not ValidationMixin.validate_text_length(self.name, 2, 100):
                raise ValidationError({
                    'name': 'Pitch name must be between 2 and 100 characters.'
                })
        
        if self.description:
            self.description = ValidationMixin.sanitize_html(self.description.strip())
            if not ValidationMixin.validate_text_length(self.description, 0, 1000):
                raise ValidationError({
                    'description': 'Description must be between 0 and 1000 characters.'
                })
        
        if self.location:
            self.location = self.location.strip()
            if not ValidationMixin.validate_text_length(self.location, 5, 255):
                raise ValidationError({
                    'location': 'Location must be between 5 and 255 characters.'
                })
        
        if self.size:
            self.size = self.size.strip().upper()
        
        # Validate coordinates if provided
        if self.latitude is not None and self.longitude is not None:
            if not ValidationMixin.validate_coordinates(self.latitude, self.longitude):
                raise ValidationError({
                    'latitude': 'Invalid coordinates. Latitude must be between -90 and 90, longitude between -180 and 180.'
                })
        
        # Validate price
        if self.price_per_hour is not None:
            if not ValidationMixin.validate_price(self.price_per_hour):
                raise ValidationError({
                    'price_per_hour': 'Price per hour must be a positive number.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='Pitch',
            entity_id=self.pk or 0,
            user_id=self.owner_id
        )

    def __str__(self):
        return self.name


class PitchAvailability(models.Model):
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)])  # 0=Monday, 6=Sunday
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    is_available = models.BooleanField(default=True)

    def clean(self):
        """Validate time range for availability"""
        super().clean()
        
        if self.opening_time and self.closing_time:
            if not ValidationMixin.validate_time_range(
                self.opening_time.strftime('%H:%M'),
                self.closing_time.strftime('%H:%M')
            ):
                raise ValidationError({
                    'closing_time': 'Closing time must be after opening time.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='PitchAvailability',
            entity_id=self.pk or 0,
            user_id=None
        )

    def __str__(self):
        return f"{self.pitch.name} - {self.get_day_of_week_display()}"


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    )
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name='bookings')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for Booking"""
        super().clean()
        
        # Validate date is not in the past (with some tolerance)
        if self.date:
            if not ValidationMixin.validate_future_date(self.date):
                raise ValidationError({
                    'date': 'Booking date cannot be in the past.'
                })
        
        # Validate time range
        if self.start_time and self.end_time:
            if not ValidationMixin.validate_time_range(
                self.start_time.strftime('%H:%M'),
                self.end_time.strftime('%H:%M')
            ):
                raise ValidationError({
                    'end_time': 'End time must be after start time.'
                })
            
            # Ensure minimum booking duration (e.g., 1 hour)
            from datetime import datetime, time
            start_dt = datetime.combine(self.date, self.start_time)
            end_dt = datetime.combine(self.date, self.end_time)
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
            
            if duration_hours < 0.5:  # Minimum 30 minutes
                raise ValidationError({
                    'end_time': 'Booking duration must be at least 30 minutes.'
                })
        
        # Validate price calculation
        if self.pitch and self.total_price is not None:
            expected_price = float(self.pitch.price_per_hour)
            if hasattr(self, '_duration_hours'):
                expected_price *= self._duration_hours
            
            if float(self.total_price) < 0:
                raise ValidationError({
                    'total_price': 'Total price cannot be negative.'
                })
        
        # Check for conflicting bookings
        if self.pitch and self.date and self.start_time and self.end_time and self.pk is None:
            conflicting_bookings = Booking.objects.filter(
                pitch=self.pitch,
                date=self.date,
                status__in=['confirmed', 'pending']
            ).exclude(pk=self.pk)
            
            for booking in conflicting_bookings:
                if (self.start_time < booking.end_time and self.end_time > booking.start_time):
                    raise ValidationError({
                        'date': 'This time slot conflicts with an existing booking.'
                    })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='Booking',
            entity_id=self.pk or 0,
            user_id=self.player_id
        )

    def save(self, *args, **kwargs):
        # Calculate duration and price before saving
        if self.start_time and self.end_time and self.pitch:
            from datetime import datetime
            start_dt = datetime.combine(self.date, self.start_time)
            end_dt = datetime.combine(self.date, self.end_time)
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
            self._duration_hours = duration_hours
            self.total_price = float(self.pitch.price_per_hour) * duration_hours
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.pitch.name} - {self.date} {self.start_time} - {self.player.username}"
    
    def should_be_completed(self):
        """Check if this booking should be automatically completed based on date and time"""
        from django.utils import timezone
        from datetime import datetime, time
        
        # Get current datetime
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        
        # If booking date has passed
        if self.date < current_date:
            return True
        
        # If booking is today but end time has passed
        if self.date == current_date and self.end_time <= current_time:
            return True
            
        return False
    
    def update_status_if_needed(self):
        """Update booking status if it should be completed"""
        if self.status == 'pending' and self.should_be_completed():
            self.status = 'completed'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False
    
    @classmethod
    def update_expired_bookings(cls):
        """Update all expired bookings to completed status"""
        from django.utils import timezone
        from datetime import datetime, time
        
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        
        # Find bookings that should be completed
        expired_bookings = cls.objects.filter(
            status='pending'
        ).filter(
            # Date has passed OR (date is today AND end time has passed)
            models.Q(date__lt=current_date) |
            models.Q(date=current_date, end_time__lte=current_time)
        )
        
        updated_count = 0
        for booking in expired_bookings:
            booking.status = 'completed'
            booking.save(update_fields=['status', 'updated_at'])
            updated_count += 1
        
        return updated_count


class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for Payment"""
        super().clean()
        
        # Validate amount
        if self.amount is not None:
            if not ValidationMixin.validate_price(self.amount):
                raise ValidationError({
                    'amount': 'Amount must be a positive number.'
                })
        
        # Validate transaction ID format if provided
        if self.transaction_id:
            if not re.match(r'^[a-zA-Z0-9\-_]{10,100}$', self.transaction_id):
                raise ValidationError({
                    'transaction_id': 'Transaction ID must be 10-100 characters with letters, numbers, hyphens, and underscores only.'
                })
        
        # Validate payment method
        if self.payment_method:
            allowed_methods = ['credit_card', 'debit_card', 'paypal', 'bank_transfer', 'cash']
            if self.payment_method not in allowed_methods:
                raise ValidationError({
                    'payment_method': f'Payment method must be one of: {", ".join(allowed_methods)}'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='Payment',
            entity_id=self.pk or 0,
            user_id=self.booking.player_id if self.booking else None
        )

    def __str__(self):
        return f"Payment for {self.booking} - {self.status}"


class Review(models.Model):
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name='reviews')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(
        blank=True, 
        null=True,
        validators=[SafeTextValidator(max_length=500)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for Review"""
        super().clean()
        
        # Validate rating
        if self.rating is not None:
            if not ValidationMixin.validate_rating(self.rating):
                raise ValidationError({
                    'rating': 'Rating must be between 1 and 5.'
                })
        
        # Validate comment
        if self.comment:
            self.comment = ValidationMixin.sanitize_html(self.comment.strip())
            if not ValidationMixin.validate_text_length(self.comment, 0, 500):
                raise ValidationError({
                    'comment': 'Comment must be between 0 and 500 characters.'
                })
        
        # Check if user has already reviewed this pitch
        if self.pitch and self.player and self.pk is None:
            existing_review = Review.objects.filter(
                pitch=self.pitch,
                player=self.player
            ).first()
            if existing_review:
                raise ValidationError({
                    'player': 'You have already reviewed this pitch.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='Review',
            entity_id=self.pk or 0,
            user_id=self.player_id
        )

    def __str__(self):
        return f"Review for {self.pitch.name} by {self.player.username}"


class Tournament(models.Model):
    name = models.CharField(
        max_length=100,
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s\-_]{2,100}$', message='Name must be 2-100 characters with letters, numbers, spaces, hyphens, and underscores only.')]
    )
    description = models.TextField(
        blank=True, 
        null=True,
        validators=[SafeTextValidator(max_length=1000)]
    )
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name='tournaments')
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_tournaments')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_teams = models.IntegerField(blank=True, null=True)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    registration_deadline = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for Tournament"""
        super().clean()
        
        # Sanitize text fields
        if self.name:
            self.name = self.name.strip()
            if not ValidationMixin.validate_text_length(self.name, 2, 100):
                raise ValidationError({
                    'name': 'Tournament name must be between 2 and 100 characters.'
                })
        
        if self.description:
            self.description = ValidationMixin.sanitize_html(self.description.strip())
            if not ValidationMixin.validate_text_length(self.description, 0, 1000):
                raise ValidationError({
                    'description': 'Description must be between 0 and 1000 characters.'
                })
        
        # Validate dates
        if self.date and self.registration_deadline:
            if self.registration_deadline >= self.date:
                raise ValidationError({
                    'registration_deadline': 'Registration deadline must be before the tournament date.'
                })
        
        # Validate time range
        if self.start_time and self.end_time:
            if not ValidationMixin.validate_time_range(
                self.start_time.strftime('%H:%M'),
                self.end_time.strftime('%H:%M')
            ):
                raise ValidationError({
                    'end_time': 'End time must be after start time.'
                })
        
        # Validate max teams
        if self.max_teams is not None:
            if self.max_teams < 2:
                raise ValidationError({
                    'max_teams': 'Tournament must allow at least 2 teams.'
                })
        
        # Validate registration fee
        if self.registration_fee is not None:
            if not ValidationMixin.validate_price(self.registration_fee):
                raise ValidationError({
                    'registration_fee': 'Registration fee must be a positive number.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='Tournament',
            entity_id=self.pk or 0,
            user_id=self.organizer_id
        )

    def __str__(self):
        return self.name


class TournamentTeam(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(
        max_length=100,
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s\-_]{2,100}$', message='Team name must be 2-100 characters with letters, numbers, spaces, hyphens, and underscores only.')]
    )
    captain = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teams')
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        validators=[PhoneNumberValidator()]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """Comprehensive model-level validation for TournamentTeam"""
        super().clean()
        
        # Validate team name
        if self.name:
            self.name = self.name.strip()
            if not ValidationMixin.validate_text_length(self.name, 2, 100):
                raise ValidationError({
                    'name': 'Team name must be between 2 and 100 characters.'
                })
        
        # Validate email
        if self.contact_email:
            self.contact_email = self.contact_email.strip().lower()
            if not ValidationMixin.validate_email(self.contact_email):
                raise ValidationError({
                    'contact_email': 'Please enter a valid email address.'
                })
        
        # Validate phone
        if self.contact_phone:
            clean_phone = re.sub(r'[^\d+]', '', self.contact_phone)
            if not ValidationMixin.validate_phone_number(clean_phone):
                raise ValidationError({
                    'contact_phone': 'Please enter a valid phone number (7-15 digits).'
                })
            self.contact_phone = clean_phone
        
        # Check if tournament has reached max teams
        if self.tournament and self.tournament.max_teams:
            current_teams = self.tournament.teams.count()
            if current_teams >= self.tournament.max_teams and self.pk is None:
                raise ValidationError({
                    'tournament': f'Tournament has reached the maximum of {self.tournament.max_teams} teams.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='TournamentTeam',
            entity_id=self.pk or 0,
            user_id=self.captain_id
        )

    def __str__(self):
        return f"{self.name} - {self.tournament.name}"


class MessageGroup(models.Model):
    name = models.CharField(
        max_length=255,
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s\-_]{2,255}$', message='Group name must be 2-255 characters with letters, numbers, spaces, hyphens, and underscores only.')]
    )
    description = models.TextField(
        blank=True, 
        null=True,
        validators=[SafeTextValidator(max_length=500)]
    )
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, related_name='group_memberships')
    is_private = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for MessageGroup"""
        super().clean()
        
        # Sanitize text fields
        if self.name:
            self.name = self.name.strip()
            if not ValidationMixin.validate_text_length(self.name, 2, 255):
                raise ValidationError({
                    'name': 'Group name must be between 2 and 255 characters.'
                })
        
        if self.description:
            self.description = ValidationMixin.sanitize_html(self.description.strip())
            if not ValidationMixin.validate_text_length(self.description, 0, 500):
                raise ValidationError({
                    'description': 'Description must be between 0 and 500 characters.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='MessageGroup',
            entity_id=self.pk or 0,
            user_id=self.creator_id
        )

    def __str__(self):
        return f"Group: {self.name}"
    
    def get_member_count(self):
        return self.members.count()


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', blank=True, null=True)
    group = models.ForeignKey(MessageGroup, on_delete=models.CASCADE, related_name='messages', blank=True, null=True)
    content = models.TextField(validators=[SafeTextValidator(max_length=2000)])
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """Comprehensive model-level validation for Message"""
        super().clean()
        
        # Sanitize content
        if self.content:
            self.content = ValidationMixin.sanitize_html(self.content.strip())
            if not ValidationMixin.validate_text_length(self.content, 1, 2000):
                raise ValidationError({
                    'content': 'Message content must be between 1 and 2000 characters.'
                })
        
        # Validate message recipients
        if not self.recipient and not self.group:
            raise ValidationError({
                'recipient': 'Message must have either a recipient or a group.'
            })
        
        if self.recipient and self.group:
            raise ValidationError({
                'recipient': 'Message cannot have both a recipient and a group.'
            })
        
        # Check if user is member of group (if sending to group)
        if self.group and self.sender not in self.group.members.all():
            raise ValidationError({
                'sender': 'You must be a member of the group to send messages.'
            })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='Message',
            entity_id=self.pk or 0,
            user_id=self.sender_id
        )

    def __str__(self):
        if self.group:
            return f"Group message from {self.sender.username} to {self.group.name}"
        elif self.recipient:
            return f"Message from {self.sender.username} to {self.recipient.username}"
        else:
            return f"Message from {self.sender.username} to Support"


class Promotion(models.Model):
    code = models.CharField(
        max_length=20, 
        unique=True,
        validators=[PromotionCodeValidator()]
    )
    description = models.TextField(
        blank=True, 
        null=True,
        validators=[SafeTextValidator(max_length=500)]
    )
    discount_percentage = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_uses = models.IntegerField(blank=True, null=True)
    current_uses = models.IntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for Promotion"""
        super().clean()
        
        # Sanitize description
        if self.description:
            self.description = ValidationMixin.sanitize_html(self.description.strip())
            if not ValidationMixin.validate_text_length(self.description, 0, 500):
                raise ValidationError({
                    'description': 'Description must be between 0 and 500 characters.'
                })
        
        # Validate code format
        if self.code:
            self.code = self.code.strip().upper()
            if not ValidationMixin.validate_promotion_code(self.code):
                raise ValidationError({
                    'code': 'Promotion code must be 3-20 characters with letters, numbers, hyphens, and underscores only.'
                })
        
        # Validate date range
        if self.valid_from and self.valid_until:
            if self.valid_from >= self.valid_until:
                raise ValidationError({
                    'valid_until': 'Valid until date must be after valid from date.'
                })
        
        # Validate max uses
        if self.max_uses is not None:
            if self.max_uses < 1:
                raise ValidationError({
                    'max_uses': 'Maximum uses must be at least 1.'
                })
        
        # Validate discount percentage
        if self.discount_percentage is not None:
            if not ValidationMixin.validate_percentage(self.discount_percentage):
                raise ValidationError({
                    'discount_percentage': 'Discount percentage must be between 1 and 100.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='Promotion',
            entity_id=self.pk or 0,
            user_id=None
        )

    def __str__(self):
        return self.code

    def is_valid(self):
        now = timezone.now()
        if self.valid_from <= now <= self.valid_until:
            if self.max_uses is None or self.current_uses < self.max_uses:
                return True
        return False


class SystemSetting(models.Model):
    key = models.CharField(
        max_length=100, 
        unique=True,
        validators=[RegexValidator(regex=r'^[a-zA-Z0-9_.]{3,100}$', message='Key must be 3-100 characters with letters, numbers, dots, and underscores only.')]
    )
    value = models.TextField()
    description = models.TextField(
        blank=True, 
        null=True,
        validators=[SafeTextValidator(max_length=500)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Comprehensive model-level validation for SystemSetting"""
        super().clean()
        
        # Sanitize key
        if self.key:
            self.key = self.key.strip().lower()
            if not ValidationMixin.validate_text_length(self.key, 3, 100):
                raise ValidationError({
                    'key': 'Key must be between 3 and 100 characters.'
                })
        
        # Sanitize description
        if self.description:
            self.description = ValidationMixin.sanitize_html(self.description.strip())
            if not ValidationMixin.validate_text_length(self.description, 0, 500):
                raise ValidationError({
                    'description': 'Description must be between 0 and 500 characters.'
                })
        
        # Log successful validation
        ValidationMixin.log_validation_success(
            operation='model_validation',
            entity='SystemSetting',
            entity_id=self.pk or 0,
            user_id=None
        )

    def __str__(self):
        return self.key
