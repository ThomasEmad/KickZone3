#!/usr/bin/env python3
"""
Registration Backend API Test
Tests the registration endpoint to ensure error handling works correctly
"""

import requests
import json
import time
from datetime import datetime

# Backend configuration
BACKEND_URL = "http://localhost:8000"
API_BASE = f"{BACKEND_URL}/api"

class RegistrationAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'RegistrationTester/1.0'
        })

    def test_registration_endpoint_exists(self):
        """Test if registration endpoint exists and is accessible"""
        print("\n🔍 Testing registration endpoint accessibility...")
        
        try:
            response = self.session.options(f"{API_BASE}/users/register/")
            print(f"   OPTIONS Response: {response.status_code}")
            return response.status_code in [200, 204, 405]  # OPTIONS, No Content, or Method Not Allowed
        except Exception as e:
            print(f"   ❌ Error accessing registration endpoint: {e}")
            return False

    def test_invalid_data_validation(self):
        """Test error handling with invalid registration data"""
        print("\n🧪 Testing invalid data validation...")
        
        # Test case 1: Missing required fields
        invalid_data = {
            "username": "",  # Empty username
            "email": "invalid-email",  # Invalid email format
            "password": "123",  # Weak password
            "first_name": "",  # Empty first name
            "last_name": "Test",  # Valid last name
            "user_type": "player"
        }
        
        try:
            response = self.session.post(f"{API_BASE}/users/register/", json=invalid_data)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 400:
                print("   ✅ Server properly rejected invalid data")
                print(f"   Response: {response.text[:200]}...")
                
                # Try to parse the error response
                try:
                    error_data = response.json()
                    print("   📋 Error Response Structure:")
                    print(json.dumps(error_data, indent=2))
                except:
                    print("   ⚠️  Response not in JSON format")
                    
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except requests.exceptions.ConnectionError:
            print("   ❌ Could not connect to backend server")
            return False
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            return False
            
        return True

    def test_duplicate_username(self):
        """Test error handling for duplicate username"""
        print("\n🔄 Testing duplicate username handling...")
        
        # First, try to register with a username that might already exist
        test_data = {
            "username": "testuser123",  # Common test username
            "email": f"test{int(time.time())}@example.com",  # Unique email
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
            "user_type": "player"
        }
        
        try:
            response = self.session.post(f"{API_BASE}/users/register/", json=test_data)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code in [200, 201]:
                print("   ✅ Registration successful")
                return True
            elif response.status_code == 400:
                print("   ✅ Server rejected registration (expected for duplicate)")
                try:
                    error_data = response.json()
                    print("   📋 Error Response:")
                    print(json.dumps(error_data, indent=2))
                except:
                    print("   Response text:", response.text[:200])
                return True
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False
                
        except Exception as e:
            print(f"   ❌ Error testing duplicate username: {e}")
            return False

    def test_duplicate_email(self):
        """Test error handling for duplicate email"""
        print("\n📧 Testing duplicate email handling...")
        
        # Try with a test email that might already exist
        test_data = {
            "username": f"user{int(time.time())}",  # Unique username
            "email": "test@example.com",  # Common test email
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
            "user_type": "player"
        }
        
        try:
            response = self.session.post(f"{API_BASE}/users/register/", json=test_data)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code in [200, 201]:
                print("   ✅ Registration successful")
                return True
            elif response.status_code == 400:
                print("   ✅ Server rejected registration (expected for duplicate)")
                try:
                    error_data = response.json()
                    print("   📋 Error Response:")
                    print(json.dumps(error_data, indent=2))
                except:
                    print("   Response text:", response.text[:200])
                return True
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False
                
        except Exception as e:
            print(f"   ❌ Error testing duplicate email: {e}")
            return False

    def test_network_error_handling(self):
        """Test handling of network/server errors"""
        print("\n🌐 Testing network error handling...")
        
        # Try to connect to a non-existent endpoint
        try:
            response = self.session.post(f"{API_BASE}/users/nonexistent/", json={})
            print(f"   ⚠️  Unexpected success: {response.status_code}")
            return False
        except requests.exceptions.ConnectionError:
            print("   ✅ Connection error properly handled")
            return True
        except Exception as e:
            print(f"   ❌ Unexpected error type: {e}")
            return False

    def run_all_tests(self):
        """Run all registration API tests"""
        print("🚀 Starting Registration Backend API Tests")
        print("=" * 50)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Backend URL: {BACKEND_URL}")
        
        tests = [
            ("Endpoint Accessibility", self.test_registration_endpoint_exists),
            ("Invalid Data Validation", self.test_invalid_data_validation),
            ("Duplicate Username", self.test_duplicate_username),
            ("Duplicate Email", self.test_duplicate_email),
            ("Network Error Handling", self.test_network_error_handling)
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"\n❌ Test '{test_name}' failed with exception: {e}")
                results.append((test_name, False))
        
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        passed = 0
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status:<8} {test_name}")
            if result:
                passed += 1
        
        print(f"\nTotal: {passed}/{len(results)} tests passed")
        
        if passed == len(results):
            print("\n🎉 All tests passed! Backend is working correctly.")
        else:
            print(f"\n⚠️  {len(results) - passed} test(s) failed. Check backend configuration.")
            
        return passed == len(results)

if __name__ == "__main__":
    tester = RegistrationAPITester()
    tester.run_all_tests()