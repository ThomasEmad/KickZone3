from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, date, time, timedelta
from .models import Pitch, PitchAvailability, Booking, Payment, Review, Tournament, TournamentTeam, Message, MessageGroup, Promotion, SystemSetting
from .validators import ValidationMixin
import logging
import re

User = get_user_model()

# Configure serializer validation logger
serializer_validation_logger = logging.getLogger('kickzone.serializers.validation')


class EnhancedValidationMixin:
    """Mixin to provide enhanced validation methods for serializers"""
    
    @staticmethod
    def validate_business_hours(data, start_field='start_time', end_field='end_time', date_field='date'):
        """Validate business hours for booking-related operations"""
        if start_field in data and end_field in data and date_field in data:
            start_time = data[start_field]
            end_time = data[end_field]
            booking_date = data[date_field]
            
            if start_time and end_time:
                # Ensure end time is after start time
                if end_time <= start_time:
                    raise serializers.ValidationError({
                        end_field: 'End time must be after start time.'
                    })
                
                # Ensure minimum booking duration (30 minutes)
                start_dt = datetime.combine(booking_date, start_time)
                end_dt = datetime.combine(booking_date, end_time)
                duration = (end_dt - start_dt).total_seconds() / 3600
                
                if duration < 0.5:
                    raise serializers.ValidationError({
                        end_field: 'Booking duration must be at least 30 minutes.'
                    })
    
    @staticmethod
    def validate_booking_conflicts(serializer, booking_data, exclude_pk=None):
        """Validate that new booking doesn't conflict with existing bookings"""
        pitch = booking_data.get('pitch')
        date = booking_data.get('date')
        start_time = booking_data.get('start_time')
        end_time = booking_data.get('end_time')
        
        if not all([pitch, date, start_time, end_time]):
            return
        
        # Check for conflicting bookings
        query = Booking.objects.filter(
            pitch=pitch,
            date=date,
            status__in=['confirmed', 'pending']
        )
        
        if exclude_pk:
            query = query.exclude(pk=exclude_pk)
        
        conflicts = []
        for booking in query:
            if (start_time < booking.end_time and end_time > booking.start_time):
                conflicts.append(booking)
        
        if conflicts:
            raise serializers.ValidationError({
                'date': f'This time slot conflicts with {len(conflicts)} existing booking(s).'
            })
    
    @staticmethod
    def validate_user_permissions(user, required_permission, target_user=None, resource=None):
        """Validate user permissions for various operations"""
        if not user or not user.is_authenticated:
            raise serializers.ValidationError('Authentication required.')
        
        # Admin can do everything
        if user.user_type == 'admin':
            return True
        
        # Check specific permissions
        if required_permission == 'create_pitch':
            if user.user_type != 'owner':
                raise serializers.ValidationError('Only pitch owners can create pitches.')
        
        elif required_permission == 'create_tournament':
            if user.user_type not in ['owner', 'admin']:
                raise serializers.ValidationError('Only pitch owners and admins can create tournaments.')
        
        elif required_permission == 'book_pitch':
            if user.user_type not in ['player', 'admin']:
                raise serializers.ValidationError('Only players can book pitches.')
        
        elif required_permission == 'review_pitch':
            if user.user_type not in ['player', 'admin']:
                raise serializers.ValidationError('Only players can review pitches.')
        
        elif required_permission == 'manage_own_resource':
            if resource and hasattr(resource, 'owner') and resource.owner != user:
                if user.user_type != 'admin':
                    raise serializers.ValidationError('You can only manage your own resources.')
        
        return True
    
    @staticmethod
    def validate_promotion_usage(promotion_code, user, booking_amount=None):
        """Validate promotion code usage"""
        if not promotion_code:
            return None
        
        try:
            promotion = Promotion.objects.get(code=promotion_code.upper())
        except Promotion.DoesNotExist:
            raise serializers.ValidationError({
                'promotion_code': 'Invalid promotion code.'
            })
        
        # Check if promotion is valid
        if not promotion.is_valid():
            raise serializers.ValidationError({
                'promotion_code': 'This promotion code is not currently valid.'
            })
        
        # Check if user has already used this promotion
        if hasattr(user, 'used_promotions'):
            if promotion in user.used_promotions.all():
                raise serializers.ValidationError({
                    'promotion_code': 'You have already used this promotion code.'
                })
        
        # Validate minimum booking amount if specified
        if booking_amount is not None:
            if float(booking_amount) < 10.0:  # Minimum booking amount
                raise serializers.ValidationError({
                    'promotion_code': 'Promotion requires a minimum booking amount of $10.00.'
                })
        
        return promotion
    
    @staticmethod
    def calculate_booking_price(pitch, start_time, end_time, date, promotion=None):
        """Calculate booking price with potential discounts"""
        if not all([pitch, start_time, end_time, date]):
            return 0
        
        # Calculate duration
        start_dt = datetime.combine(date, start_time)
        end_dt = datetime.combine(date, end_time)
        duration_hours = (end_dt - start_dt).total_seconds() / 3600
        
        # Base price
        base_price = float(pitch.price_per_hour) * duration_hours
        
        # Apply promotion discount
        if promotion:
            discount = (base_price * promotion.discount_percentage) / 100
            final_price = base_price - discount
        else:
            final_price = base_price
        
        return round(final_price, 2)
    
    @staticmethod
    def validate_tournament_registration(tournament_data, user):
        """Validate tournament team registration"""
        tournament = tournament_data.get('tournament')
        team_name = tournament_data.get('name')
        
        if not tournament or not team_name:
            return
        
        # Check if tournament is open for registration
        if tournament.registration_deadline and timezone.now().date() > tournament.registration_deadline:
            raise serializers.ValidationError({
                'tournament': 'Registration deadline has passed.'
            })
        
        # Check if tournament has reached max teams
        if tournament.max_teams and tournament.teams.count() >= tournament.max_teams:
            raise serializers.ValidationError({
                'tournament': 'Tournament has reached maximum team capacity.'
            })
        
        # Check if user is already registered in this tournament
        if TournamentTeam.objects.filter(tournament=tournament, captain=user).exists():
            raise serializers.ValidationError({
                'captain': 'You are already registered as captain of a team in this tournament.'
            })
    
    @staticmethod
    def validate_message_content(content, max_length=2000):
        """Enhanced message content validation"""
        if not content or not content.strip():
            raise serializers.ValidationError({
                'content': 'Message content cannot be empty.'
            })
        
        # Check length
        if len(content.strip()) > max_length:
            raise serializers.ValidationError({
                'content': f'Message content cannot exceed {max_length} characters.'
            })
        
        # Sanitize content
        sanitized = ValidationMixin.sanitize_html(content.strip())
        if sanitized != content.strip():
            raise serializers.ValidationError({
                'content': 'Message contains potentially dangerous content.'
            })
        
        return sanitized
    
    @staticmethod
    def validate_booking_advance_booking(booking_date, min_advance_hours=1):
        """Validate that booking is made sufficiently in advance"""
        if not booking_date:
            return
        
        now = timezone.now()
        booking_datetime = datetime.combine(booking_date, time.min)
        time_diff = (booking_datetime - now).total_seconds() / 3600
        
        if time_diff < min_advance_hours:
            raise serializers.ValidationError({
                'date': f'Bookings must be made at least {min_advance_hours} hour(s) in advance.'
            })
    
    @staticmethod
    def log_serializer_validation(operation, entity, entity_id, user_id, success=True, details=None):
        """Log serializer validation events"""
        if success:
            serializer_validation_logger.info(
                f"Serializer Validation Success: {operation} | Entity: {entity} | "
                f"ID: {entity_id} | User: {user_id} | Timestamp: {timezone.now()}"
            )
        else:
            serializer_validation_logger.warning(
                f"Serializer Validation Failed: {operation} | Entity: {entity} | "
                f"ID: {entity_id} | User: {user_id} | Details: {details} | Timestamp: {timezone.now()}"
            )


