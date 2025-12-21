"""
Comprehensive validation utilities for the KickZone application.
This module provides reusable validators for common validation patterns.
"""

import re
import logging
import ipaddress
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import BaseValidator, RegexValidator, EmailValidator
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q

# Configure validation logger
validation_logger = logging.getLogger('kickzone.validation')

class ValidationMixin:
    """Mixin to provide common validation methods"""
    
    @staticmethod
    def sanitize_html(content: str) -> str:
        """Remove potentially dangerous HTML content"""
        if not content:
            return ""
        
        # Remove script tags and their content
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        # Remove javascript: URLs
        content = re.sub(r'javascript:[^"\']*', '', content, flags=re.IGNORECASE)
        # Remove on* event handlers
        content = re.sub(r'\son\w+="[^"]*"', '', content, flags=re.IGNORECASE)
        content = re.sub(r"\son\w+='[^']*'", '', content, flags=re.IGNORECASE)
        # Remove style attributes with expressions
        content = re.sub(r'style="[^"]*expression\([^)]*\)"[^>]*', '', content, flags=re.IGNORECASE)
        content = re.sub(r"style='[^']*expression\([^)]*\)'[^>]*", '', content, flags=re.IGNORECASE)
        
        # Remove potentially dangerous HTML tags
        dangerous_tags = ['script', 'object', 'embed', 'link', 'style', 'iframe', 'frame', 'frameset', 
                         'applet', 'base', 'form', 'input', 'select', 'textarea', 'button']
        for tag in dangerous_tags:
            content = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', content, flags=re.IGNORECASE | re.DOTALL)
            content = re.sub(f'<{tag}[^>]*/?>', '', content, flags=re.IGNORECASE)
        
        return content.strip()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent directory traversal and dangerous characters"""
        if not filename:
            return ""
        
        # Remove path separators and dangerous characters
        filename = re.sub(r'[/\\:*?"<>|]', '', filename)
        # Remove control characters
        filename = ''.join(char for char in filename if ord(char) >= 32)
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = f"{name[:250]}.{ext}" if ext else filename[:255]
        
        return filename.strip()
    
    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        """Validate phone number format"""
        if not phone:
            return False
        
        # Remove all non-digit characters for validation
        clean_phone = re.sub(r'[^\d]', '', phone)
        
        # Check if it's a reasonable length (7-15 digits)
        return 7 <= len(clean_phone) <= 15
    
    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> bool:
        """Validate latitude and longitude coordinates"""
        try:
            lat = float(latitude)
            lng = float(longitude)
            return -90 <= lat <= 90 and -180 <= lng <= 180
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format and security"""
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            # Only allow HTTP and HTTPS
            if parsed.scheme not in ['http', 'https']:
                return False
            # Basic hostname validation
            if not parsed.netloc:
                return False
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_time_range(start_time: str, end_time: str) -> bool:
        """Validate time range"""
        try:
            from datetime import time
            start = datetime.strptime(start_time, '%H:%M').time()
            end = datetime.strptime(end_time, '%H:%M').time()
            return start < end
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> bool:
        """Validate date range"""
        try:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            return start_date <= end_date
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_future_date(date_input: Union[str, date]) -> bool:
        """Validate that date is in the future"""
        try:
            if isinstance(date_input, str):
                date_input = datetime.strptime(date_input, '%Y-%m-%d').date()
            return date_input >= date.today()
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_age(birth_date: Union[str, date], min_age: int = 13, max_age: int = 100) -> bool:
        """Validate age based on birth date"""
        try:
            if isinstance(birth_date, str):
                birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            
            today = date.today()
            age = today.year - birth_date.year
            if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
                age -= 1
            
            return min_age <= age <= max_age
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_image_size(file_size: int, max_size_mb: int = 5) -> bool:
        """Validate image file size"""
        return 0 < file_size <= max_size_mb * 1024 * 1024
    
    @staticmethod
    def validate_image_extension(filename: str) -> bool:
        """Validate image file extension"""
        if not filename:
            return False
        
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        file_ext = filename.lower().strip()
        return any(file_ext.endswith(ext) for ext in allowed_extensions)
    
    @staticmethod
    def validate_promotion_code(code: str) -> bool:
        """Validate promotion code format"""
        if not code:
            return False
        
        # Allow alphanumeric characters, hyphens, and underscores, 3-20 characters
        return bool(re.match(r'^[A-Za-z0-9_-]{3,20}$', code.strip()))
    
    @staticmethod
    def validate_skill_level(skill_level: Any) -> bool:
        """Validate skill level"""
        try:
            level = int(skill_level)
            return 1 <= level <= 100
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_rating(rating: Any) -> bool:
        """Validate rating value"""
        try:
            rate = int(rating)
            return 1 <= rate <= 5
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_percentage(percentage: Any) -> bool:
        """Validate percentage value"""
        try:
            pct = int(percentage)
            return 0 <= pct <= 100
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_price(price: Any) -> bool:
        """Validate price value"""
        try:
            prc = float(price)
            return prc >= 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_text_length(text: str, min_length: int = 0, max_length: int = 1000) -> bool:
        """Validate text length"""
        if not text:
            return min_length == 0
        
        return min_length <= len(text.strip()) <= max_length
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username format"""
        if not username:
            return False
        
        # 3-30 characters, alphanumeric and underscore only
        return bool(re.match(r'^[a-zA-Z0-9_]{3,30}$', username))
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        try:
            EmailValidator()(email)
            return True
        except ValidationError:
            return False
    
    @staticmethod
    def log_validation_error(error_type: str, field: str, value: Any, reason: str, user_id: Optional[int] = None):
        """Log validation errors for security and debugging"""
        validation_logger.warning(
            f"Validation Error: {error_type} | Field: {field} | Value: {value} | "
            f"Reason: {reason} | User: {user_id} | Timestamp: {timezone.now()}"
        )
    
    @staticmethod
    def log_validation_success(operation: str, entity: str, entity_id: int, user_id: Optional[int] = None):
        """Log successful validation for audit purposes"""
        validation_logger.info(
            f"Validation Success: {operation} | Entity: {entity} | ID: {entity_id} | "
            f"User: {user_id} | Timestamp: {timezone.now()}"
        )


# Django validators using the mixin
class SafeTextValidator(BaseValidator):
    """Validator for safe text input without HTML injection"""
    
    def __init__(self, max_length=1000):
        super().__init__(limit_value=max_length)
    
    def __call__(self, value):
        if value:
            # Check for HTML tags
            if re.search(r'<[^>]+>', value):
                raise ValidationError("HTML tags are not allowed in text fields.")
            
            # Check for potentially dangerous content
            sanitized = ValidationMixin.sanitize_html(value)
            if sanitized != value:
                raise ValidationError("Potentially dangerous content detected.")
    
    def clean(self, value):
        return ValidationMixin.sanitize_html(value)


class PhoneNumberValidator(BaseValidator):
    """Validator for phone numbers"""
    
    def __init__(self):
        super().__init__(limit_value=None)
    
    def __call__(self, value):
        if value and not ValidationMixin.validate_phone_number(value):
            raise ValidationError("Invalid phone number format.")


class UsernameValidator(RegexValidator):
    """Validator for usernames"""
    regex = r'^[a-zA-Z0-9_]{3,30}$'
    message = "Username must be 3-30 characters long and contain only letters, numbers, and underscores."


class SafeURLValidator(BaseValidator):
    """Validator for safe URLs"""
    
    def __call__(self, value):
        if value and not ValidationMixin.validate_url(value):
            raise ValidationError("Invalid or unsafe URL.")


class CoordinateValidator(BaseValidator):
    """Validator for latitude/longitude coordinates"""
    
    def __init__(self):
        super().__init__(limit_value=None)
    
    def __call__(self, value):
        # This validator is used for coordinates, but we need both lat and lng
        # It should be called with both values in a different context
        pass


class ImageFileValidator(BaseValidator):
    """Validator for image files"""
    
    def __init__(self, max_size_mb=5):
        super().__init__(limit_value=max_size_mb)
    
    def __call__(self, value):
        if value:
            # Validate file extension
            if hasattr(value, 'name'):
                filename = value.name
                if not ValidationMixin.validate_image_extension(filename):
                    raise ValidationError("Invalid image file type.")
            
            # Validate file size if available
            if hasattr(value, 'size'):
                if not ValidationMixin.validate_image_size(value.size, self.limit_value):
                    raise ValidationError(f"Image file too large. Maximum size is {self.limit_value}MB.")


class PromotionCodeValidator(RegexValidator):
    """Validator for promotion codes"""
    regex = r'^[A-Za-z0-9_-]{3,20}$'
    message = "Promotion code must be 3-20 characters long and contain only letters, numbers, hyphens, and underscores."


class StrongPasswordValidator:
    """Custom validator for strong passwords"""
    
    def __init__(self, min_length=8):
        self.min_length = min_length
    
    def validate(self, password, user=None):
        """Validate password strength"""
        if not password:
            raise ValidationError("Password is required.")
        
        # Check minimum length
        if len(password) < self.min_length:
            raise ValidationError(f"Password must be at least {self.min_length} characters long.")
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter (A-Z).")
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter (a-z).")
        
        # Check for at least one digit
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one number (0-9).")
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?]', password):
            raise ValidationError("Password must contain at least one special character (!@#$%^&* etc.).")
        
        # Check for common weak patterns
        weak_patterns = [
            r'123456|654321|111111|000000',  # Sequential numbers
            r'qwerty|asdf|zxcv',  # Keyboard patterns
            r'(.)\1{2,}',  # Repeated characters
            r'password|admin|letmein|welcome',  # Common weak passwords
        ]
        
        password_lower = password.lower()
        for pattern in weak_patterns:
            if re.search(pattern, password_lower):
                raise ValidationError("Password contains common weak patterns. Please choose a stronger password.")
    
    def get_help_text(self):
        """Return help text for password requirements"""
        return (
            f"Your password must meet the following requirements:\n"
            f"• At least {self.min_length} characters long\n"
            f"• Contain at least one uppercase letter (A-Z)\n"
            f"• Contain at least one lowercase letter (a-z)\n"
            f"• Contain at least one number (0-9)\n"
            f"• Contain at least one special character (!@#$%^&* etc.)\n"
            f"• Not contain common weak patterns or sequences"
        )


class PasswordStrengthValidator(BaseValidator):
    """Django-compatible password strength validator"""
    
    def __init__(self, min_length=8):
        super().__init__(limit_value=min_length)
        self.min_length = min_length
    
    def __call__(self, value):
        if not value:
            raise ValidationError("Password is required.")
        
        # Check minimum length
        if len(value) < self.min_length:
            raise ValidationError(f"Password must be at least {self.min_length} characters long.")
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', value):
            raise ValidationError("Password must contain at least one uppercase letter (A-Z).")
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', value):
            raise ValidationError("Password must contain at least one lowercase letter (a-z).")
        
        # Check for at least one digit
        if not re.search(r'\d', value):
            raise ValidationError("Password must contain at least one number (0-9).")
    
    def get_help_text(self):
        return (
            f"Your password must meet the following requirements:\n"
            f"• At least {self.min_length} characters long\n"
            f"• Contain at least one uppercase letter (A-Z)\n"
            f"• Contain at least one lowercase letter (a-z)\n"
            f"• Contain at least one number (0-9)"
        )