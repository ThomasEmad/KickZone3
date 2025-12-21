"""
Enhanced views with comprehensive validation, security sanitization, and monitoring.
This module provides secure, validated API endpoints with detailed logging and error handling.
"""

import re
import json
import ipaddress
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Q, Avg, Count
from django.core.mail import send_mail
from django.http import Http404
from django.utils.decorators import method_decorator

from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound, AuthenticationFailed

try:
    from django_filters.rest_framework import DjangoFilterBackend
    from django_filters import rest_framework as django_filters
    DJANGO_FILTERS_AVAILABLE = True
except ImportError:
    django_filters = None
    DjangoFilterBackend = None
    DJANGO_FILTERS_AVAILABLE = False

from .models import Pitch, PitchAvailability, Booking, Payment, Review, Tournament, TournamentTeam, Message, MessageGroup, Promotion, SystemSetting
from .serializers import (
    UserSerializer, PitchSerializer, PitchAvailabilitySerializer,
    BookingSerializer, PaymentSerializer, ReviewSerializer,
    TournamentSerializer, TournamentTeamSerializer, MessageSerializer,
    MessageGroupSerializer, PromotionSerializer, SystemSettingSerializer
)
from .validators import ValidationMixin
from .serializers import EnhancedValidationMixin

# Configure view-level logger
view_logger = logging.getLogger('kickzone.views.security')
request_logger = logging.getLogger('kickzone.views.requests')

User = get_user_model()


class SecurityMixin:
    """Mixin to provide security validation and sanitization"""
    
    @staticmethod
    def sanitize_input_data(data, max_size=1024*1024):  # 1MB limit
        """Sanitize and validate input data"""
        if not data:
            return data
        
        # Check data size
        if hasattr(data, '__len__') and len(str(data)) > max_size:
            raise ValidationError({
                'detail': f'Request data exceeds maximum size of {max_size} bytes.'
            })
        
        # Sanitize string inputs
        if isinstance(data, dict):
            return {SecurityMixin.sanitize_input_data(k): SecurityMixin.sanitize_input_data(v) 
                   for k, v in data.items()}
        elif isinstance(data, list):
            return [SecurityMixin.sanitize_input_data(item) for item in data]
        elif isinstance(data, str):
            # Remove potentially dangerous content
            sanitized = ValidationMixin.sanitize_html(data)
            # Check for SQL injection patterns
            sql_patterns = [
                r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
                r'(\b(OR|AND)\s+[\'"]?[\d]+[\'"]?\s*=\s*[\'"]?[\d]+[\'"]?\b)',
                r'(\'\s*OR\s*\'\s*=\s*\'\s*)',
                r'(\-\-)',
                r'(\b(CHAR|ASCII|HEX)\s*\()',
                r'(\b(INFORMATION_SCHEMA|SYSCAT|SYSOBJECTS)\b)'
            ]
            
            for pattern in sql_patterns:
                if re.search(pattern, sanitized, re.IGNORECASE):
                    view_logger.warning(
                        f"Potential SQL injection attempt detected: {sanitized[:100]}...",
                        extra={'suspicious_input': True}
                    )
                    raise ValidationError({
                        'detail': 'Potentially dangerous content detected in request.'
                    })
            
            return sanitized
        
        return data
    
    @staticmethod
    def validate_ip_address(request):
        """Validate client IP address for rate limiting"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        try:
            # Validate IP format
            ipaddress.ip_address(ip)
            return ip
        except ValueError:
            return None
    
    @staticmethod
    def check_rate_limit(request, limit_key, limit_count=100, window_seconds=3600):
        """Check rate limiting based on IP or user"""
        client_ip = SecurityMixin.validate_ip_address(request)
        if not client_ip:
            return False
        
        # Use IP or user ID as key
        key = f"rate_limit_{limit_key}_{client_ip}"
        current_count = cache.get(key, 0)
        
        if current_count >= limit_count:
            view_logger.warning(
                f"Rate limit exceeded for {limit_key} from IP {client_ip}",
                extra={'rate_limit_exceeded': True}
            )
            return False
        
        # Increment counter
        cache.set(key, current_count + 1, window_seconds)
        return True
    
    @staticmethod
    def validate_user_agent(request):
        """Validate User-Agent header"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Block common malicious User-Agents
        blocked_patterns = [
            r'(sqlmap|nikto|nessus|openvas|nmap|masscan)',
            r'(bot|crawler|spider)',
            r'(curl|wget|python-requests|httpclient)'
        ]
        
        for pattern in blocked_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                view_logger.warning(
                    f"Blocked request from suspicious User-Agent: {user_agent}",
                    extra={'suspicious_user_agent': True}
                )
                return False
        
        return True
    
    @staticmethod
    def log_request(request, response_status=None):
        """Log API requests for monitoring and security"""
        client_ip = SecurityMixin.validate_ip_address(request)
        user_id = request.user.id if request.user.is_authenticated else None
        
        # Log the request
        request_logger.info(
            f"{request.method} {request.path} - "
            f"IP: {client_ip} - "
            f"User: {user_id} - "
            f"Status: {response_status}",
            extra={
                'method': request.method,
                'path': request.path,
                'ip_address': client_ip,
                'user_id': user_id,
                'status_code': response_status
            }
        )


