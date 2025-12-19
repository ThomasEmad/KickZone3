from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Pitch, PitchAvailability, Booking, Payment, Review, Tournament, TournamentTeam, Message, MessageGroup, Promotion, SystemSetting

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    is_online = serializers.BooleanField(read_only=True)
    last_seen = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'user_type', 
                 'phone_number', 'profile_image', 'Position', 'Skill_Level', 'reserved_hours',
                 'is_online', 'last_seen', 'date_joined', 'created_at', 'updated_at']
        read_only_fields = ['id', 'date_joined', 'created_at', 'updated_at']
    
    def get_last_seen(self, obj):
        if obj.last_activity:
            return obj.last_activity.strftime('%Y-%m-%d %H:%M:%S')
        return None

class PitchAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PitchAvailability
        fields = ['id', 'day_of_week', 'opening_time', 'closing_time', 'is_available']

class PitchSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    availabilities = PitchAvailabilitySerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = Pitch
        fields = ['id', 'name', 'description', 'location', 'latitude', 'longitude', 
                 'surface_type', 'size', 'price_per_hour', 'image', 'owner', 
                 'availabilities', 'average_rating', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0

class BookingSerializer(serializers.ModelSerializer):
    pitch = PitchSerializer(read_only=True)
    player = UserSerializer(read_only=True)
    payment = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = ['id', 'pitch', 'player', 'date', 'start_time', 'end_time', 
                 'status', 'total_price', 'payment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_price', 'created_at', 'updated_at']
    
    def get_payment(self, obj):
        try:
            return PaymentSerializer(obj.payment).data
        except Payment.DoesNotExist:
            return None

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'amount', 'status', 'payment_method', 
                 'transaction_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ReviewSerializer(serializers.ModelSerializer):
    pitch = PitchSerializer(read_only=True)
    player = UserSerializer(read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'pitch', 'player', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class TournamentTeamSerializer(serializers.ModelSerializer):
    captain = UserSerializer(read_only=True)
    
    class Meta:
        model = TournamentTeam
        fields = ['id', 'name', 'captain', 'contact_email', 'contact_phone', 'created_at']
        read_only_fields = ['id', 'created_at']

class TournamentSerializer(serializers.ModelSerializer):
    pitch = PitchSerializer(read_only=True)
    organizer = UserSerializer(read_only=True)
    teams = TournamentTeamSerializer(many=True, read_only=True)
    
    class Meta:
        model = Tournament
        fields = ['id', 'name', 'description', 'pitch', 'organizer', 'date', 
                 'start_time', 'end_time', 'max_teams', 'registration_fee', 
                 'registration_deadline', 'teams', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class MessageGroupSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    members = UserSerializer(many=True, read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = MessageGroup
        fields = ['id', 'name', 'description', 'creator', 'members', 'member_count', 
                 'is_private', 'created_at', 'updated_at']
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)
    group = MessageGroupSerializer(read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'recipient', 'group', 'content', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']

class PromotionSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Promotion
        fields = ['id', 'code', 'description', 'discount_percentage', 'max_uses', 
                 'current_uses', 'valid_from', 'valid_until', 'is_valid', 
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'current_uses', 'created_at', 'updated_at']

class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = ['id', 'key', 'value', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