class UserSerializer(serializers.ModelSerializer):
    is_online = serializers.BooleanField(read_only=True)
    last_seen = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'user_type', 
                 'phone_number', 'profile_image', 'Position', 'Skill_Level', 'reserved_hours',
                 'is_online', 'last_seen', 'date_joined', 'created_at', 'updated_at',
                 'password', 'password_confirm']
        read_only_fields = ['id', 'date_joined', 'created_at', 'updated_at', 'is_online', 'reserved_hours']
    
    def validate_username(self, value):
        """Enhanced username validation"""
        if value:
            value = value.strip().lower()
            if not ValidationMixin.validate_username(value):
                raise serializers.ValidationError(
                    'Username must be 3-30 characters long and contain only letters, numbers, and underscores.'
                )
            
            # Check for unique username
            if User.objects.filter(username=value).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError('Username already exists.')
        
        return value
    
    def validate_email(self, value):
        """Enhanced email validation"""
        if value:
            value = value.strip().lower()
            if not ValidationMixin.validate_email(value):
                raise serializers.ValidationError('Please enter a valid email address.')
            
            # Check for unique email
            if User.objects.filter(email=value).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError('Email already exists.')
        
        return value
    
    def validate_phone_number(self, value):
        """Enhanced phone number validation"""
        if value:
            clean_phone = ValidationMixin.sanitize_html(value.strip())
            if not ValidationMixin.validate_phone_number(clean_phone):
                raise serializers.ValidationError('Please enter a valid phone number (7-15 digits).')
        
        return value
    
    def validate_Skill_Level(self, value):
        """Enhanced Skill Level validation"""
        if value is not None:
            try:
                if isinstance(value, str):
                    value = int(value)
                elif not isinstance(value, int):
                    value = int(value)
                
                if not ValidationMixin.validate_skill_level(value):
                    raise serializers.ValidationError("Skill level must be between 1 and 100.")
                    
                return value
            except (ValueError, TypeError):
                raise serializers.ValidationError("Skill level must be a valid integer.")
        return value
    
    def validate_password(self, value):
        """Enhanced password validation"""
        if value:
            if len(value) < 8:
                raise serializers.ValidationError('Password must be at least 8 characters long.')
            
            # Check for complexity
            if not re.search(r'[A-Z]', value):
                raise serializers.ValidationError('Password must contain at least one uppercase letter.')
            if not re.search(r'[a-z]', value):
                raise serializers.ValidationError('Password must contain at least one lowercase letter.')
            if not re.search(r'[0-9]', value):
                raise serializers.ValidationError('Password must contain at least one number.')
        
        return value
    
    def validate(self, data):
        """Cross-field validation for User"""
        # Password confirmation
        if 'password' in data and 'password_confirm' in data:
            if data['password'] != data['password_confirm']:
                raise serializers.ValidationError({
                    'password_confirm': 'Passwords do not match.'
                })
        
        # User type validation
        if 'user_type' in data:
            allowed_types = ['player', 'owner', 'admin']
            if data['user_type'] not in allowed_types:
                raise serializers.ValidationError({
                    'user_type': f'User type must be one of: {", ".join(allowed_types)}'
                })
        
        # Name validation
        for name_field in ['first_name', 'last_name']:
            if name_field in data and data[name_field]:
                data[name_field] = ValidationMixin.sanitize_html(data[name_field].strip())
                if not ValidationMixin.validate_text_length(data[name_field], 1, 50):
                    raise serializers.ValidationError({
                        name_field: f'{name_field.replace("_", " ").title()} must be between 1 and 50 characters.'
                    })
        
        # Position validation
        if 'Position' in data and data['Position']:
            data['Position'] = ValidationMixin.sanitize_html(data['Position'].strip())
            if not re.match(r'^[a-zA-Z\s]{2,50}$', data['Position']):
                raise serializers.ValidationError({
                    'Position': 'Position must be 2-50 characters and contain only letters and spaces.'
                })
        
        return data
    
    def create(self, validated_data):
        """Enhanced user creation with proper password hashing"""
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='user_creation',
            entity='User',
            entity_id=user.pk,
            user_id=user.pk,
            success=True
        )
        
        return user
    
    def update(self, instance, validated_data):
        """Enhanced user update"""
        validated_data.pop('password_confirm', None)
        
        # Handle password update separately
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='user_update',
            entity='User',
            entity_id=instance.pk,
            user_id=instance.pk,
            success=True
        )
        
        return instance
    
    def get_last_seen(self, obj):
        if obj.last_activity:
            return obj.last_activity.strftime('%Y-%m-%d %H:%M:%S')
        return None


class PitchAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PitchAvailability
        fields = ['id', 'day_of_week', 'opening_time', 'closing_time', 'is_available']
    
    def validate_day_of_week(self, value):
        """Validate day of week"""
        if value < 0 or value > 6:
            raise serializers.ValidationError('Day of week must be between 0 (Monday) and 6 (Sunday).')
        return value
    
    def validate(self, data):
        """Cross-field validation for PitchAvailability"""
        EnhancedValidationMixin.validate_business_hours(data, 'opening_time', 'closing_time')
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='pitch_availability_validation',
            entity='PitchAvailability',
            entity_id=data.get('id', 0),
            user_id=self.context.get('request').user.id if self.context.get('request') else None,
            success=True
        )
        
        return data


class PitchSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    availabilities = PitchAvailabilitySerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Pitch
        fields = ['id', 'name', 'description', 'location', 'latitude', 'longitude', 
                 'surface_type', 'size', 'price_per_hour', 'image', 'owner', 
                 'availabilities', 'average_rating', 'is_available', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'owner', 'average_rating', 'is_available']
    
    def validate_name(self, value):
        """Enhanced pitch name validation"""
        if value:
            value = value.strip()
            if not ValidationMixin.validate_text_length(value, 2, 100):
                raise serializers.ValidationError('Pitch name must be between 2 and 100 characters.')
            
            # Check for unique name per owner
            owner = self.context.get('request').user if self.context.get('request') else None
            if owner and Pitch.objects.filter(name=value, owner=owner).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError('You already have a pitch with this name.')
        
        return value
    
    def validate_location(self, value):
        """Enhanced location validation"""
        if value:
            value = value.strip()
            if not ValidationMixin.validate_text_length(value, 5, 255):
                raise serializers.ValidationError('Location must be between 5 and 255 characters.')
        
        return value
    
    def validate_price_per_hour(self, value):
        """Enhanced price validation"""
        try:
            price = float(value)
            if price <= 0:
                raise serializers.ValidationError('Price per hour must be greater than 0.')
            if price > 1000:
                raise serializers.ValidationError('Price per hour seems too high.')
            return price
        except (ValueError, TypeError):
            raise serializers.ValidationError('Price per hour must be a valid number.')
    
    def validate_coordinates(self, data):
        """Validate latitude and longitude together"""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if latitude is not None and longitude is not None:
            if not ValidationMixin.validate_coordinates(latitude, longitude):
                raise serializers.ValidationError({
                    'latitude': 'Invalid coordinates. Latitude must be between -90 and 90, longitude between -180 and 180.'
                })
        
        return data
    
    def validate(self, data):
        """Cross-field validation for Pitch"""
        # Validate coordinates
        self.validate_coordinates(data)
        
        # Validate user permissions
        request = self.context.get('request')
        if request and request.method == 'POST':
            EnhancedValidationMixin.validate_user_permissions(
                request.user, 
                'create_pitch'
            )
        
        # Sanitize text fields
        for field in ['name', 'description', 'location', 'size']:
            if field in data and data[field]:
                data[field] = ValidationMixin.sanitize_html(data[field].strip())
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='pitch_validation',
            entity='Pitch',
            entity_id=data.get('id', 0),
            user_id=request.user.id if request else None,
            success=True
        )
        
        return data
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews:
            return round(sum(review.rating for review in reviews) / len(reviews), 1)
        return 0
    
    def get_is_available(self, obj):
        """Check if pitch has any available time slots"""
        today = date.today()
        current_time = datetime.now().time()
        current_weekday = today.weekday()
        
        # Check if there are future available slots
        return obj.availabilities.filter(
            is_available=True,
            day_of_week=current_weekday,
            closing_time__gt=current_time
        ).exists() or obj.availabilities.filter(
            is_available=True,
            day_of_week__gt=current_weekday
        ).exists()


