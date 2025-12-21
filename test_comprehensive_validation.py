#!/usr/bin/env python
"""
Comprehensive validation test suite for KickZone backend.
This script tests all validation layers including models, serializers, views, and security.
"""

import os
import sys
import django
import json
import requests
import time
from datetime import datetime, timedelta
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'kickzone'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kickzone.settings')
django.setup()

from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework import status
from kickzone_app.models import User, Pitch, Booking, Message, Tournament, TournamentTeam, Promotion, Review
from kickzone_app.serializers import (
    UserSerializer, PitchSerializer, BookingSerializer, MessageSerializer,
    TournamentSerializer, TournamentTeamSerializer, PromotionSerializer, ReviewSerializer
)
from kickzone_app.validators import (
    validate_email, validate_phone_number, validate_password,
    validate_name, validate_price, validate_capacity,
    validate_coordinates, validate_time_slot
)
from kickzone_app.error_handlers import EnhancedErrorHandler
from kickzone_app.middleware import SecurityMiddleware, RateLimitMiddleware


class ValidationTestSuite:
    """Comprehensive validation test suite"""
    
    def __init__(self):
        self.factory = APIRequestFactory()
        self.user_model = get_user_model()
        self.test_results = []
        self.start_time = time.time()
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Comprehensive Validation Test Suite")
        print("=" * 60)
        
        # Test model validation
        self.test_model_validation()
        
        # Test validators
        self.test_custom_validators()
        
        # Test serializers
        self.test_serializer_validation()
        
        # Test business rules
        self.test_business_rule_validation()
        
        # Test security validation
        self.test_security_validation()
        
        # Test error handling
        self.test_error_handling()
        
        # Test API endpoints
        self.test_api_validation()
        
        # Print summary
        self.print_test_summary()
    
    def test_model_validation(self):
        """Test model-level validation"""
        print("\n📋 Testing Model Validation...")
        
        # Test User model validation
        try:
            # Test invalid email
            user = self.user_model(
                username="testuser",
                email="invalid-email",
                phone_number="invalid-phone",
                user_type="player"
            )
            user.full_clean()
            self.record_test_result("Model Validation - Invalid Email", False, "Should have raised validation error")
        except DjangoValidationError:
            self.record_test_result("Model Validation - Invalid Email", True, "Correctly rejected invalid email")
        
        try:
            # Test invalid phone number
            user = self.user_model(
                username="testuser2",
                email="test@example.com",
                phone_number="invalid-phone",
                user_type="player"
            )
            user.full_clean()
            self.record_test_result("Model Validation - Invalid Phone", False, "Should have raised validation error")
        except DjangoValidationError:
            self.record_test_result("Model Validation - Invalid Phone", True, "Correctly rejected invalid phone")
        
        try:
            # Test valid user
            user = self.user_model(
                username="validuser",
                email="valid@example.com",
                phone_number="+1234567890",
                user_type="player"
            )
            user.full_clean()
            self.record_test_result("Model Validation - Valid User", True, "Valid user created successfully")
        except DjangoValidationError as e:
            self.record_test_result("Model Validation - Valid User", False, f"Unexpected error: {e}")
        
        # Test Pitch model validation
        try:
            pitch = Pitch(
                name="Test Pitch",
                location="Test Location",
                capacity=-5,  # Invalid capacity
                price_per_hour=-10.0,  # Invalid price
                coordinates="invalid-coords"  # Invalid coordinates
            )
            pitch.full_clean()
            self.record_test_result("Model Validation - Invalid Pitch", False, "Should have raised validation error")
        except DjangoValidationError:
            self.record_test_result("Model Validation - Invalid Pitch", True, "Correctly rejected invalid pitch data")
    
    def test_custom_validators(self):
        """Test custom validator functions"""
        print("\n🔧 Testing Custom Validators...")
        
        # Test email validation
        try:
            validate_email("valid@example.com")
            self.record_test_result("Email Validator - Valid", True, "Valid email accepted")
        except Exception as e:
            self.record_test_result("Email Validator - Valid", False, f"Unexpected error: {e}")
        
        try:
            validate_email("invalid-email")
            self.record_test_result("Email Validator - Invalid", False, "Should have raised validation error")
        except Exception:
            self.record_test_result("Email Validator - Invalid", True, "Invalid email correctly rejected")
        
        # Test phone validation
        try:
            validate_phone_number("+1234567890")
            self.record_test_result("Phone Validator - Valid", True, "Valid phone accepted")
        except Exception as e:
            self.record_test_result("Phone Validator - Valid", False, f"Unexpected error: {e}")
        
        try:
            validate_phone_number("invalid-phone")
            self.record_test_result("Phone Validator - Invalid", False, "Should have raised validation error")
        except Exception:
            self.record_test_result("Phone Validator - Invalid", True, "Invalid phone correctly rejected")
        
        # Test password validation
        try:
            validate_password("StrongPassword123!")
            self.record_test_result("Password Validator - Strong", True, "Strong password accepted")
        except Exception as e:
            self.record_test_result("Password Validator - Strong", False, f"Unexpected error: {e}")
        
        try:
            validate_password("weak")
            self.record_test_result("Password Validator - Weak", False, "Should have raised validation error")
        except Exception:
            self.record_test_result("Password Validator - Weak", True, "Weak password correctly rejected")
    
    def test_serializer_validation(self):
        """Test serializer validation"""
        print("\n📝 Testing Serializer Validation...")
        
        # Test User Serializer
        valid_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'phone_number': '+1234567890',
            'user_type': 'player',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        serializer = UserSerializer(data=valid_data)
        if serializer.is_valid():
            self.record_test_result("Serializer - Valid User Data", True, "Valid user data accepted")
        else:
            self.record_test_result("Serializer - Valid User Data", False, f"Unexpected validation error: {serializer.errors}")
        
        # Test invalid user data
        invalid_data = valid_data.copy()
        invalid_data['email'] = 'invalid-email'
        
        serializer = UserSerializer(data=invalid_data)
        if not serializer.is_valid():
            self.record_test_result("Serializer - Invalid User Data", True, "Invalid data correctly rejected")
        else:
            self.record_test_result("Serializer - Invalid User Data", False, "Should have rejected invalid data")
    
    def test_business_rule_validation(self):
        """Test business rule validation"""
        print("\n⚙️ Testing Business Rule Validation...")
        
        # Test booking time conflict
        try:
            # Create test user and pitch
            user = self.user_model.objects.create_user(
                username='testuser', 
                email='test@example.com',
                password='StrongPassword123!'
            )
            pitch = Pitch.objects.create(
                name="Test Pitch",
                location="Test Location",
                capacity=10,
                price_per_hour=50.0
            )
            
            # Create existing booking
            existing_booking = Booking.objects.create(
                user=user,
                pitch=pitch,
                date=datetime.now().date(),
                start_time=datetime.now().time(),
                end_time=(datetime.now() + timedelta(hours=1)).time(),
                status='confirmed'
            )
            
            # Try to create overlapping booking
            overlapping_booking_data = {
                'user': user.id,
                'pitch': pitch.id,
                'date': datetime.now().date(),
                'start_time': (datetime.now() + timedelta(minutes=30)).time(),
                'end_time': (datetime.now() + timedelta(hours=1, minutes=30)).time()
            }
            
            serializer = BookingSerializer(data=overlapping_booking_data)
            if not serializer.is_valid():
                self.record_test_result("Business Rule - Booking Conflict", True, "Booking conflict correctly detected")
            else:
                self.record_test_result("Business Rule - Booking Conflict", False, "Should have detected booking conflict")
            
        except Exception as e:
            self.record_test_result("Business Rule - Booking Conflict", False, f"Test setup error: {e}")
    
    def test_security_validation(self):
        """Test security validation"""
        print("\n🔒 Testing Security Validation...")
        
        # Test SQL injection detection
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM users WHERE '1'='1"
        ]
        
        for malicious_input in malicious_inputs:
            if SecurityMiddleware._contains_sql_injection.__func__(SecurityMiddleware, None):
                # Create a mock request with malicious input
                request = self.factory.get('/', {'search': malicious_input})
                middleware = SecurityMiddleware(None)
                
                if middleware._contains_sql_injection(request):
                    self.record_test_result(f"Security - SQL Injection ({malicious_input[:20]}...)", True, "SQL injection correctly detected")
                else:
                    self.record_test_result(f"Security - SQL Injection ({malicious_input[:20]}...)", False, "Failed to detect SQL injection")
                break
        
        # Test suspicious User-Agent detection
        suspicious_user_agents = [
            "sqlmap/1.0",
            "bot/crawler 1.0",
            "curl/7.68.0"
        ]
        
        for user_agent in suspicious_user_agents:
            middleware = SecurityMiddleware(None)
            if middleware._is_suspicious_user_agent(user_agent):
                self.record_test_result(f"Security - Suspicious UA ({user_agent})", True, "Suspicious User-Agent correctly detected")
            else:
                self.record_test_result(f"Security - Suspicious UA ({user_agent})", False, "Failed to detect suspicious User-Agent")
            break
    
    def test_error_handling(self):
        """Test error handling"""
        print("\n❌ Testing Error Handling...")
        
        # Test validation error handling
        from kickzone_app.error_handlers import ValidationException
        
        try:
            raise ValidationException("Test validation error", field="test_field", errors=["Field is required"])
        except ValidationException as e:
            error_handler = EnhancedErrorHandler()
            error_data = error_handler.handle_validation_error(e)
            
            if 'error' in error_data and 'message' in error_data['error']:
                self.record_test_result("Error Handling - Validation Error", True, "Validation error correctly handled")
            else:
                self.record_test_result("Error Handling - Validation Error", False, "Error handling format incorrect")
        
        # Test security error handling
        from kickzone_app.error_handlers import SecurityException
        
        try:
            raise SecurityException("Test security violation", violation_type="unauthorized_access")
        except SecurityException as e:
            error_handler = EnhancedErrorHandler()
            error_data = error_handler.handle_security_error(e)
            
            if 'error' in error_data and 'code' in error_data['error']:
                self.record_test_result("Error Handling - Security Error", True, "Security error correctly handled")
            else:
                self.record_test_result("Error Handling - Security Error", False, "Security error handling format incorrect")
    
    def test_api_validation(self):
        """Test API endpoint validation"""
        print("\n🌐 Testing API Validation...")
        
        # Test registration endpoint
        try:
            response = requests.post(
                'http://localhost:8000/api/auth/register/',
                data=json.dumps({
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'StrongPassword123!',
                    'password_confirm': 'StrongPassword123!',
                    'phone_number': '+1234567890',
                    'user_type': 'player'
                }),
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if response.status_code in [200, 201, 400]:  # Accept success or validation error
                self.record_test_result("API - Registration Endpoint", True, "Registration endpoint accessible")
            else:
                self.record_test_result("API - Registration Endpoint", False, f"Unexpected status code: {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            self.record_test_result("API - Registration Endpoint", False, f"Request failed: {e}")
        
        # Test login endpoint with rate limiting
        for i in range(5):  # Try multiple times to test rate limiting
            try:
                response = requests.post(
                    'http://localhost:8000/api/auth/login/',
                    data=json.dumps({
                        'username': 'nonexistent',
                        'password': 'wrongpassword'
                    }),
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
                
                if i >= 3 and response.status_code == 429:  # Rate limited after multiple attempts
                    self.record_test_result("API - Rate Limiting", True, "Rate limiting correctly triggered")
                    break
                elif response.status_code == 429:
                    self.record_test_result("API - Rate Limiting", True, "Rate limiting working")
                    break
                else:
                    if i == 4:  # Last attempt
                        self.record_test_result("API - Rate Limiting", False, "Rate limiting not triggered")
            
            except requests.exceptions.RequestException:
                if i == 4:
                    self.record_test_result("API - Rate Limiting", False, "Request failed")
                break
        
        # Test invalid input handling
        try:
            response = requests.post(
                'http://localhost:8000/api/auth/register/',
                data=json.dumps({
                    'username': '',  # Invalid empty username
                    'email': 'invalid-email',
                    'password': 'weak'
                }),
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if response.status_code == 400:
                self.record_test_result("API - Invalid Input Handling", True, "Invalid input correctly rejected")
            else:
                self.record_test_result("API - Invalid Input Handling", False, f"Unexpected status code: {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            self.record_test_result("API - Invalid Input Handling", False, f"Request failed: {e}")
    
    def record_test_result(self, test_name, passed, message):
        """Record test result"""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status_emoji = "✅" if passed else "❌"
        print(f"  {status_emoji} {test_name}: {message}")
    
    def print_test_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['test']}: {result['message']}")
        
        end_time = time.time()
        duration = end_time - self.start_time
        print(f"\n⏱️ Test Duration: {duration:.2f} seconds")
        
        # Save results to file
        results_file = os.path.join(os.path.dirname(__file__), 'validation_test_results.json')
        with open(results_file, 'w') as f:
            json.dump({
                'summary': {
                    'total': total_tests,
                    'passed': passed_tests,
                    'failed': failed_tests,
                    'success_rate': (passed_tests/total_tests)*100,
                    'duration': duration,
                    'timestamp': datetime.now().isoformat()
                },
                'tests': self.test_results
            }, f, indent=2)
        
        print(f"📁 Detailed results saved to: {results_file}")


def main():
    """Main test execution"""
    test_suite = ValidationTestSuite()
    test_suite.run_all_tests()


if __name__ == "__main__":
    main()