#!/usr/bin/env python3
"""
Debug script to check and fix reserved hours for users.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kickzone.settings')
django.setup()

from kickzone_app.models import User, Booking
from datetime import datetime, timedelta

def debug_reserved_hours():
    """Debug and fix reserved hours"""
    print("🔍 Debugging reserved hours...")
    
    users = User.objects.all()
    print(f"Found {users.count()} users")
    
    updated_count = 0
    
    for user in users:
        print(f"\n👤 User: {user.username}")
        print(f"   Current reserved_hours: {user.reserved_hours}")
        
        # Get user's bookings
        bookings = user.bookings.all()
        print(f"   Total bookings: {bookings.count()}")
        
        # Calculate hours from confirmed and completed bookings
        total_hours = 0
        for booking in bookings:
            if booking.status in ['confirmed', 'completed']:
                # Calculate duration
                start_datetime = datetime.combine(booking.date, booking.start_time)
                end_datetime = datetime.combine(booking.date, booking.end_time)
                duration_hours = (end_datetime - start_datetime).total_seconds() / 3600
                total_hours += duration_hours
                print(f"   📅 Booking {booking.id}: {booking.date} {booking.start_time}-{booking.end_time} ({booking.status}) = {duration_hours}h")
        
        calculated_hours = int(total_hours)
        print(f"   🧮 Calculated hours: {calculated_hours}")
        
        # Update if different
        if calculated_hours != user.reserved_hours:
            user.reserved_hours = calculated_hours
            user.save(update_fields=['reserved_hours'])
            updated_count += 1
            print(f"   ✅ Updated from {user.reserved_hours} to {calculated_hours}")
        else:
            print(f"   ℹ️ No update needed")
    
    print(f"\n🎉 Process complete!")
    print(f"Updated {updated_count} users")

if __name__ == "__main__":
    debug_reserved_hours()