class BookingSerializer(serializers.ModelSerializer):
    pitch = PitchSerializer(read_only=True)
    player = UserSerializer(read_only=True)
    payment = serializers.SerializerMethodField()
    promotion_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'pitch', 'player', 'date', 'start_time', 'end_time', 
                 'status', 'total_price', 'payment', 'promotion_code', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_price', 'created_at', 'updated_at', 'player', 'status']
    
    def validate_date(self, value):
        """Enhanced date validation"""
        if value:
            # Check if date is in the past
            if value < date.today():
                raise serializers.ValidationError('Booking date cannot be in the past.')
            
            # Check advance booking requirement
            EnhancedValidationMixin.validate_booking_advance_booking(value)
        
        return value
    
    def validate_start_time(self, value):
        """Enhanced start time validation"""
        if value:
            # Business hours validation (example: 6 AM to 10 PM)
            if value < time(6, 0) or value > time(22, 0):
                raise serializers.ValidationError('Booking time must be between 6:00 AM and 10:00 PM.')
        
        return value
    
    def validate_end_time(self, value):
        """Enhanced end time validation"""
        if value:
            # Ensure end time is reasonable
            if value > time(23, 59):
                raise serializers.ValidationError('End time cannot be after midnight.')
        
        return value
    
    def validate(self, data):
        """Cross-field validation for Booking"""
        # Validate business hours
        EnhancedValidationMixin.validate_business_hours(data)
        
        # Validate user permissions
        request = self.context.get('request')
        if request:
            EnhancedValidationMixin.validate_user_permissions(
                request.user, 
                'book_pitch'
            )
            
            # Set player to current user for new bookings
            if not self.instance:
                data['player'] = request.user
        
        # Validate promotion code
        promotion_code = data.get('promotion_code')
        if promotion_code:
            promotion = EnhancedValidationMixin.validate_promotion_usage(
                promotion_code, 
                data.get('player') or request.user,
                data.get('total_price')
            )
            data['promotion'] = promotion
        
        # Calculate and validate price
        if 'pitch' in data and 'start_time' in data and 'end_time' in data and 'date' in data:
            calculated_price = EnhancedValidationMixin.calculate_booking_price(
                data['pitch'],
                data['start_time'],
                data['end_time'],
                data['date'],
                data.get('promotion')
            )
            data['total_price'] = calculated_price
        
        # Check for booking conflicts
        EnhancedValidationMixin.validate_booking_conflicts(
            self, 
            data, 
            exclude_pk=self.instance.pk if self.instance else None
        )
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='booking_validation',
            entity='Booking',
            entity_id=data.get('id', 0),
            user_id=request.user.id if request else None,
            success=True
        )
        
        return data
    
    def get_payment(self, obj):
        try:
            return PaymentSerializer(obj.payment).data
        except Payment.DoesNotExist:
            return None
    
    def create(self, validated_data):
        """Enhanced booking creation"""
        validated_data.pop('promotion_code', None)
        promotion = validated_data.pop('promotion', None)
        
        booking = Booking.objects.create(**validated_data)
        
        # Create payment record
        Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            status='pending'
        )
        
        # Update promotion usage if applicable
        if promotion:
            promotion.current_uses += 1
            promotion.save()
            # Add to user's used promotions (if such relationship exists)
            # booking.player.used_promotions.add(promotion)
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='booking_creation',
            entity='Booking',
            entity_id=booking.pk,
            user_id=booking.player_id,
            success=True
        )
        
        return booking


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'amount', 'status', 'payment_method', 
                 'transaction_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        """Enhanced amount validation"""
        try:
            amount = float(value)
            if amount <= 0:
                raise serializers.ValidationError('Amount must be greater than 0.')
            return amount
        except (ValueError, TypeError):
            raise serializers.ValidationError('Amount must be a valid number.')
    
    def validate_payment_method(self, value):
        """Enhanced payment method validation"""
        if value:
            allowed_methods = ['credit_card', 'debit_card', 'paypal', 'bank_transfer', 'cash']
            if value not in allowed_methods:
                raise serializers.ValidationError(
                    f'Payment method must be one of: {", ".join(allowed_methods)}'
                )
        return value
    
    def validate(self, data):
        """Cross-field validation for Payment"""
        amount = data.get('amount')
        booking = data.get('booking')
        
        # Validate amount matches booking total
        if booking and amount:
            if float(amount) != float(booking.total_price):
                raise serializers.ValidationError({
                    'amount': f'Payment amount must match booking total (${booking.total_price}).'
                })
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='payment_validation',
            entity='Payment',
            entity_id=data.get('id', 0),
            user_id=booking.player_id if booking else None,
            success=True
        )
        
        return data


