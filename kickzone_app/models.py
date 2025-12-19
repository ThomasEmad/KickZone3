from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('player', 'Player'),
        ('owner', 'Pitch Owner'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='player')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    
    # Simplified profile fields
    Position = models.CharField(max_length=50, blank=True, null=True)
    Skill_Level = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    reserved_hours = models.IntegerField(default=0)
    
    # Presence tracking
    last_activity = models.DateTimeField(blank=True, null=True)
    is_online = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    surface_type = models.CharField(max_length=10, choices=SURFACE_TYPE_CHOICES)
    size = models.CharField(max_length=50, blank=True, null=True)
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='pitch_images/', blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pitches')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class PitchAvailability(models.Model):
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)])  # 0=Monday, 6=Sunday
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    is_available = models.BooleanField(default=True)

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

    def __str__(self):
        return f"{self.pitch.name} - {self.date} {self.start_time} - {self.player.username}"

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

    def __str__(self):
        return f"Payment for {self.booking} - {self.status}"

class Review(models.Model):
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, related_name='reviews')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for {self.pitch.name} by {self.player.username}"

class Tournament(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
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

    def __str__(self):
        return self.name

class TournamentTeam(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=100)
    captain = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teams')
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.tournament.name}"

class MessageGroup(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, related_name='group_memberships')
    is_private = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Group: {self.name}"
    
    def get_member_count(self):
        return self.members.count()

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', blank=True, null=True)
    group = models.ForeignKey(MessageGroup, on_delete=models.CASCADE, related_name='messages', blank=True, null=True)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.group:
            return f"Group message from {self.sender.username} to {self.group.name}"
        elif self.recipient:
            return f"Message from {self.sender.username} to {self.recipient.username}"
        else:
            return f"Message from {self.sender.username} to Support"

class Promotion(models.Model):
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    discount_percentage = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_uses = models.IntegerField(blank=True, null=True)
    current_uses = models.IntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    def is_valid(self):
        now = timezone.now()
        if self.valid_from <= now <= self.valid_until:
            if self.max_uses is None or self.current_uses < self.max_uses:
                return True
        return False

class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