class EnhancedViewSet(viewsets.ModelViewSet):
    """Base ViewSet with enhanced security and validation"""
    
    security_mixin = SecurityMixin()
    validation_mixin = EnhancedValidationMixin()
    
    def initial(self, request, *args, **kwargs):
        """Enhanced initial processing with security validation"""
        # Security validations
        if not self.security_mixin.validate_user_agent(request):
            raise PermissionDenied("Access denied due to invalid User-Agent.")
        
        # Rate limiting check
        rate_key = f"{self.__class__.__name__}_{request.method}"
        if not self.security_mixin.check_rate_limit(request, rate_key):
            raise PermissionDenied("Rate limit exceeded. Please try again later.")
        
        # Input sanitization
        if request.method in ['POST', 'PUT', 'PATCH']:
            request.data = self.security_mixin.sanitize_input_data(request.data)
        
        # Log request
        self.security_mixin.log_request(request)
        
        # Call parent initial
        super().initial(request, *args, **kwargs)
    
    def handle_exception(self, exc):
        """Enhanced exception handling with logging"""
        # Log the exception
        view_logger.error(
            f"Exception in {self.__class__.__name__}: {str(exc)}",
            exc_info=True,
            extra={'exception_type': type(exc).__name__}
        )
        
        # Call parent exception handling
        return super().handle_exception(exc)
    
    def finalize_response(self, request, response, *args, **kwargs):
        """Enhanced response with security headers"""
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        # Log response
        self.security_mixin.log_request(request, response.status_code)
        
        return super().finalize_response(request, response, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Enhanced create with transaction and logging"""
        try:
            with transaction.atomic():
                instance = serializer.save()
                
                # Log successful creation
                view_logger.info(
                    f"Created {self.serializer_class.Meta.model.__name__} ID: {instance.id}",
                    extra={
                        'entity_type': self.serializer_class.Meta.model.__name__,
                        'entity_id': instance.id,
                        'user_id': self.request.user.id
                    }
                )
                
                return instance
        except Exception as e:
            view_logger.error(
                f"Failed to create {self.serializer_class.Meta.model.__name__}: {str(e)}",
                exc_info=True,
                extra={'user_id': self.request.user.id}
            )
            raise
    
    def perform_update(self, serializer):
        """Enhanced update with transaction and logging"""
        try:
            with transaction.atomic():
                instance = serializer.save()
                
                # Log successful update
                view_logger.info(
                    f"Updated {self.serializer_class.Meta.model.__name__} ID: {instance.id}",
                    extra={
                        'entity_type': self.serializer_class.Meta.model.__name__,
                        'entity_id': instance.id,
                        'user_id': self.request.user.id
                    }
                )
                
                return instance
        except Exception as e:
            view_logger.error(
                f"Failed to update {self.serializer_class.Meta.model.__name__}: {str(e)}",
                exc_info=True,
                extra={'user_id': self.request.user.id}
            )
            raise
    
    def perform_destroy(self, instance):
        """Enhanced destroy with logging"""
        try:
            entity_id = instance.id
            entity_type = self.serializer_class.Meta.model.__name__
            
            instance.delete()
            
            # Log successful deletion
            view_logger.info(
                f"Deleted {entity_type} ID: {entity_id}",
                extra={
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'user_id': self.request.user.id
                }
            )
        except Exception as e:
            view_logger.error(
                f"Failed to delete {self.serializer_class.Meta.model.__name__}: {str(e)}",
                exc_info=True,
                extra={'user_id': self.request.user.id}
            )
            raise


class UserViewSet(EnhancedViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ['user_type']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    def get_permissions(self):
        """Enhanced permissions with security checks"""
        if self.action in ['register', 'login']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Enhanced user registration with validation"""
        try:
            # Additional security checks
            if not self.security_mixin.check_rate_limit(request, 'user_register', limit_count=5, window_seconds=300):
                raise PermissionDenied("Too many registration attempts. Please try again later.")
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Additional validation
            username = serializer.validated_data.get('username', '').lower()
            email = serializer.validated_data.get('email', '').lower()
            
            # Check for suspicious patterns
            if re.search(r'(admin|root|system|test)', username):
                view_logger.warning(
                    f"Suspicious username attempted: {username}",
                    extra={'suspicious_username': True}
                )
                raise ValidationError({
                    'username': 'Username contains restricted terms.'
                })
            
            # Create user
            user = serializer.save()
            
            # Create token
            token, created = Token.objects.get_or_create(user=user)
            
            # Log successful registration
            view_logger.info(
                f"User registered successfully: {user.username}",
                extra={'user_id': user.id, 'registration': True}
            )
            
            return Response({
                'user': serializer.data,
                'token': token.key,
                'message': 'Registration successful.'
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            view_logger.warning(
                f"Registration validation failed: {str(e)}",
                extra={'registration_validation_failed': True}
            )
            raise
        except Exception as e:
            view_logger.error(
                f"Registration failed: {str(e)}",
                exc_info=True,
                extra={'registration_failed': True}
            )
            raise ValidationError({
                'detail': 'Registration failed. Please try again.'
            })
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """Enhanced user login with security"""
        try:
            # Rate limiting for login attempts
            if not self.security_mixin.check_rate_limit(request, 'user_login', limit_count=10, window_seconds=300):
                raise PermissionDenied("Too many login attempts. Please try again later.")
            
            username = request.data.get('username', '').lower().strip()
            password = request.data.get('password', '')
            
            if not username or not password:
                raise ValidationError({
                    'detail': 'Username and password are required.'
                })
            
            # Check for brute force attempts
            cache_key = f"failed_login_{username}"
            failed_attempts = cache.get(cache_key, 0)
            
            if failed_attempts >= 5:
                view_logger.warning(
                    f"Account locked due to multiple failed login attempts: {username}",
                    extra={'account_locked': True}
                )
                raise PermissionDenied("Account temporarily locked due to multiple failed attempts.")
            
            # Attempt authentication
            try:
                user = User.objects.get(username=username)
                
                if user.check_password(password):
                    # Clear failed attempts on successful login
                    cache.delete(cache_key)
                    
                    # Update last login
                    user.last_login = timezone.now()
                    user.save(update_fields=['last_login'])
                    
                    # Create or get token
                    token, created = Token.objects.get_or_create(user=user)
                    
                    view_logger.info(
                        f"User login successful: {username}",
                        extra={'user_id': user.id, 'login_success': True}
                    )
                    
                    return Response({
                        'user': UserSerializer(user).data,
                        'token': token.key,
                        'message': 'Login successful.'
                    })
                else:
                    # Increment failed attempts
                    cache.set(cache_key, failed_attempts + 1, 900)  # 15 minutes
                    
                    view_logger.warning(
                        f"Failed login attempt for username: {username}",
                        extra={'failed_login': True}
                    )
                    
                    raise ValidationError({
                        'detail': 'Invalid credentials.'
                    })
                    
            except User.DoesNotExist:
                # Increment failed attempts for non-existent users too
                cache.set(cache_key, failed_attempts + 1, 900)
                
                view_logger.warning(
                    f"Login attempt for non-existent user: {username}",
                    extra={'nonexistent_user_login': True}
                )
                
                raise ValidationError({
                    'detail': 'Invalid credentials.'
                })
                
        except (ValidationError, PermissionDenied):
            raise
        except Exception as e:
            view_logger.error(
                f"Login error: {str(e)}",
                exc_info=True,
                extra={'login_error': True}
            )
            raise ValidationError({
                'detail': 'Login failed. Please try again.'
            })
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Enhanced user logout"""
        try:
            if request.user.is_authenticated:
                # Delete token
                try:
                    request.user.auth_token.delete()
                except:
                    pass  # Token might not exist
                
                view_logger.info(
                    f"User logout: {request.user.username}",
                    extra={'user_id': request.user.id, 'logout': True}
                )
                
                return Response({
                    'message': 'Successfully logged out.'
                })
            else:
                return Response({
                    'message': 'No active session found.'
                })
        except Exception as e:
            view_logger.error(
                f"Logout error: {str(e)}",
                exc_info=True,
                extra={'logout_error': True}
            )
            raise ValidationError({
                'detail': 'Logout failed.'
            })
    
    @action(detail=False, methods=['get', 'put'])
    def profile(self, request):
        """Enhanced profile management"""
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        
        elif request.method == 'PUT':
            try:
                # Handle FormData conversion for Skill_Level
                data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
                
                # Ensure Skill_Level is properly converted to integer
                if 'Skill_Level' in data:
                    try:
                        original_value = data['Skill_Level']
                        if hasattr(data, 'getlist'):
                            skill_level_value = data.getlist('Skill_Level')[0] if data.getlist('Skill_Level') else None
                        else:
                            skill_level_value = data.get('Skill_Level')
                        
                        if skill_level_value is not None:
                            data['Skill_Level'] = int(skill_level_value)
                    except (ValueError, TypeError):
                        raise ValidationError({
                            'Skill_Level': 'Invalid Skill_Level value. Must be a number between 1 and 100.'
                        })
                
                serializer = self.get_serializer(
                    request.user, 
                    data=data, 
                    partial=True
                )
                
                if not serializer.is_valid():
                    raise ValidationError(serializer.errors)
                
                updated_user = serializer.save()
                
                view_logger.info(
                    f"Profile updated: {request.user.username}",
                    extra={'user_id': request.user.id, 'profile_update': True}
                )
                
                return Response({
                    'success': True,
                    'user': UserSerializer(updated_user).data,
                    'message': 'Profile updated successfully.'
                })
                
            except ValidationError:
                raise
            except Exception as e:
                view_logger.error(
                    f"Profile update error: {str(e)}",
                    exc_info=True,
                    extra={'user_id': request.user.id, 'profile_update_error': True}
                )
                raise ValidationError({
                    'detail': 'Failed to update profile.'
                })


# Continue with other ViewSets...
# For brevity, I'll include just a couple more enhanced ViewSets

class PitchViewSet(EnhancedViewSet):
    queryset = Pitch.objects.all()
    serializer_class = PitchSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    
    search_fields = ['name', 'description', 'location']
    ordering_fields = ['price_per_hour', 'created_at']
    
    def get_queryset(self):
        """Enhanced queryset with filtering and security"""
        user = self.request.user
        
        # Base queryset
        queryset = Pitch.objects.all()
        
        # Apply search
        search = self.request.query_params.get('search', None)
        if search:
            # Sanitize search term
            search = self.security_mixin.sanitize_input_data(search)
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(location__icontains=search)
            )
        
        # Apply filters
        surface_type = self.request.query_params.get('surface_type')
        if surface_type:
            queryset = queryset.filter(surface_type=surface_type)
        
        owner = self.request.query_params.get('owner')
        if owner:
            try:
                owner_id = int(owner)
                queryset = queryset.filter(owner_id=owner_id)
            except ValueError:
                pass
        
        return queryset.select_related('owner').prefetch_related('reviews', 'availabilities')
    
    def perform_create(self, serializer):
        """Enhanced pitch creation with ownership validation"""
        # Ensure user is owner
        if self.request.user.user_type != 'owner':
            raise PermissionDenied("Only pitch owners can create pitches.")
        
        serializer.save(owner=self.request.user)
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Enhanced nearby pitches with security"""
        lat = request.query_params.get('latitude')
        lng = request.query_params.get('longitude')
        radius = request.query_params.get('radius', 10)
        
        # Validate inputs
        try:
            lat = float(lat)
            lng = float(lng)
            radius = float(radius)
            
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValidationError({
                    'detail': 'Invalid latitude or longitude values.'
                })
            
            if radius <= 0 or radius > 100:
                raise ValidationError({
                    'detail': 'Radius must be between 0 and 100 km.'
                })
                
        except (ValueError, TypeError):
            raise ValidationError({
                'detail': 'Invalid latitude, longitude, or radius values.'
            })
        
        # Calculate nearby pitches (simplified distance calculation)
        pitches = Pitch.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )
        
        nearby_pitches = []
        for pitch in pitches:
            # Simple distance calculation (not precise but works for demo)
            distance = ((float(pitch.latitude) - lat) ** 2 + (float(pitch.longitude) - lng) ** 2) ** 0.5
            if distance <= radius / 100:  # Rough conversion
                nearby_pitches.append({
                    'id': pitch.id,
                    'name': pitch.name,
                    'location': pitch.location,
                    'price_per_hour': pitch.price_per_hour,
                    'distance': round(distance * 111, 2)  # Rough km conversion
                })
        
        return Response({
            'pitches': nearby_pitches,
            'count': len(nearby_pitches),
            'search_params': {
                'latitude': lat,
                'longitude': lng,
                'radius': radius
            }
        })


class BookingViewSet(EnhancedViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['pitch', 'player', 'status', 'date']
    ordering_fields = ['date', 'created_at']
    
    def get_queryset(self):
        """Enhanced queryset with user-based filtering"""
        user = self.request.user
        
        if user.user_type == 'owner':
            queryset = Booking.objects.filter(pitch__owner=user)
        elif user.user_type == 'admin':
            queryset = Booking.objects.all()
        else:
            queryset = Booking.objects.filter(player=user)
        
        # Update expired bookings
        Booking.update_expired_bookings()
        
        # Apply filters
        date_gte = self.request.query_params.get('date__gte')
        if date_gte:
            queryset = queryset.filter(date__gte=date_gte)
        
        status_in = self.request.query_params.get('status__in')
        if status_in:
            status_list = [s.strip() for s in status_in.split(',')]
            queryset = queryset.filter(status__in=status_list)
        
        return queryset.select_related('pitch', 'player').prefetch_related('payment')
    
    def create(self, request, *args, **kwargs):
        """Enhanced booking creation with comprehensive validation"""
        try:
            # Get and validate input data
            pitch_id = request.data.get('pitch_id')
            date = request.data.get('date')
            start_time = request.data.get('start_time')
            end_time = request.data.get('end_time')
            promotion_code = request.data.get('promotion_code', '')
            
            # Validate required fields
            if not all([pitch_id, date, start_time, end_time]):
                raise ValidationError({
                    'detail': 'Pitch ID, date, start time, and end time are required.'
                })
            
            # Validate user permissions
            if request.user.user_type not in ['player', 'admin']:
                raise PermissionDenied("Only players can create bookings.")
            
            # Get pitch
            try:
                pitch = Pitch.objects.get(id=pitch_id)
            except Pitch.DoesNotExist:
                raise NotFound("Pitch not found.")
            
            # Validate date and time
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                start_time_obj = datetime.strptime(start_time, '%H:%M').time()
                end_time_obj = datetime.strptime(end_time, '%H:%M').time()
            except ValueError:
                raise ValidationError({
                    'detail': 'Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time.'
                })
            
            # Check if date is in the future
            if date_obj < datetime.now().date():
                raise ValidationError({
                    'detail': 'Booking date cannot be in the past.'
                })
            
            # Validate time range
            if end_time_obj <= start_time_obj:
                raise ValidationError({
                    'detail': 'End time must be after start time.'
                })
            
            # Check minimum duration (30 minutes)
            duration = (datetime.combine(date_obj, end_time_obj) - 
                       datetime.combine(date_obj, start_time_obj)).total_seconds() / 3600
            if duration < 0.5:
                raise ValidationError({
                    'detail': 'Booking duration must be at least 30 minutes.'
                })
            
            # Check pitch availability
            day_of_week = date_obj.weekday()
            try:
                availability = PitchAvailability.objects.get(pitch=pitch, day_of_week=day_of_week)
                if not availability.is_available:
                    raise ValidationError({
                        'detail': 'Pitch is not available on this day.'
                    })
                
                if (start_time_obj < availability.opening_time or 
                    end_time_obj > availability.closing_time):
                    raise ValidationError({
                        'detail': 'Requested time is outside available hours.'
                    })
            except PitchAvailability.DoesNotExist:
                raise ValidationError({
                    'detail': 'Pitch availability not set for this day.'
                })
            
            # Check for conflicting bookings
            conflicts = Booking.objects.filter(
                pitch=pitch,
                date=date_obj,
                status__in=['confirmed', 'pending'],
                start_time__lt=end_time_obj,
                end_time__gt=start_time_obj
            )
            
            if conflicts.exists():
                raise ValidationError({
                    'detail': 'Pitch is already booked for this time slot.'
                })
            
            # Calculate price
            total_price = float(pitch.price_per_hour) * duration
            
            # Apply promotion if provided
            promotion = None
            if promotion_code:
                try:
                    promotion = Promotion.objects.get(code=promotion_code.upper())
                    if not promotion.is_valid():
                        raise ValidationError({
                            'promotion_code': 'This promotion code is not valid.'
                        })
                    
                    # Calculate discount
                    discount = total_price * (promotion.discount_percentage / 100)
                    total_price -= discount
                    
                except Promotion.DoesNotExist:
                    raise ValidationError({
                        'promotion_code': 'Invalid promotion code.'
                    })
            
            # Create booking
            booking_data = {
                'pitch': pitch,
                'player': request.user,
                'date': date_obj,
                'start_time': start_time_obj,
                'end_time': end_time_obj,
                'total_price': round(total_price, 2),
                'status': 'pending'
            }
            
            booking = Booking.objects.create(**booking_data)
            
            # Create payment record
            payment = Payment.objects.create(
                booking=booking,
                amount=booking.total_price,
                status='pending'
            )
            
            # Update promotion usage
            if promotion:
                promotion.current_uses += 1
                promotion.save()
            
            # Send notification email
            try:
                if pitch.owner.email:
                    subject = f'New Booking Request for {pitch.name}'
                    message = f'New booking request from {request.user.username} for {date} from {start_time} to {end_time}.'
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [pitch.owner.email])
            except Exception as e:
                view_logger.warning(f"Failed to send booking notification: {str(e)}")
            
            serializer = self.get_serializer(booking)
            
            view_logger.info(
                f"Booking created: ID {booking.id}",
                extra={
                    'booking_id': booking.id,
                    'user_id': request.user.id,
                    'pitch_id': pitch.id
                }
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except (ValidationError, PermissionDenied, NotFound):
            raise
        except Exception as e:
            view_logger.error(
                f"Booking creation error: {str(e)}",
                exc_info=True,
                extra={'user_id': request.user.id}
            )
            raise ValidationError({
                'detail': 'Failed to create booking. Please try again.'
            })
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Enhanced booking confirmation"""
        booking = self.get_object()
        
        # Check permissions
        if request.user != booking.pitch.owner and request.user.user_type != 'admin':
            raise PermissionDenied("You don't have permission to confirm this booking.")
        
        if booking.status != 'pending':
            raise ValidationError({
                'detail': 'Only pending bookings can be confirmed.'
            })
        
        # Confirm booking
        booking.status = 'confirmed'
        booking.save()
        
        # Update payment
        try:
            payment = booking.payment
            payment.status = 'completed'
            payment.save()
        except Payment.DoesNotExist:
            pass
        
        # Send notifications
        try:
            if booking.player.email:
                subject = f'Booking Confirmed for {booking.pitch.name}'
                message = f'Your booking for {booking.pitch.name} on {booking.date} has been confirmed.'
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [booking.player.email])
        except Exception as e:
            view_logger.warning(f"Failed to send confirmation email: {str(e)}")
        
        serializer = self.get_serializer(booking)
        
        view_logger.info(
            f"Booking confirmed: ID {booking.id}",
            extra={
                'booking_id': booking.id,
                'user_id': request.user.id
            }
        )
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Enhanced booking cancellation"""
        booking = self.get_object()
        
        # Check permissions
        if (request.user not in [booking.player, booking.pitch.owner] and 
            request.user.user_type != 'admin'):
            raise PermissionDenied("You don't have permission to cancel this booking.")
        
        if booking.status in ['completed', 'cancelled']:
            raise ValidationError({
                'detail': 'Cannot cancel a completed or already cancelled booking.'
            })
        
        # Cancel booking
        booking.status = 'cancelled'
        booking.save()
        
        # Update payment
        try:
            payment = booking.payment
            payment.status = 'refunded'
            payment.save()
        except Payment.DoesNotExist:
            pass
        
        # Send notifications
        try:
            # Notify the other party
            if request.user == booking.player and booking.pitch.owner.email:
                subject = f'Booking Cancelled for {booking.pitch.name}'
                message = f'Your booking for {booking.pitch.name} has been cancelled by the player.'
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [booking.pitch.owner.email])
            elif request.user == booking.pitch.owner and booking.player.email:
                subject = f'Booking Cancelled for {booking.pitch.name}'
                message = f'Your booking for {booking.pitch.name} has been cancelled by the pitch owner.'
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [booking.player.email])
        except Exception as e:
            view_logger.warning(f"Failed to send cancellation email: {str(e)}")
        
        serializer = self.get_serializer(booking)
        
        view_logger.info(
            f"Booking cancelled: ID {booking.id}",
            extra={
                'booking_id': booking.id,
                'user_id': request.user.id
            }
        )
        
        return Response(serializer.data)


# Additional ViewSets would continue here...
# For brevity, I'm including just the main enhanced ViewSets