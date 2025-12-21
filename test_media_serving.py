#!/usr/bin/env python
"""
Test script to verify media file serving configuration
"""
import os
import sys
import django

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kickzone.settings')
django.setup()

from django.conf import settings
from django.urls import get_resolver
from kickzone_app.models import Pitch

def test_media_configuration():
    print("=== Media Configuration Test ===\n")
    
    # Check settings
    print(f"DEBUG: {settings.DEBUG}")
    print(f"MEDIA_URL: {settings.MEDIA_URL}")
    print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
    print(f"WHITENOISE_USE_FINDERS: {getattr(settings, 'WHITENOISE_USE_FINDERS', 'Not set')}")
    print()
    
    # Check if media root exists
    if os.path.exists(settings.MEDIA_ROOT):
        print("✓ Media root directory exists")
        media_files = []
        for root, dirs, files in os.walk(settings.MEDIA_ROOT):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    media_files.append(os.path.join(root, file))
        print(f"✓ Found {len(media_files)} image files in media directory")
        
        if media_files:
            print("\nSample media files:")
            for i, file_path in enumerate(media_files[:5]):  # Show first 5
                relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
                url = f"{settings.MEDIA_URL}{relative_path}"
                print(f"  {i+1}. {url}")
    else:
        print("✗ Media root directory does not exist")
    
    # Check URL patterns
    print(f"\n=== URL Patterns ===")
    resolver = get_resolver()
    url_patterns = []
    
    def collect_patterns(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, 'url_patterns'):
                collect_patterns(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                url_patterns.append(prefix + str(pattern.pattern))
    
    collect_patterns(resolver.url_patterns)
    
    media_patterns = [p for p in url_patterns if 'media' in p]
    print("Media-related URL patterns:")
    for pattern in media_patterns:
        print(f"  {pattern}")
    
    # Check Pitch model for images
    print(f"\n=== Pitch Model Image Test ===")
    pitches_with_images = Pitch.objects.filter(image__isnull=False).exclude(image='')
    print(f"Pitches with images: {pitches_with_images.count()}")
    
    if pitches_with_images.exists():
        print("Sample pitch images:")
        for pitch in pitches_with_images[:3]:  # Show first 3
            if pitch.image:
                print(f"  - {pitch.name}: {pitch.image.url}")
    
    print(f"\n=== Configuration Complete ===")
    print("Your media files should now be accessible at:")
    print(f"  Base URL: {settings.MEDIA_URL}")
    print(f"  Example: {settings.MEDIA_URL}pitch_images/Urban_Soccer_Center_2.jpg")

if __name__ == "__main__":
    test_media_configuration()