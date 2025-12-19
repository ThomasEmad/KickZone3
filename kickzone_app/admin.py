from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Pitch, PitchAvailability, Booking, Payment, Review, Tournament, TournamentTeam, Message, Promotion, SystemSetting

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'phone_number')
    list_filter = ('user_type', 'is_staff', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('user_type', 'phone_number', 'profile_image')}),
    )

@admin.register(Pitch)
class PitchAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'surface_type', 'price_per_hour', 'owner')
    list_filter = ('surface_type', 'owner')
    search_fields = ('name', 'location', 'description')

@admin.register(PitchAvailability)
class PitchAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('pitch', 'day_of_week', 'opening_time', 'closing_time', 'is_available')
    list_filter = ('day_of_week', 'is_available')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('pitch', 'player', 'date', 'start_time', 'end_time', 'status', 'total_price')
    list_filter = ('status', 'date')
    search_fields = ('pitch__name', 'player__username')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('booking', 'amount', 'status', 'payment_method', 'transaction_id')
    list_filter = ('status', 'payment_method')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('pitch', 'player', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('pitch__name', 'player__username', 'comment')

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'pitch', 'organizer', 'date', 'max_teams', 'registration_fee')
    list_filter = ('date',)
    search_fields = ('name', 'description')

@admin.register(TournamentTeam)
class TournamentTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'tournament', 'captain', 'created_at')
    list_filter = ('tournament',)
    search_fields = ('name', 'captain__username')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'recipient__username', 'content')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percentage', 'current_uses', 'max_uses', 'valid_from', 'valid_until')
    list_filter = ('valid_from', 'valid_until')
    search_fields = ('code', 'description')

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description')
    search_fields = ('key', 'description')
