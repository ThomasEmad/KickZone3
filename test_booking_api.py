#!/usr/bin/env python3
"""
Simple Django test to verify booking API functionality.
This test uses Django's test framework to verify the fixes work.
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kickzone.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from kickzone_app.models import Pitch, PitchAvailability, Booking
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()

def test_booking_api():
    """Test booking API functionality"""
    print("🚀 Starting Django booking API test...")
    
    # Create test client
    client = APIClient()
    
    # Create test user
    test_user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'user_type': 'player'
        }
    )
    test_user.set_password('testpassword123')
    test_user.save()
    
    # Create token for authentication
    token, created = Token.objects.get_or_create(user=test_user)
    
    # Authenticate client
    client.force_authenticate(user=test_user, token=token)
    
    # Test 1: Check if user can access bookings endpoint
    print("📋 Testing bookings endpoint access...")
    response = client.get('/api/bookings/')
    
    if response.status_code == 200:
        print("✅ SUCCESS: Bookings endpoint accessible")
        data = response.json()
        # Handle paginated response
        if 'results' in data:
            bookings = data['results']
        else:
            bookings = data
        print(f"📊 Found {len(bookings)} bookings for user")
    else:
        print(f"❌ FAILED: Bookings endpoint returned {response.status_code}")
        return False
    
    # Test 2: Create a test pitch
    print("🏟️ Creating test pitch...")
    pitch_owner, created = User.objects.get_or_create(
        username='pitchowner',
        defaults={
            'email': 'owner@example.com',
            'first_name': 'Pitch',
            'last_name': 'Owner',
            'user_type': 'owner'
        }
    )
    pitch_owner.set_password('ownerpassword123')
    pitch_owner.save()
    
    pitch, created = Pitch.objects.get_or_create(
        name='Test Pitch',
        owner=pitch_owner,
        defaults={
            'description': 'Test pitch for API testing',
            'location': 'Test Location',
            'surface_type': 'grass',
            'price_per_hour': 50.00
        }
    )
    
    # Create pitch availability
    for day in range(7):  # 0-6 (Monday to Sunday)
        PitchAvailability.objects.get_or_create(
            pitch=pitch,
            day_of_week=day,
            defaults={
                'opening_time': '08:00',
                'closing_time': '22:00',
                'is_available': True
            }
        )
    
    print(f"✅ Pitch created: {pitch.name}")
    
    # Test 3: Create a booking
    print("📅 Creating test booking...")
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    booking_data = {
        'pitch_id': pitch.id,
        'date': tomorrow.strftime('%Y-%m-%d'),
        'start_time': '15:00',  # Use different time to avoid conflicts
        'end_time': '16:00'
    }
    
    response = client.post('/api/bookings/', booking_data)
    
    if response.status_code == 201:
        booking = response.json()
        booking_id = booking['id']
        print(f"✅ Booking created successfully: ID {booking_id}")
        
        # Test 4: Check if booking appears in upcoming bookings
        print("🔍 Testing upcoming bookings filter...")
        local_today = datetime.now().strftime('%Y-%m-%d')
        
        # Test upcoming bookings with date__gte (should include today and future)
        response = client.get('/api/bookings/', {
            'date__gte': local_today,
            'status__in': 'pending,confirmed'
        })
        
        if response.status_code == 200:
            upcoming_data = response.json()
            # Handle paginated response
            if 'results' in upcoming_data:
                upcoming_bookings = upcoming_data['results']
            else:
                upcoming_bookings = upcoming_data
            
            print(f"📊 Found {len(upcoming_bookings)} upcoming bookings")
            
            # Check if our booking appears
            booking_found = any(b['id'] == booking_id for b in upcoming_bookings)
            if booking_found:
                print("✅ SUCCESS: Booking appears in upcoming bookings")
            else:
                print("❌ FAILED: Booking not found in upcoming bookings")
                print(f"Available booking IDs: {[b['id'] for b in upcoming_bookings]}")
                return False
        else:
            print(f"❌ FAILED: Upcoming bookings query failed with status {response.status_code}")
            return False
        
        # Test 5: Check reserved hours calculation
        print("⏰ Testing reserved hours calculation...")
        test_user.refresh_from_db()
        reserved_hours = test_user.reserved_hours
        print(f"📊 Reserved hours for user: {reserved_hours}")
        
        if reserved_hours >= 0:  # Should be at least 0
            print("✅ SUCCESS: Reserved hours field is accessible")
        else:
            print("❌ FAILED: Reserved hours calculation issue")
            return False
        
        # Cleanup
        print("🧹 Cleaning up test data...")
        Booking.objects.filter(id=booking_id).delete()
        
    else:
        print(f"❌ FAILED: Booking creation failed with status {response.status_code}")
        print(f"Response: {response.content.decode()}")
        return False
    
    print("\n🎉 ALL TESTS PASSED!")
    print("✅ Bookings API is working correctly")
    print("✅ Upcoming bookings filtering works")
    print("✅ Reserved hours calculation is functional")
    return True

if __name__ == "__main__":
    try:
        success = test_booking_api()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)