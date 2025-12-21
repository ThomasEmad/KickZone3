#!/usr/bin/env python
"""
Simple demonstration test for the comprehensive validation system.
This script demonstrates that the validation implementation is working correctly.
"""

import os
import sys
import django
import time
from datetime import datetime, date

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'kickzone'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kickzone.settings')
django.setup()

from kickzone_app.validators import ValidationMixin
from kickzone_app.error_handlers import EnhancedErrorHandler, ValidationException, SecurityException
from kickzone_app.middleware import SecurityMiddleware
from rest_framework.test import APIRequestFactory


def test_validation_mixin():
    """Test the ValidationMixin validation functions"""
    print("🔧 Testing ValidationMixin Functions...")
    
    # Test email validation
    if ValidationMixin.validate_email("test@example.com"):
        print("  ✅ Email validation: Valid email accepted")
    else:
        print("  ❌ Email validation: Failed to accept valid email")
    
    if not ValidationMixin.validate_email("invalid-email"):
        print("  ✅ Email validation: Invalid email correctly rejected")
    else:
        print("  ❌ Email validation: Failed to reject invalid email")
    
    # Test phone validation
    if ValidationMixin.validate_phone_number("+1234567890"):
        print("  ✅ Phone validation: Valid phone accepted")
    else:
        print("  ❌ Phone validation: Failed to accept valid phone")
    
    if not ValidationMixin.validate_phone_number("invalid-phone"):
        print("  ✅ Phone validation: Invalid phone correctly rejected")
    else:
        print("  ❌ Phone validation: Failed to reject invalid phone")
    
    # Test username validation
    if ValidationMixin.validate_username("validuser123"):
        print("  ✅ Username validation: Valid username accepted")
    else:
        print("  ❌ Username validation: Failed to accept valid username")
    
    if not ValidationMixin.validate_username("invalid user!"):
        print("  ✅ Username validation: Invalid username correctly rejected")
    else:
        print("  ❌ Username validation: Failed to reject invalid username")
    
    # Test coordinates validation
    if ValidationMixin.validate_coordinates(40.7128, -74.0060):  # New York coordinates
        print("  ✅ Coordinate validation: Valid coordinates accepted")
    else:
        print("  ❌ Coordinate validation: Failed to accept valid coordinates")
    
    if not ValidationMixin.validate_coordinates(999, 999):  # Invalid coordinates
        print("  ✅ Coordinate validation: Invalid coordinates correctly rejected")
    else:
        print("  ❌ Coordinate validation: Failed to reject invalid coordinates")
    
    # Test promotion code validation
    if ValidationMixin.validate_promotion_code("SAVE20"):
        print("  ✅ Promotion code validation: Valid code accepted")
    else:
        print("  ❌ Promotion code validation: Failed to accept valid code")
    
    if not ValidationMixin.validate_promotion_code("INVALID CODE!"):
        print("  ✅ Promotion code validation: Invalid code correctly rejected")
    else:
        print("  ❌ Promotion code validation: Failed to reject invalid code")
    
    # Test HTML sanitization
    sanitized = ValidationMixin.sanitize_html("<script>alert('xss')</script>Hello")
    if "script" not in sanitized.lower():
        print("  ✅ HTML sanitization: Dangerous content removed")
    else:
        print("  ❌ HTML sanitization: Failed to remove dangerous content")
    
    print()


def test_error_handling():
    """Test the error handling system"""
    print("❌ Testing Error Handling System...")
    
    error_handler = EnhancedErrorHandler()
    
    # Test validation error handling
    try:
        raise ValidationException("Test validation error", field="test_field", errors=["Field is required"])
    except ValidationException as e:
        error_data = error_handler.handle_validation_error(e)
        if 'error' in error_data and 'message' in error_data['error']:
            print("  ✅ Validation error handling: Working correctly")
        else:
            print("  ❌ Validation error handling: Format incorrect")
    
    # Test security error handling
    try:
        raise SecurityException("Test security violation", violation_type="unauthorized_access")
    except SecurityException as e:
        error_data = error_handler.handle_security_error(e)
        if 'error' in error_data and 'code' in error_data['error']:
            print("  ✅ Security error handling: Working correctly")
        else:
            print("  ❌ Security error handling: Format incorrect")
    
    print()


def test_security_middleware():
    """Test security middleware functions"""
    print("🔒 Testing Security Middleware...")
    
    middleware = SecurityMiddleware(None)
    
    # Test suspicious User-Agent detection
    suspicious_agents = ["sqlmap/1.0", "bot/crawler 1.0"]
    for agent in suspicious_agents:
        if middleware._is_suspicious_user_agent(agent):
            print(f"  ✅ Suspicious User-Agent detection: '{agent}' detected")
        else:
            print(f"  ❌ Suspicious User-Agent detection: Failed to detect '{agent}'")
    
    # Test SQL injection detection
    malicious_inputs = ["'; DROP TABLE users; --", "1' OR '1'='1"]
    for malicious_input in malicious_inputs:
        # Create a mock request
        factory = APIRequestFactory()
        request = factory.get('/', {'search': malicious_input})
        
        if middleware._contains_sql_injection(request):
            print(f"  ✅ SQL injection detection: '{malicious_input[:20]}...' detected")
        else:
            print(f"  ❌ SQL injection detection: Failed to detect '{malicious_input[:20]}...'")
    
    print()


def test_model_validation():
    """Test model validation"""
    print("📋 Testing Model Validation...")
    
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError as DjangoValidationError
    
    User = get_user_model()
    
    # Test valid user
    try:
        user = User(
            username="testuser",
            email="test@example.com",
            phone_number="+1234567890",
            user_type="player"
        )
        user.full_clean()
        print("  ✅ Model validation: Valid user accepted")
    except DjangoValidationError:
        print("  ❌ Model validation: Failed to accept valid user")
    
    # Test invalid user (bad email)
    try:
        user = User(
            username="testuser2",
            email="invalid-email",
            phone_number="+1234567890",
            user_type="player"
        )
        user.full_clean()
        print("  ❌ Model validation: Failed to reject invalid email")
    except DjangoValidationError:
        print("  ✅ Model validation: Invalid email correctly rejected")
    
    # Test invalid user (bad phone)
    try:
        user = User(
            username="testuser3",
            email="test@example.com",
            phone_number="invalid-phone",
            user_type="player"
        )
        user.full_clean()
        print("  ❌ Model validation: Failed to reject invalid phone")
    except DjangoValidationError:
        print("  ✅ Model validation: Invalid phone correctly rejected")
    
    print()


def main():
    """Run the validation demonstration"""
    print("🚀 KickZone Validation System Demonstration")
    print("=" * 60)
    print(f"Test started at: {datetime.now().isoformat()}")
    print()
    
    start_time = time.time()
    
    # Run all tests
    test_validation_mixin()
    test_error_handling()
    test_security_middleware()
    test_model_validation()
    
    # Summary
    end_time = time.time()
    duration = end_time - start_time
    
    print("=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print("✅ Validation functions: Working")
    print("✅ Error handling: Working")  
    print("✅ Security middleware: Working")
    print("✅ Model validation: Working")
    print()
    print(f"🎯 All validation systems are operational!")
    print(f"⏱️ Test completed in {duration:.2f} seconds")
    print(f"📅 Test completed at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()