class ReviewSerializer(serializers.ModelSerializer):
    pitch = PitchSerializer(read_only=True)
    player = UserSerializer(read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'pitch', 'player', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'player']
    
    def validate_rating(self, value):
        """Enhanced rating validation"""
        try:
            rating = int(value)
            if not ValidationMixin.validate_rating(rating):
                raise serializers.ValidationError('Rating must be between 1 and 5.')
            return rating
        except (ValueError, TypeError):
            raise serializers.ValidationError('Rating must be a valid integer.')
    
    def validate_comment(self, value):
        """Enhanced comment validation"""
        if value:
            sanitized = EnhancedValidationMixin.validate_message_content(value, max_length=500)
            return sanitized
        return value
    
    def validate(self, data):
        """Cross-field validation for Review"""
        request = self.context.get('request')
        if request:
            EnhancedValidationMixin.validate_user_permissions(
                request.user, 
                'review_pitch'
            )
            
            # Set player to current user for new reviews
            if not self.instance:
                data['player'] = request.user
        
        pitch = data.get('pitch')
        player = data.get('player')
        
        # Check if user has already reviewed this pitch
        if pitch and player and not self.instance:
            if Review.objects.filter(pitch=pitch, player=player).exists():
                raise serializers.ValidationError({
                    'player': 'You have already reviewed this pitch.'
                })
        
        # Check if user has actually booked this pitch
        if pitch and player:
            has_booked = Booking.objects.filter(
                pitch=pitch, 
                player=player, 
                status__in=['confirmed', 'completed']
            ).exists()
            if not has_booked:
                raise serializers.ValidationError({
                    'pitch': 'You can only review pitches you have booked and played on.'
                })
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='review_validation',
            entity='Review',
            entity_id=data.get('id', 0),
            user_id=request.user.id if request else None,
            success=True
        )
        
        return data


