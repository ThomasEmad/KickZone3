from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.authtoken.models import Token
try:
    from django_filters.rest_framework import DjangoFilterBackend
    from django_filters import rest_framework as django_filters
    print("✓ django_filters imported successfully")
except ImportError as e:
    print(f"✗ Failed to import django_filters: {e}")
    DjangoFilterBackend = None
    django_filters = None

from django.db.models import Avg, Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .models import Pitch, PitchAvailability, Booking, Payment, Review, Tournament, TournamentTeam, Message, MessageGroup, Promotion, SystemSetting
from .serializers import (
    UserSerializer, PitchSerializer, PitchAvailabilitySerializer,
    BookingSerializer, PaymentSerializer, ReviewSerializer,
    TournamentSerializer, TournamentTeamSerializer, MessageSerializer,
    MessageGroupSerializer, PromotionSerializer, SystemSettingSerializer
)

User = get_user_model()

# Custom filter for Pitch price range
if django_filters:
    class PitchFilter(django_filters.FilterSet):
        min_price = django_filters.NumberFilter(field_name='price_per_hour', lookup_expr='gte')
        max_price = django_filters.NumberFilter(field_name='price_per_hour', lookup_expr='lte')
        
        class Meta:
            model = Pitch
            fields = ['surface_type', 'owner', 'min_price', 'max_price']

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ['user_type']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create token for the user
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'user': serializer.data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """Login a user"""
        username = request.data.get('username', '').lower().strip()  # Convert to lowercase to match registration
        password = request.data.get('password')
        
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                token, created = Token.objects.get_or_create(user=user)
                return Response({
                    'user': UserSerializer(user).data,
                    'token': token.key
                })
            else:
                return Response(
                    {'error': 'Invalid credentials'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Logout a user"""
        try:
            # Delete the user's token
            request.user.auth_token.delete()
            return Response({'message': 'Successfully logged out'})
        except:
            return Response(
                {'error': 'Error logging out'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def get_permissions(self):
        if self.action in ['register', 'login', 'directory', 'online_users']:
            permission_classes = []
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def directory(self, request):
        """Get users for messaging directory with search and filtering"""
        search_query = request.query_params.get('search', '')
        user_type = request.query_params.get('user_type', '')
        exclude_self = request.query_params.get('exclude_self', 'true').lower() == 'true'
        
        queryset = User.objects.all()
        
        # Exclude current user if requested
        if exclude_self:
            queryset = queryset.exclude(id=request.user.id)
        
        # Apply search filter
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        
        # Apply user type filter
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        
        # Apply ordering
        queryset = queryset.order_by('username')
        
        # Limit results for performance
        queryset = queryset[:100]  # Limit to 100 users
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'users': serializer.data,
            'count': queryset.count()
        })
    
    @action(detail=False, methods=['post'])
    def update_presence(self, request):
        """Update user presence status"""
        status = request.data.get('status', 'offline')
        
        # Update user's last seen timestamp
        request.user.last_activity = timezone.now()
        request.user.save(update_fields=['last_activity'])
        
        return Response({
            'status': 'success',
            'message': 'Presence updated successfully'
        })
    
    @action(detail=False, methods=['get'])
    def online_users(self, request):
        """Get list of currently online users"""
        # Consider users online if they've been active in the last 5 minutes
        from datetime import timedelta
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        
        online_users = User.objects.filter(
            last_activity__gte=five_minutes_ago
        ).exclude(id=request.user.id)
        
        serializer = self.get_serializer(online_users, many=True)
        return Response({
            'online_users': serializer.data,
            'count': online_users.count()
        })
    
    @action(detail=False, methods=['get', 'put'])
    def profile(self, request):
        """Get or update current user's profile"""
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        
        elif request.method == 'PUT':
            print(f"DEBUG: Profile update request data: {request.data}")
            print(f"DEBUG: Request user: {request.user.username}")
            print(f"DEBUG: Content type: {request.content_type}")
            
            # Handle FormData conversion for Skill_Level
            data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
            
            # Ensure Skill_Level is properly converted to integer
            if 'Skill_Level' in data:
                try:
                    original_value = data['Skill_Level']
                    if hasattr(data, 'getlist'):
                        # Handle multiple values from FormData
                        skill_level_value = data.getlist('Skill_Level')[0] if data.getlist('Skill_Level') else None
                    else:
                        skill_level_value = data.get('Skill_Level')
                    
                    if skill_level_value is not None:
                        data['Skill_Level'] = int(skill_level_value)
                        print(f"DEBUG: Skill_Level converted from {original_value} to {data['Skill_Level']}")
                except (ValueError, TypeError) as e:
                    print(f"DEBUG: Skill_Level conversion error: {e}")
                    return Response({
                        'error': 'Invalid Skill_Level value. Must be a number between 1 and 100.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            print(f"DEBUG: Processed data: {data}")
            
            serializer = self.get_serializer(request.user, data=data, partial=True)
            
            if not serializer.is_valid():
                print(f"DEBUG: Serializer errors: {serializer.errors}")
                return Response({
                    'error': 'Validation failed',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            print("DEBUG: Serializer is valid, saving...")
            try:
                updated_user = serializer.save()
                print(f"DEBUG: User updated successfully: {updated_user.username}")
                print(f"DEBUG: New Skill_Level: {updated_user.Skill_Level}")
                
                # Return updated user data
                return Response({
                    'success': True,
                    'user': UserSerializer(updated_user).data,
                    'message': 'Profile updated successfully'
                })
            except Exception as e:
                print(f"DEBUG: Save error: {e}")
                import traceback
                traceback.print_exc()
                return Response({
                    'error': 'Failed to save profile updates',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PitchViewSet(viewsets.ModelViewSet):
    queryset = Pitch.objects.all()
    serializer_class = PitchSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    
    # Use custom filter for price range filtering
    if django_filters:
        filterset_class = PitchFilter
    else:
        filterset_fields = ['surface_type', 'owner']
    
    search_fields = ['name', 'description', 'location']
    ordering_fields = ['price_per_hour', 'created_at']
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Get nearby pitches based on user's location"""
        lat = request.query_params.get('latitude')
        lng = request.query_params.get('longitude')
        radius = request.query_params.get('radius', 10)  # Default radius: 10km
        
        if not lat or not lng:
            return Response(
                {"error": "Latitude and longitude parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lat = float(lat)
            lng = float(lng)
            radius = float(radius)
        except ValueError:
            return Response(
                {"error": "Invalid latitude, longitude, or radius value"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Using a simple distance calculation (not precise but works for demonstration)
        # In production, you might want to use PostGIS or another geospatial solution
        pitches = Pitch.objects.all()
        nearby_pitches = []
        
        for pitch in pitches:
            if pitch.latitude and pitch.longitude:
                # Simple distance calculation (not precise)
                distance = ((float(pitch.latitude) - lat) ** 2 + (float(pitch.longitude) - lng) ** 2) ** 0.5
                if distance <= radius / 100:  # Rough conversion
                    nearby_pitches.append(pitch)
        
        serializer = self.get_serializer(nearby_pitches, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Get availability for a specific pitch"""
        pitch = self.get_object()
        date = request.query_params.get('date')
        
        if not date:
            return Response(
                {"error": "Date parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Parse date string to date object
            from datetime import datetime
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            day_of_week = date_obj.weekday()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the pitch availability for the specific day of week
        try:
            availability = PitchAvailability.objects.get(pitch=pitch, day_of_week=day_of_week)
            if not availability.is_available:
                return Response({"available": False})
            
            # Get existing bookings for the date
            bookings = Booking.objects.filter(
                pitch=pitch, 
                date=date_obj, 
                status__in=['confirmed', 'pending']
            )
            
            # Convert bookings to time slots
            booked_slots = []
            for booking in bookings:
                booked_slots.append({
                    'start_time': booking.start_time.strftime('%H:%M'),
                    'end_time': booking.end_time.strftime('%H:%M')
                })
            
            return Response({
                "available": True,
                "opening_time": availability.opening_time.strftime('%H:%M'),
                "closing_time": availability.closing_time.strftime('%H:%M'),
                "booked_slots": booked_slots
            })
        except PitchAvailability.DoesNotExist:
            return Response({"available": False})
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

class PitchAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = PitchAvailability.objects.all()
    serializer_class = PitchAvailabilitySerializer
    filter_backends = []
    if DjangoFilterBackend:
        filter_backends.append(DjangoFilterBackend)
    filterset_fields = ['pitch', 'day_of_week']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['pitch', 'player', 'status', 'date']
    ordering_fields = ['date', 'created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'owner':
            # Pitch owners can see bookings for their pitches
            queryset = Booking.objects.filter(pitch__owner=user)
        elif user.user_type == 'admin':
            # Admins can see all bookings
            queryset = Booking.objects.all()
        else:
            # Players can only see their own bookings
            queryset = Booking.objects.filter(player=user)
        
        # Automatically update expired bookings to completed
        Booking.update_expired_bookings()
        
        # Apply custom filtering based on query parameters
        date_gt = self.request.query_params.get('date__gt')
        date_gte = self.request.query_params.get('date__gte')
        status_in = self.request.query_params.get('status__in')
        status = self.request.query_params.get('status')
        date = self.request.query_params.get('date')
        
        if date_gte:
            # Filter for bookings with date greater than or equal to specified date (current and future bookings)
            queryset = queryset.filter(date__gte=date_gte)
        elif date_gt:
            # Filter for bookings with date greater than specified date (future bookings only)
            queryset = queryset.filter(date__gt=date_gt)
        
        if status_in:
            # Filter for multiple status values (e.g., 'pending,confirmed')
            status_list = [s.strip() for s in status_in.split(',')]
            queryset = queryset.filter(status__in=status_list)
        
        if status:
            # Filter for single status value
            queryset = queryset.filter(status=status)
        
        if date and not date_gt:
            # Filter for exact date match
            queryset = queryset.filter(date=date)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new booking"""
        print(f"DEBUG: Booking create called with data: {request.data}")
        pitch_id = request.data.get('pitch_id')
        date = request.data.get('date')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')

        if not all([pitch_id, date, start_time, end_time]):
            print("DEBUG: Missing required fields")
            return Response(
                {"error": "Pitch ID, date, start time, and end time are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            print(f"DEBUG: Getting pitch {pitch_id}")
            pitch = Pitch.objects.get(id=pitch_id)

            # Check if the pitch is available at the requested time
            from datetime import datetime
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            day_of_week = date_obj.weekday()
            print(f"DEBUG: Date {date}, day {day_of_week}")

            try:
                availability = PitchAvailability.objects.get(pitch=pitch, day_of_week=day_of_week)
                if not availability.is_available:
                    print("DEBUG: Pitch not available on this day")
                    return Response(
                        {"error": "Pitch is not available on this day"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Parse times
                print(f"DEBUG: Parsing times {start_time} to {end_time}")
                start_time_obj = datetime.strptime(start_time, '%H:%M').time()
                end_time_obj = datetime.strptime(end_time, '%H:%M').time()
                print(f"DEBUG: Parsed times {start_time_obj} to {end_time_obj}")

                # Check if the requested time is within the available hours
                if start_time_obj < availability.opening_time or end_time_obj > availability.closing_time:
                    print("DEBUG: Time outside available hours")
                    return Response(
                        {"error": "Requested time is outside available hours"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check for overlapping bookings
                overlapping_bookings = Booking.objects.filter(
                    pitch=pitch,
                    date=date_obj,
                    status__in=['confirmed', 'pending'],
                    start_time__lt=end_time_obj,
                    end_time__gt=start_time_obj
                )
                print(f"DEBUG: Overlapping bookings count: {overlapping_bookings.count()}")

                if overlapping_bookings.exists():
                    print("DEBUG: Overlapping booking found")
                    return Response(
                        {"error": "Pitch is already booked for this time slot"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Calculate total price
                from datetime import datetime, timedelta
                from decimal import Decimal
                start_datetime = datetime.combine(date_obj, start_time_obj)
                end_datetime = datetime.combine(date_obj, end_time_obj)
                duration_hours = (end_datetime - start_datetime).total_seconds() / 3600
                total_price = pitch.price_per_hour * Decimal(duration_hours)
                print(f"DEBUG: Duration {duration_hours}, price_per_hour {pitch.price_per_hour}, total {total_price}")

                # Create the booking
                print("DEBUG: Creating booking")
                booking = Booking.objects.create(
                    pitch=pitch,
                    player=request.user,
                    date=date_obj,
                    start_time=start_time_obj,
                    end_time=end_time_obj,
                    total_price=total_price,
                    status='pending'
                )
                print(f"DEBUG: Booking created {booking.id}")

                # Send notification to pitch owner
                try:
                    if pitch.owner.email:
                        subject = f'New Booking Request for {pitch.name}'
                        message = f'You have a new booking request from {request.user.username} for {date} from {start_time} to {end_time}.'
                        from_email = settings.DEFAULT_FROM_EMAIL
                        recipient_list = [pitch.owner.email]
                        print(f"DEBUG: Sending email to {pitch.owner.email}")
                        send_mail(subject, message, from_email, recipient_list)
                        print("DEBUG: Email sent")
                except Exception as e:
                    print(f"DEBUG: Email sending failed: {e}")

                serializer = self.get_serializer(booking)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

            except PitchAvailability.DoesNotExist:
                print("DEBUG: Pitch availability not set")
                return Response(
                    {"error": "Pitch availability not set for this day"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Pitch.DoesNotExist:
            print("DEBUG: Pitch not found")
            return Response(
                {"error": "Pitch not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            print(f"DEBUG: ValueError: {e}")
            return Response(
                {"error": f"Invalid date or time format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"DEBUG: Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a booking"""
        booking = self.get_object()
        
        if booking.status != 'pending':
            return Response(
                {"error": "Only pending bookings can be confirmed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if the user is the pitch owner or an admin
        if request.user.user_type not in ['owner', 'admin'] or (
            request.user.user_type == 'owner' and booking.pitch.owner != request.user
        ):
            return Response(
                {"error": "You don't have permission to confirm this booking"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        booking.status = 'confirmed'
        booking.save()
        
        # Create a payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            status='pending'
        )
        
        # Send notification to player
        if booking.player.email:
            subject = f'Booking Confirmed for {booking.pitch.name}'
            message = f'Your booking for {booking.pitch.name} on {booking.date} from {booking.start_time} to {booking.end_time} has been confirmed.'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [booking.player.email]
            send_mail(subject, message, from_email, recipient_list)
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking"""
        booking = self.get_object()
        
        print(f"DEBUG: Cancel request for booking {booking.id} by user {request.user.username}")
        print(f"DEBUG: Booking status: {booking.status}")
        
        if booking.status in ['completed', 'cancelled']:
            print(f"DEBUG: Cannot cancel booking with status {booking.status}")
            return Response(
                {"error": "Cannot cancel a completed or already cancelled booking"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if the user is the player, pitch owner, or an admin
        if request.user not in [booking.player, booking.pitch.owner] and request.user.user_type != 'admin':
            print(f"DEBUG: User {request.user.username} does not have permission to cancel")
            return Response(
                {"error": "You don't have permission to cancel this booking"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Perform the cancellation
        booking.status = 'cancelled'
        booking.save()
        print(f"DEBUG: Booking {booking.id} status updated to cancelled")
        
        # If payment exists, mark it as refunded
        try:
            payment = booking.payment
            payment.status = 'refunded'
            payment.save()
            print(f"DEBUG: Payment {payment.id} marked as refunded")
        except Payment.DoesNotExist:
            print(f"DEBUG: No payment found for booking {booking.id}")
            pass
        
        # Send notification to the other party
        try:
            if request.user == booking.player and booking.pitch.owner.email:
                subject = f'Booking Cancelled for {booking.pitch.name}'
                message = f'Your booking for {booking.pitch.name} on {booking.date} from {booking.start_time} to {booking.end_time} has been cancelled by the player.'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [booking.pitch.owner.email]
                send_mail(subject, message, from_email, recipient_list)
                print(f"DEBUG: Cancellation email sent to pitch owner")
            elif request.user == booking.pitch.owner and booking.player.email:
                subject = f'Booking Cancelled for {booking.pitch.name}'
                message = f'Your booking for {booking.pitch.name} on {booking.date} from {booking.start_time} to {booking.end_time} has been cancelled by the pitch owner.'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [booking.player.email]
                send_mail(subject, message, from_email, recipient_list)
                print(f"DEBUG: Cancellation email sent to player")
        except Exception as e:
            print(f"DEBUG: Email sending failed: {e}")
            # Don't fail the cancellation if email fails
            pass
        
        serializer = self.get_serializer(booking)
        print(f"DEBUG: Returning cancelled booking data")
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_expired(self, request):
        """Manually trigger update of expired bookings"""
        # Check if user is admin or owner
        if request.user.user_type not in ['admin', 'owner']:
            return Response(
                {"error": "You don't have permission to update bookings"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        updated_count = Booking.update_expired_bookings()
        
        return Response({
            "message": f"Successfully updated {updated_count} expired bookings to completed status",
            "updated_count": updated_count
        })
    
    def get_permissions(self):
        if self.action in ['create', 'confirm', 'cancel', 'update_expired']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filter_backends = [filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ['booking', 'status']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return Payment.objects.all()
        else:
            # Users can only see their own payments
            return Payment.objects.filter(booking__player=user)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process a payment"""
        payment = self.get_object()
        
        if payment.status != 'pending':
            return Response(
                {"error": "Only pending payments can be processed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if the user is the player or an admin
        if request.user != payment.booking.player and request.user.user_type != 'admin':
            return Response(
                {"error": "You don't have permission to process this payment"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        payment_method = request.data.get('payment_method')
        if not payment_method:
            return Response(
                {"error": "Payment method is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # In a real implementation, you would integrate with a payment gateway here
        # For demonstration, we'll just mark the payment as completed
        payment.status = 'completed'
        payment.payment_method = payment_method
        payment.transaction_id = f"txn_{timezone.now().strftime('%Y%m%d%H%M%S')}"
        payment.save()
        
        # Update booking status
        booking = payment.booking
        booking.status = 'confirmed'
        booking.save()
        
        # Send confirmation email
        if booking.player.email:
            subject = f'Payment Confirmed for {booking.pitch.name}'
            message = f'Your payment of ${booking.total_price} for {booking.pitch.name} on {booking.date} has been confirmed.'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [booking.player.email]
            send_mail(subject, message, from_email, recipient_list)
        
        serializer = self.get_serializer(payment)
        return Response(serializer.data)
    
    def get_permissions(self):
        if self.action in ['create', 'process']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    filter_backends = [filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ['pitch', 'player', 'rating']
    ordering_fields = ['created_at', 'rating']
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return Review.objects.all()
        else:
            # Users can see all reviews, but can only modify their own
            return Review.objects.all()
    
    def create(self, request, *args, **kwargs):
        """Create a new review"""
        pitch_id = request.data.get('pitch_id')
        rating = request.data.get('rating')
        comment = request.data.get('comment', '')
        
        if not pitch_id or not rating:
            return Response(
                {"error": "Pitch ID and rating are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            pitch = Pitch.objects.get(id=pitch_id)
            rating = int(rating)
            
            if rating < 1 or rating > 5:
                return Response(
                    {"error": "Rating must be between 1 and 5"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if the user has booked this pitch before
            has_booked = Booking.objects.filter(
                pitch=pitch,
                player=request.user,
                status='completed'
            ).exists()
            
            if not has_booked:
                return Response(
                    {"error": "You can only review pitches you have booked and completed"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if the user has already reviewed this pitch
            existing_review = Review.objects.filter(
                pitch=pitch,
                player=request.user
            ).first()
            
            if existing_review:
                # Update existing review
                existing_review.rating = rating
                existing_review.comment = comment
                existing_review.save()
                serializer = self.get_serializer(existing_review)
                return Response(serializer.data)
            else:
                # Create new review
                review = Review.objects.create(
                    pitch=pitch,
                    player=request.user,
                    rating=rating,
                    comment=comment
                )
                serializer = self.get_serializer(review)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Pitch.DoesNotExist:
            return Response(
                {"error": "Pitch not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {"error": "Invalid rating value"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def update(self, request, *args, **kwargs):
        """Update a review"""
        review = self.get_object()
        
        if review.player != request.user and request.user.user_type != 'admin':
            return Response(
                {"error": "You can only update your own reviews"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a review"""
        review = self.get_object()
        
        if review.player != request.user and request.user.user_type != 'admin':
            return Response(
                {"error": "You can only delete your own reviews"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

class TournamentViewSet(viewsets.ModelViewSet):
    queryset = Tournament.objects.all()
    serializer_class = TournamentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    filterset_fields = ['pitch', 'organizer']
    search_fields = ['name', 'description']
    ordering_fields = ['date', 'created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.user_type == 'admin':
            return Tournament.objects.all()
        else:
            return Tournament.objects.all()
    
    @action(detail=True, methods=['post'])
    def register_team(self, request, pk=None):
        """Register a team for a tournament"""
        tournament = self.get_object()
        name = request.data.get('name')
        contact_email = request.data.get('contact_email', '')
        contact_phone = request.data.get('contact_phone', '')

        if not name:
            return Response(
                {"error": "Team name is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if registration is still open
        if tournament.registration_deadline and timezone.now().date() > tournament.registration_deadline:
            return Response(
                {"error": "Registration deadline has passed"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if the tournament has reached its maximum number of teams
        if tournament.max_teams and tournament.teams.count() >= tournament.max_teams:
            return Response(
                {"error": "Tournament has reached its maximum number of teams"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for unique team name in this tournament
        if TournamentTeam.objects.filter(tournament=tournament, name=name).exists():
            return Response(
                {"error": "A team with this name already exists in this tournament"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for unique contact email if provided
        if contact_email and TournamentTeam.objects.filter(tournament=tournament, contact_email=contact_email).exists():
            return Response(
                {"error": "This contact email is already registered for another team in this tournament"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for unique contact phone if provided
        if contact_phone and TournamentTeam.objects.filter(tournament=tournament, contact_phone=contact_phone).exists():
            return Response(
                {"error": "This contact phone is already registered for another team in this tournament"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the team
        team = TournamentTeam.objects.create(
            tournament=tournament,
            name=name,
            captain=request.user,
            contact_email=contact_email,
            contact_phone=contact_phone
        )

        # Send confirmation email
        if request.user.email:
            try:
                subject = f'Team Registration Confirmed for {tournament.name}'
                message = f'Your team "{name}" has been successfully registered for the {tournament.name} tournament.'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [request.user.email]
                send_mail(subject, message, from_email, recipient_list)
            except Exception as e:
                # Don't fail the registration if email fails
                pass

        serializer = TournamentTeamSerializer(team)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def get_permissions(self):
        if self.action in ['create', 'register_team']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

class TournamentTeamViewSet(viewsets.ModelViewSet):
    queryset = TournamentTeam.objects.all()
    serializer_class = TournamentTeamSerializer
    filter_backends = []
    if DjangoFilterBackend:
        filter_backends.append(DjangoFilterBackend)
    filterset_fields = ['tournament', 'captain']
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return TournamentTeam.objects.all()
        else:
            return TournamentTeam.objects.all()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['sender', 'recipient', 'is_read']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        user = self.request.user
        # Users can only see messages they sent or received
        return Message.objects.filter(Q(sender=user) | Q(recipient=user))
    
    def create(self, request, *args, **kwargs):
        """Create a new message"""
        recipient_id = request.data.get('recipient_id')
        group_id = request.data.get('group_id')
        content = request.data.get('content')
        
        # Handle group creation with message sending
        create_group_and_send = request.data.get('create_group_and_send')
        recipient_ids = request.data.get('recipient_ids', [])
        group_name = request.data.get('group_name')
        
        print(f"DEBUG: Message creation request data: {request.data}")
        print(f"DEBUG: Content: {content}")
        print(f"DEBUG: Recipient ID: {recipient_id}")
        print(f"DEBUG: Group ID: {group_id}")
        print(f"DEBUG: Create group and send: {create_group_and_send}")
        print(f"DEBUG: Recipient IDs: {recipient_ids}")
        print(f"DEBUG: Group name: {group_name}")
        
        if not content:
            return Response(
                {"error": "Message content is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        recipient = None
        group = None
        
        # Handle support messages (recipient_id = 'support' or None)
        if recipient_id == 'support' or recipient_id is None:
            # Support messages don't need a specific recipient
            print("DEBUG: Creating support message")
            message = Message.objects.create(
                sender=request.user,
                recipient=None,  # Support messages have no specific recipient
                group=None,
                content=content
            )
            serializer = self.get_serializer(message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        # Handle group creation and messaging
        if create_group_and_send:
            if not group_name:
                return Response(
                    {"error": "Group name is required when creating a group"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not recipient_ids or len(recipient_ids) == 0:
                return Response(
                    {"error": "At least one recipient is required when creating a group"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Ensure recipient_ids is a list
            if isinstance(recipient_ids, str):
                try:
                    # Try to parse as JSON
                    import json
                    recipient_ids = json.loads(recipient_ids)
                except (json.JSONDecodeError, ValueError):
                    # If not JSON, treat as single string
                    recipient_ids = [recipient_ids]
            elif not isinstance(recipient_ids, list):
                recipient_ids = [recipient_ids]
            
            print(f"DEBUG: Processed recipient IDs: {recipient_ids}")
            
            # Create the group
            try:
                # Validate that all recipient IDs exist
                recipients = User.objects.filter(id__in=recipient_ids)
                if recipients.count() != len(recipient_ids):
                    return Response(
                        {"error": "One or more recipient IDs are invalid"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create group
                group = MessageGroup.objects.create(
                    name=group_name,
                    description=f"Group created by {request.user.username}",
                    creator=request.user,
                    is_private=True
                )
                
                # Add all members (including creator)
                all_members = list(recipients) + [request.user]
                group.members.add(*all_members)
                
                # Create and send the message to the group
                message = Message.objects.create(
                    sender=request.user,
                    group=group,
                    content=content
                )
                
                serializer = self.get_serializer(message)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response(
                    {"error": f"Failed to create group and send message: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Check for existing group message
        elif group_id:
            try:
                group = MessageGroup.objects.get(id=group_id)
                # Check if user is member of the group
                if not group.members.filter(id=request.user.id).exists():
                    return Response(
                        {"error": "You are not a member of this group"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except MessageGroup.DoesNotExist:
                return Response(
                    {"error": "Group not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Check for direct message
        elif recipient_id:
            try:
                # Handle string recipient IDs
                if isinstance(recipient_id, str) and recipient_id.isdigit():
                    recipient_id = int(recipient_id)
                
                recipient = User.objects.get(id=recipient_id)
                # Prevent sending messages to yourself
                if recipient.id == request.user.id:
                    return Response(
                        {"error": "You cannot send messages to yourself"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except User.DoesNotExist:
                return Response(
                    {"error": "Recipient not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            except ValueError:
                return Response(
                    {"error": "Invalid recipient ID"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {"error": "Either recipient_id, group_id, or create_group_and_send is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for duplicate messages (same sender, recipient/group, and content within 30 seconds)
        from datetime import timedelta
        thirty_seconds_ago = timezone.now() - timedelta(seconds=30)
        
        duplicate_check = Message.objects.filter(
            sender=request.user,
            content=content,
            created_at__gte=thirty_seconds_ago
        )
        
        if group:
            duplicate_check = duplicate_check.filter(group=group)
        else:
            duplicate_check = duplicate_check.filter(recipient=recipient)
        
        if duplicate_check.exists():
            return Response(
                {"error": "Duplicate message detected. Please wait before sending the same message again."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the message (for non-group-creation cases)
        try:
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                group=group,
                content=content
            )
            
            # Send email notification if recipient exists and has email
            
            
            serializer = self.get_serializer(message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {"error": f"Failed to create message: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark a message as read"""
        message = self.get_object()
        
        if message.recipient != request.user:
            return Response(
                {"error": "You can only mark messages you received as read"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message.is_read = True
        message.save()
        
        serializer = self.get_serializer(message)
        return Response(serializer.data)
    
    def get_permissions(self):
        if self.action in ['create', 'mark_as_read']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

class MessageGroupViewSet(viewsets.ModelViewSet):
    queryset = MessageGroup.objects.all()
    serializer_class = MessageGroupSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        user = self.request.user
        # Users can only see groups they are members of
        return MessageGroup.objects.filter(members=user)
    
    def create(self, request, *args, **kwargs):
        """Create a new message group"""
        name = request.data.get('name')
        description = request.data.get('description', '')
        member_ids = request.data.get('member_ids', [])
        is_private = request.data.get('is_private', True)
        
        if not name:
            return Response(
                {"error": "Group name is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the group
        group = MessageGroup.objects.create(
            name=name,
            description=description,
            creator=request.user,
            is_private=is_private
        )
        
        # Add creator as a member
        group.members.add(request.user)
        
        # Add other members if specified
        if member_ids:
            try:
                members = User.objects.filter(id__in=member_ids)
                group.members.add(*members)
            except User.DoesNotExist:
                return Response(
                    {"error": "One or more specified members not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(group)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """Add a member to the group"""
        group = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {"error": "User ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            group.members.add(user)
            
            serializer = self.get_serializer(group)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """Remove a member from the group"""
        group = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {"error": "User ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            if user == group.creator:
                return Response(
                    {"error": "Cannot remove the group creator"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            group.members.remove(user)
            
            serializer = self.get_serializer(group)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def conversations(self, request, pk=None):
        """Get conversation messages for this group"""
        group = self.get_object()
        messages = Message.objects.filter(group=group).order_by('-created_at')
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    def get_permissions(self):
        if self.action in ['create', 'add_member', 'remove_member']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    if DjangoFilterBackend:
        filter_backends.insert(0, DjangoFilterBackend)
    search_fields = ['code', 'description']
    ordering_fields = ['valid_from', 'valid_until', 'created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return Promotion.objects.all()
        else:
            # Non-admin users can only see valid promotions
            return Promotion.objects.filter(
                valid_from__lte=timezone.now(),
                valid_until__gte=timezone.now()
            )
    
    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        """Use a promotion code"""
        promotion = self.get_object()
        
        if not promotion.is_valid():
            return Response(
                {"error": "Promotion code is not valid or has expired"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking_id = request.data.get('booking_id')
        if not booking_id:
            return Response(
                {"error": "Booking ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = Booking.objects.get(id=booking_id, player=request.user)
            
            if booking.status != 'pending':
                return Response(
                    {"error": "Promotion can only be applied to pending bookings"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Apply the promotion
            discount_amount = booking.total_price * (promotion.discount_percentage / 100)
            booking.total_price -= discount_amount
            booking.save()
            
            # Increment the promotion usage count
            promotion.current_uses += 1
            promotion.save()
            
            serializer = BookingSerializer(booking)
            return Response(serializer.data)
            
        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        elif self.action in ['use']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['key']
    search_fields = ['key', 'description']
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return SystemSetting.objects.all()
        else:
            # Non-admin users can only see non-sensitive settings
            return SystemSetting.objects.exclude(key__startswith='admin_')
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

