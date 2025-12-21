"""
Comprehensive test for enhanced form error handling
Tests backend error responses and validation messages
"""

import json
import pytest
from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from kickzone_app.models import Pitch, Booking, Message, Promotion
from kickzone_app.error_handlers import ValidationException, SecurityException, BusinessRuleException

User = get_user_model()


class FormErrorHandlingTestCase(APITestCase):
    """Test case for comprehensive form error handling"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'TestPassword123!',
            'first_name': 'Test',
            'last_name': 'User',
            'user_type': 'player'
        }
        
    def test_registration_validation_errors(self):
        """Test registration form validation errors"""
        url = reverse('register')
        
        # Test empty fields
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
        # Test invalid email
        invalid_data = self.user_data.copy()
        invalid_data['email'] = 'invalid-email'
        response = self.client.post(url, invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('email', str(data))
        
        # Test weak password
        weak_password_data = self.user_data.copy()
        weak_password_data['password'] = '123'
        response = self.client.post(url, weak_password_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
    def test_duplicate_username_error(self):
        """Test duplicate username error handling"""
        url = reverse('register')
        
        # Create first user
        User.objects.create_user(**self.user_data)
        
        # Try to create second user with same username
        duplicate_data = self.user_data.copy()
        duplicate_data['email'] = 'different@example.com'
        response = self.client.post(url, duplicate_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
        # Check that error message is user-friendly
        error_message = data['error']['message']
        self.assertIn('username', error_message.lower())
        self.assertIn('taken', error_message.lower())
        
    def test_duplicate_email_error(self):
        """Test duplicate email error handling"""
        url = reverse('register')
        
        # Create first user
        User.objects.create_user(**self.user_data)
        
        # Try to create second user with same email
        duplicate_data = self.user_data.copy()
        duplicate_data['username'] = 'different_user'
        response = self.client.post(url, duplicate_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
        # Check that error message is user-friendly
        error_message = data['error']['message']
        self.assertIn('email', error_message.lower())
        self.assertIn('already', error_message.lower())
        
    def test_login_validation_errors(self):
        """Test login form validation errors"""
        url = reverse('login')
        
        # Test empty credentials
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test invalid credentials
        invalid_login = {
            'username': 'nonexistent',
            'password': 'wrongpassword'
        }
        response = self.client.post(url, invalid_login)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
    def test_booking_validation_errors(self):
        """Test booking form validation errors"""
        # Create a test user and pitch
        user = User.objects.create_user(
            username='bookinguser',
            email='booking@example.com',
            password='TestPassword123!',
            user_type='player'
        )
        self.client.force_authenticate(user=user)
        
        pitch = Pitch.objects.create(
            name='Test Pitch',
            description='Test pitch for booking',
            price_per_hour=50.00,
            location='Test Location',
            owner=user
        )
        
        url = reverse('booking-list')
        
        # Test invalid booking data
        invalid_booking = {
            'pitch_id': pitch.id,
            'date': '2020-01-01',  # Past date
            'start_time': '25:00',  # Invalid time
        }
        
        response = self.client.post(url, invalid_booking)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
    def test_message_validation_errors(self):
        """Test message form validation errors"""
        # Create test users
        sender = User.objects.create_user(
            username='sender',
            email='sender@example.com',
            password='TestPassword123!',
            user_type='player'
        )
        recipient = User.objects.create_user(
            username='recipient',
            email='recipient@example.com',
            password='TestPassword123!',
            user_type='player'
        )
        
        self.client.force_authenticate(user=sender)
        
        url = reverse('message-list')
        
        # Test empty message
        invalid_message = {
            'recipient_id': recipient.id,
            'content': ''  # Empty content
        }
        
        response = self.client.post(url, invalid_message)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
        # Test non-existent recipient
        invalid_recipient_message = {
            'recipient_id': 99999,  # Non-existent user
            'content': 'Test message'
        }
        
        response = self.client.post(url, invalid_recipient_message)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
    def test_promotion_validation_errors(self):
        """Test promotion form validation errors"""
        # Create a pitch owner
        owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='TestPassword123!',
            user_type='owner'
        )
        
        self.client.force_authenticate(user=owner)
        
        url = reverse('promotion-list')
        
        # Test invalid promotion data
        invalid_promotion = {
            'code': 'INVALID CODE WITH SPACES AND SPECIAL CHARS!@#',
            'discount_percentage': 150,  # Invalid percentage
            'valid_from': '2023-01-01T10:00:00',
            'valid_until': '2023-01-01T09:00:00',  # End before start
        }
        
        response = self.client.post(url, invalid_promotion)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        
    def test_payment_validation_errors(self):
        """Test payment form validation errors"""
        # This would test payment validation if payment processing is implemented
        # For now, we'll test that the endpoint exists and handles errors properly
        
        url = reverse('payment-process')
        
        # Test invalid payment data
        invalid_payment = {
            'booking_id': 99999,  # Non-existent booking
            'payment_method': 'invalid_method'
        }
        
        response = self.client.post(url, invalid_payment)
        # Should return 404 or 400 depending on implementation
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])


class EnhancedErrorMessagesTestCase(TestCase):
    """Test case for enhanced error messages and formatting"""
    
    def test_validation_exception_format(self):
        """Test ValidationException produces correct error format"""
        exc = ValidationException(
            detail="Test validation error",
            code="TEST_VALIDATION_ERROR",
            field="test_field",
            errors=[{"field": "test_field", "message": "Test error message"}]
        )
        
        # This would be processed by the error handler
        # The format should match the expected structure
        expected_format = {
            'error': {
                'code': 'TEST_VALIDATION_ERROR',
                'message': 'Test validation error',
                'field': 'test_field',
                'details': [{"field": "test_field", "message": "Test error message"}],
                'timestamp': exc.timestamp if hasattr(exc, 'timestamp') else None
            }
        }
        
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.default_code, 'validation_error')
        
    def test_security_exception_format(self):
        """Test SecurityException produces correct error format"""
        exc = SecurityException(
            detail="Security violation",
            code="SECURITY_VIOLATION",
            violation_type="suspicious_activity"
        )
        
        self.assertEqual(exc.status_code, 403)
        self.assertEqual(exc.default_code, 'security_violation')
        
    def test_business_rule_exception_format(self):
        """Test BusinessRuleException produces correct error format"""
        exc = BusinessRuleException(
            detail="Business rule violation",
            code="BUSINESS_RULE_VIOLATION",
            rule_name="booking_conflict"
        )
        
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.default_code, 'business_rule_violation')


class ErrorResponseFormatTestCase(APITestCase):
    """Test case for error response format consistency"""
    
    def test_error_response_structure(self):
        """Test that all error responses follow the same structure"""
        url = reverse('register')
        
        # Trigger a validation error
        response = self.client.post(url, {
            'username': '',  # Empty username
            'email': 'invalid-email',  # Invalid email
            'password': '123'  # Weak password
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        
        # Check that response has the expected structure
        self.assertIn('error', data)
        error = data['error']
        
        # All error responses should have these fields
        required_fields = ['code', 'message']
        for field in required_fields:
            self.assertIn(field, error)
            
        # Details should be a list
        if 'details' in error:
            self.assertIsInstance(error['details'], list)
            
    def test_error_timestamp_included(self):
        """Test that error responses include timestamp"""
        url = reverse('register')
        
        response = self.client.post(url, {'username': ''})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = json.loads(response.content)
        error = data['error']
        
        # Timestamp should be included
        self.assertIn('timestamp', error)
        
        # Timestamp should be a valid ISO format string
        timestamp = error['timestamp']
        self.assertIsInstance(timestamp, str)
        # Basic check for ISO format (this is a simplified check)
        self.assertIn('T', timestamp)
        self.assertIn(':', timestamp)


def run_comprehensive_error_tests():
    """Run all error handling tests and generate a report"""
    import subprocess
    import sys
    
    print("🚀 Running Comprehensive Form Error Handling Tests")
    print("=" * 60)
    
    # Run the tests
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            __file__, 
            '-v', 
            '--tb=short',
            '--disable-warnings'
        ], capture_output=True, text=True, cwd='.')
        
        print("✅ Test Results:")
        print(result.stdout)
        
        if result.stderr:
            print("⚠️ Warnings/Errors:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("🎉 All tests passed! Enhanced error handling is working correctly.")
        else:
            print("❌ Some tests failed. Please review the error handling implementation.")
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


if __name__ == '__main__':
    # Run tests when script is executed directly
    success = run_comprehensive_error_tests()
    sys.exit(0 if success else 1)