class TournamentTeamSerializer(serializers.ModelSerializer):
    captain = UserSerializer(read_only=True)
    
    class Meta:
        model = TournamentTeam
        fields = ['id', 'name', 'captain', 'contact_email', 'contact_phone', 'created_at']
        read_only_fields = ['id', 'created_at', 'captain']
    
    def validate_name(self, value):
        """Enhanced team name validation"""
        if value:
            value = value.strip()
            if not ValidationMixin.validate_text_length(value, 2, 100):
                raise serializers.ValidationError('Team name must be between 2 and 100 characters.')
        return value
    
    def validate_contact_email(self, value):
        """Enhanced contact email validation"""
        if value:
            value = value.strip().lower()
            if not ValidationMixin.validate_email(value):
                raise serializers.ValidationError('Please enter a valid email address.')
        return value
    
    def validate_contact_phone(self, value):
        """Enhanced contact phone validation"""
        if value:
            clean_phone = ValidationMixin.sanitize_html(value.strip())
            if not ValidationMixin.validate_phone_number(clean_phone):
                raise serializers.ValidationError('Please enter a valid phone number (7-15 digits).')
            return clean_phone
        return value
    
    def validate(self, data):
        """Cross-field validation for TournamentTeam"""
        request = self.context.get('request')
        if request:
            # Set captain to current user
            if not self.instance:
                data['captain'] = request.user
        
        # Validate tournament registration rules
        EnhancedValidationMixin.validate_tournament_registration(data, data.get('captain'))
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='tournament_team_validation',
            entity='TournamentTeam',
            entity_id=data.get('id', 0),
            user_id=request.user.id if request else None,
            success=True
        )
        
        return data


class TournamentSerializer(serializers.ModelSerializer):
    pitch = PitchSerializer(read_only=True)
    organizer = UserSerializer(read_only=True)
    teams = TournamentTeamSerializer(many=True, read_only=True)
    registration_open = serializers.ReadOnlyField()
    team_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Tournament
        fields = ['id', 'name', 'description', 'pitch', 'organizer', 'date', 
                 'start_time', 'end_time', 'max_teams', 'registration_fee', 
                 'registration_deadline', 'teams', 'registration_open', 'team_count',
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'organizer', 'teams', 'registration_open', 'team_count']
    
    def validate_name(self, value):
        """Enhanced tournament name validation"""
        if value:
            value = value.strip()
            if not ValidationMixin.validate_text_length(value, 2, 100):
                raise serializers.ValidationError('Tournament name must be between 2 and 100 characters.')
        return value
    
    def validate_max_teams(self, value):
        """Enhanced max teams validation"""
        if value is not None:
            if value < 2:
                raise serializers.ValidationError('Tournament must allow at least 2 teams.')
            if value > 128:
                raise serializers.ValidationError('Tournament cannot have more than 128 teams.')
        return value
    
    def validate_registration_fee(self, value):
        """Enhanced registration fee validation"""
        try:
            fee = float(value)
            if fee < 0:
                raise serializers.ValidationError('Registration fee cannot be negative.')
            if fee > 1000:
                raise serializers.ValidationError('Registration fee seems too high.')
            return fee
        except (ValueError, TypeError):
            raise serializers.ValidationError('Registration fee must be a valid number.')
    
    def validate(self, data):
        """Cross-field validation for Tournament"""
        request = self.context.get('request')
        if request:
            EnhancedValidationMixin.validate_user_permissions(
                request.user, 
                'create_tournament'
            )
            
            # Set organizer to current user
            if not self.instance:
                data['organizer'] = request.user
        
        # Validate date relationships
        date = data.get('date')
        registration_deadline = data.get('registration_deadline')
        
        if date and registration_deadline:
            if registration_deadline >= date:
                raise serializers.ValidationError({
                    'registration_deadline': 'Registration deadline must be before the tournament date.'
                })
        
        # Validate time relationships
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time.'
                })
        
        # Sanitize text fields
        for field in ['name', 'description']:
            if field in data and data[field]:
                data[field] = ValidationMixin.sanitize_html(data[field].strip())
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='tournament_validation',
            entity='Tournament',
            entity_id=data.get('id', 0),
            user_id=request.user.id if request else None,
            success=True
        )
        
        return data
    
    def get_registration_open(self, obj):
        """Check if registration is currently open"""
        if obj.registration_deadline:
            return timezone.now().date() <= obj.registration_deadline
        return True
    
    def get_team_count(self, obj):
        """Get current team count"""
        return obj.teams.count()


class MessageGroupSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    members = UserSerializer(many=True, read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = MessageGroup
        fields = ['id', 'name', 'description', 'creator', 'members', 'member_count', 
                 'is_private', 'created_at', 'updated_at']
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at', 'members', 'member_count']
    
    def validate_name(self, value):
        """Enhanced group name validation"""
        if value:
            value = value.strip()
            if not ValidationMixin.validate_text_length(value, 2, 255):
                raise serializers.ValidationError('Group name must be between 2 and 255 characters.')
        return value
    
    def validate(self, data):
        """Cross-field validation for MessageGroup"""
        request = self.context.get('request')
        if request:
            # Set creator to current user
            if not self.instance:
                data['creator'] = request.user
        
        # Sanitize text fields
        for field in ['name', 'description']:
            if field in data and data[field]:
                data[field] = ValidationMixin.sanitize_html(data[field].strip())
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='message_group_validation',
            entity='MessageGroup',
            entity_id=data.get('id', 0),
            user_id=request.user.id if request else None,
            success=True
        )
        
        return data


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)
    group = MessageGroupSerializer(read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'recipient', 'group', 'content', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at', 'sender', 'is_read']
    
    def validate_content(self, value):
        """Enhanced content validation"""
        return EnhancedValidationMixin.validate_message_content(value)
    
    def validate(self, data):
        """Cross-field validation for Message"""
        request = self.context.get('request')
        if request:
            # Set sender to current user
            if not self.instance:
                data['sender'] = request.user
        
        recipient = data.get('recipient')
        group = data.get('group')
        
        # Validate message recipients
        if not recipient and not group:
            raise serializers.ValidationError({
                'recipient': 'Message must have either a recipient or a group.'
            })
        
        if recipient and group:
            raise serializers.ValidationError({
                'recipient': 'Message cannot have both a recipient and a group.'
            })
        
        # Check if user is member of group (if sending to group)
        if group and request.user not in group.members.all():
            raise serializers.ValidationError({
                'sender': 'You must be a member of the group to send messages.'
            })
        
        # Prevent self-messaging for certain types
        if recipient and recipient == request.user:
            raise serializers.ValidationError({
                'recipient': 'You cannot send messages to yourself.'
            })
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='message_validation',
            entity='Message',
            entity_id=data.get('id', 0),
            user_id=request.user.id if request else None,
            success=True
        )
        
        return data


class PromotionSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)
    discount_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Promotion
        fields = ['id', 'code', 'description', 'discount_percentage', 'max_uses', 
                 'current_uses', 'valid_from', 'valid_until', 'is_valid', 'discount_amount',
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'current_uses', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        """Enhanced promotion code validation"""
        if value:
            value = value.strip().upper()
            if not ValidationMixin.validate_promotion_code(value):
                raise serializers.ValidationError(
                    'Promotion code must be 3-20 characters with letters, numbers, hyphens, and underscores only.'
                )
            
            # Check for unique code
            if Promotion.objects.filter(code=value).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError('Promotion code already exists.')
        
        return value
    
    def validate_discount_percentage(self, value):
        """Enhanced discount percentage validation"""
        try:
            percentage = int(value)
            if not ValidationMixin.validate_percentage(percentage):
                raise serializers.ValidationError('Discount percentage must be between 1 and 100.')
            return percentage
        except (ValueError, TypeError):
            raise serializers.ValidationError('Discount percentage must be a valid integer.')
    
    def validate_max_uses(self, value):
        """Enhanced max uses validation"""
        if value is not None:
            if value < 1:
                raise serializers.ValidationError('Maximum uses must be at least 1.')
            if value > 10000:
                raise serializers.ValidationError('Maximum uses cannot exceed 10,000.')
        return value
    
    def validate(self, data):
        """Cross-field validation for Promotion"""
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        
        # Validate date range
        if valid_from and valid_until:
            if valid_from >= valid_until:
                raise serializers.ValidationError({
                    'valid_until': 'Valid until date must be after valid from date.'
                })
        
        # Sanitize description
        if 'description' in data and data['description']:
            data['description'] = ValidationMixin.sanitize_html(data['description'].strip())
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='promotion_validation',
            entity='Promotion',
            entity_id=data.get('id', 0),
            user_id=None,
            success=True
        )
        
        return data
    
    def get_discount_amount(self, obj):
        """Calculate discount amount for a standard booking (example: $100)"""
        standard_booking_amount = 100.00
        return round((standard_booking_amount * obj.discount_percentage) / 100, 2)


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = ['id', 'key', 'value', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_key(self, value):
        """Enhanced system setting key validation"""
        if value:
            value = value.strip().lower()
            if not ValidationMixin.validate_text_length(value, 3, 100):
                raise serializers.ValidationError('Key must be between 3 and 100 characters.')
            
            # Check for unique key
            if SystemSetting.objects.filter(key=value).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError('Setting key already exists.')
        return value
    
    def validate(self, data):
        """Cross-field validation for SystemSetting"""
        # Sanitize description
        if 'description' in data and data['description']:
            data['description'] = ValidationMixin.sanitize_html(data['description'].strip())
        
        EnhancedValidationMixin.log_serializer_validation(
            operation='system_setting_validation',
            entity='SystemSetting',
            entity_id=data.get('id', 0),
            user_id=None,
            success=True
        )
        
        return data
