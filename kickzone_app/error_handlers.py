"""
Comprehensive error handling utilities and custom exceptions.
This module provides structured error handling, logging, and user-friendly error messages.
"""

import logging
import traceback
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError, NotFound, PermissionDenied, AuthenticationFailed
from rest_framework.response import Response
from rest_framework import status

# Configure error handler logger
error_handler_logger = logging.getLogger('kickzone.error_handlers')


class ValidationException(APIException):
    """Custom validation exception with detailed error information"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Validation failed."
    default_code = 'validation_error'
    
    def __init__(self, detail=None, code=None, field=None, errors=None):
        self.field = field
        self.errors = errors or []
        
        if detail is None:
            detail = self.default_detail
        
        if code is None:
            code = self.default_code
        
        super().__init__(detail, code)


class SecurityException(APIException):
    """Custom security-related exception"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Security policy violation."
    default_code = 'security_violation'
    
    def __init__(self, detail=None, code=None, violation_type=None):
        self.violation_type = violation_type
        super().__init__(detail, code)


class BusinessRuleException(APIException):
    """Custom business rule violation exception"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Business rule violation."
    default_code = 'business_rule_violation'
    
    def __init__(self, detail=None, code=None, rule_name=None):
        self.rule_name = rule_name
        super().__init__(detail, code)


class RateLimitException(APIException):
    """Custom rate limit exceeded exception"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Rate limit exceeded."
    default_code = 'rate_limit_exceeded'
    
    def __init__(self, detail=None, code=None, retry_after=None):
        self.retry_after = retry_after
        super().__init__(detail, code)


class EnhancedErrorHandler:
    """Enhanced error handler with comprehensive logging and monitoring"""
    
    @staticmethod
    def handle_validation_error(error, request=None, context=None):
        """Handle validation errors with detailed logging"""
        error_data = {
            'type': 'validation_error',
            'timestamp': timezone.now().isoformat(),
            'error_message': str(error),
            'error_code': getattr(error, 'code', 'validation_error'),
        }
        
        # Add field-specific information if available
        if hasattr(error, 'field'):
            error_data['field'] = error.field
        
        if hasattr(error, 'errors'):
            error_data['errors'] = error.errors
        
        # Add request context
        if request:
            error_data.update(EnhancedErrorHandler._get_request_context(request))
        
        # Add context information
        if context:
            error_data['context'] = context
        
        # Log the error
        error_handler_logger.warning(
            f"Validation error: {error_data['error_message']}",
            extra=error_data
        )
        
        # Create user-friendly error response
        user_message = EnhancedErrorHandler._get_user_friendly_message(error, 'validation')
        
        return {
            'error': {
                'code': error_data['error_code'],
                'message': user_message,
                'field': error_data.get('field'),
                'details': error_data.get('errors', []),
                'timestamp': error_data['timestamp']
            }
        }
    
    @staticmethod
    def handle_security_error(error, request=None, context=None):
        """Handle security-related errors"""
        error_data = {
            'type': 'security_error',
            'timestamp': timezone.now().isoformat(),
            'error_message': str(error),
            'error_code': getattr(error, 'code', 'security_violation'),
            'violation_type': getattr(error, 'violation_type', 'unknown')
        }
        
        # Add request context
        if request:
            error_data.update(EnhancedErrorHandler._get_request_context(request))
        
        # Add context information
        if context:
            error_data['context'] = context
        
        # Log security violation
        error_handler_logger.error(
            f"Security violation: {error_data['violation_type']} - {error_data['error_message']}",
            extra=error_data
        )
        
        # Send security alert email to admins in production
        if not settings.DEBUG:
            EnhancedErrorHandler._send_security_alert(error_data)
        
        # Create user-friendly error response
        user_message = EnhancedErrorHandler._get_user_friendly_message(error, 'security')
        
        return {
            'error': {
                'code': error_data['error_code'],
                'message': user_message,
                'timestamp': error_data['timestamp']
            }
        }
    
    @staticmethod
    def handle_business_rule_error(error, request=None, context=None):
        """Handle business rule violations"""
        error_data = {
            'type': 'business_rule_error',
            'timestamp': timezone.now().isoformat(),
            'error_message': str(error),
            'error_code': getattr(error, 'code', 'business_rule_violation'),
            'rule_name': getattr(error, 'rule_name', 'unknown')
        }
        
        # Add request context
        if request:
            error_data.update(EnhancedErrorHandler._get_request_context(request))
        
        # Add context information
        if context:
            error_data['context'] = context
        
        # Log business rule violation
        error_handler_logger.warning(
            f"Business rule violation: {error_data['rule_name']} - {error_data['error_message']}",
            extra=error_data
        )
        
        # Create user-friendly error response
        user_message = EnhancedErrorHandler._get_user_friendly_message(error, 'business_rule')
        
        return {
            'error': {
                'code': error_data['error_code'],
                'message': user_message,
                'rule': error_data['rule_name'],
                'timestamp': error_data['timestamp']
            }
        }
    
    @staticmethod
    def handle_unexpected_error(error, request=None, context=None):
        """Handle unexpected errors"""
        error_data = {
            'type': 'unexpected_error',
            'timestamp': timezone.now().isoformat(),
            'error_message': str(error),
            'error_type': type(error).__name__,
            'traceback': traceback.format_exc()
        }
        
        # Add request context
        if request:
            error_data.update(EnhancedErrorHandler._get_request_context(request))
        
        # Add context information
        if context:
            error_data['context'] = context
        
        # Log unexpected error
        error_handler_logger.error(
            f"Unexpected error: {error_data['error_type']} - {error_data['error_message']}",
            extra=error_data
        )
        
        # Send error alert to admins in production
        if not settings.DEBUG:
            EnhancedErrorHandler._send_error_alert(error_data)
        
        # Create user-friendly error response
        user_message = EnhancedErrorHandler._get_user_friendly_message(error, 'unexpected')
        
        response_data = {
            'error': {
                'code': 'internal_error',
                'message': user_message,
                'timestamp': error_data['timestamp']
            }
        }
        
        # Include error details in debug mode
        if settings.DEBUG:
            response_data['error']['debug'] = {
                'error_type': error_data['error_type'],
                'traceback': error_data['traceback']
            }
        
        return response_data
    
    @staticmethod
    def _get_request_context(request):
        """Extract relevant context from request"""
        if not request:
            return {}
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR')
        
        # Get user information
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        username = getattr(request.user, 'username', None) if hasattr(request, 'user') else None
        
        return {
            'method': request.method,
            'path': request.path,
            'client_ip': client_ip,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'user_id': user_id,
            'username': username,
            'content_type': request.META.get('CONTENT_TYPE', ''),
            'content_length': request.META.get('CONTENT_LENGTH', 0)
        }
    
    @staticmethod
    def _get_user_friendly_message(error, error_type):
        """Get user-friendly error messages"""
        messages = {
            'validation': {
                'default': 'The provided data is invalid. Please check your input and try again.',
                'required_field': 'This field is required.',
                'invalid_format': 'The format of this field is invalid.',
                'value_too_short': 'This value is too short.',
                'value_too_long': 'This value is too long.',
                'invalid_choice': 'Please select a valid option.',
                'unique_constraint': 'This value already exists. Please choose a different one.'
            },
            'security': {
                'default': 'Access denied due to security policy.',
                'authentication_required': 'You need to log in to access this resource.',
                'permission_denied': 'You do not have permission to perform this action.',
                'rate_limit_exceeded': 'Too many requests. Please wait before trying again.',
                'invalid_token': 'Your session has expired. Please log in again.',
                'suspicious_activity': 'Unusual activity detected. Please contact support if you believe this is an error.'
            },
            'business_rule': {
                'default': 'This action cannot be completed due to business rules.',
                'booking_conflict': 'This time slot is no longer available.',
                'insufficient_permissions': 'You do not have the required permissions for this action.',
                'resource_unavailable': 'The requested resource is currently unavailable.',
                'operation_not_allowed': 'This operation is not allowed at this time.'
            },
            'unexpected': {
                'default': 'An unexpected error occurred. Please try again later.',
                'database_error': 'Database temporarily unavailable. Please try again later.',
                'external_service_error': 'External service temporarily unavailable. Please try again later.',
                'file_processing_error': 'File processing failed. Please check your file and try again.',
                'email_error': 'Email service temporarily unavailable. Please try again later.'
            }
        }
        
        error_messages = messages.get(error_type, messages['unexpected'])
        
        # Try to extract specific error information
        error_str = str(error).lower()
        
        if 'required' in error_str or 'blank' in error_str:
            return error_messages.get('required_field', error_messages['default'])
        elif 'format' in error_str or 'invalid' in error_str:
            return error_messages.get('invalid_format', error_messages['default'])
        elif 'too short' in error_str:
            return error_messages.get('value_too_short', error_messages['default'])
        elif 'too long' in error_str:
            return error_messages.get('value_too_long', error_messages['default'])
        elif 'choice' in error_str or 'option' in error_str:
            return error_messages.get('invalid_choice', error_messages['default'])
        elif 'unique' in error_str or 'already exists' in error_str:
            return error_messages.get('unique_constraint', error_messages['default'])
        elif 'authentication' in error_str or 'login' in error_str:
            return error_messages.get('authentication_required', error_messages['default'])
        elif 'permission' in error_str or 'access' in error_str:
            return error_messages.get('permission_denied', error_messages['default'])
        elif 'rate limit' in error_str or 'too many' in error_str:
            return error_messages.get('rate_limit_exceeded', error_messages['default'])
        elif 'token' in error_str or 'session' in error_str:
            return error_messages.get('invalid_token', error_messages['default'])
        elif 'booking' in error_str or 'time slot' in error_str:
            return error_messages.get('booking_conflict', error_messages['default'])
        elif 'database' in error_str:
            return error_messages.get('database_error', error_messages['default'])
        elif 'external' in error_str or 'service' in error_str:
            return error_messages.get('external_service_error', error_messages['default'])
        elif 'file' in error_str or 'processing' in error_str:
            return error_messages.get('file_processing_error', error_messages['default'])
        elif 'email' in error_str or 'mail' in error_str:
            return error_messages.get('email_error', error_messages['default'])
        else:
            return error_messages['default']
    
    @staticmethod
    def _send_security_alert(error_data):
        """Send security alert email to administrators"""
        try:
            subject = f"Security Alert: {error_data['violation_type']}"
            
            message = f"""
Security Alert from KickZone Application

Violation Type: {error_data['violation_type']}
Timestamp: {error_data['timestamp']}
Client IP: {error_data.get('client_ip', 'Unknown')}
User: {error_data.get('username', 'Anonymous')} (ID: {error_data.get('user_id', 'Unknown')})
Path: {error_data.get('path', 'Unknown')}
Method: {error_data.get('method', 'Unknown')}

Error Message: {error_data['error_message']}

Please review this security incident immediately.
            """
            
            # Get admin email addresses
            admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=True
                )
        except Exception as e:
            error_handler_logger.error(f"Failed to send security alert: {str(e)}")
    
    @staticmethod
    def _send_error_alert(error_data):
        """Send error alert email to administrators"""
        try:
            subject = f"Error Alert: {error_data['error_type']}"
            
            message = f"""
Error Alert from KickZone Application

Error Type: {error_data['error_type']}
Timestamp: {error_data['timestamp']}
Client IP: {error_data.get('client_ip', 'Unknown')}
User: {error_data.get('username', 'Anonymous')} (ID: {error_data.get('user_id', 'Unknown')})
Path: {error_data.get('path', 'Unknown')}
Method: {error_data.get('method', 'Unknown')}

Error Message: {error_data['error_message']}

Traceback:
{error_data.get('traceback', 'No traceback available')}

Please investigate this error.
            """
            
            # Get admin email addresses
            admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=True
                )
        except Exception as e:
            error_handler_logger.error(f"Failed to send error alert: {str(e)}")


def handle_api_exception(exc, context):
    """
    Custom exception handler for DRF API exceptions.
    Returns JSON response with detailed error information.
    """
    error_handler = EnhancedErrorHandler()
    request = context.get('request')
    
    # Handle different types of exceptions
    if isinstance(exc, ValidationError):
        return Response(
            error_handler.handle_validation_error(exc, request),
            status=status.HTTP_400_BAD_REQUEST
        )
    elif isinstance(exc, (PermissionDenied, AuthenticationFailed)):
        return Response(
            error_handler.handle_security_error(exc, request),
            status=status.HTTP_403_FORBIDDEN
        )
    elif isinstance(exc, NotFound):
        return Response(
            error_handler.handle_validation_error(exc, request),
            status=status.HTTP_404_NOT_FOUND
        )
    elif isinstance(exc, (ValidationException, SecurityException, BusinessRuleException, RateLimitException)):
        error_class = exc.__class__.__name__
        if 'Validation' in error_class:
            return Response(
                error_handler.handle_validation_error(exc, request),
                status=exc.status_code
            )
        elif 'Security' in error_class:
            return Response(
                error_handler.handle_security_error(exc, request),
                status=exc.status_code
            )
        elif 'BusinessRule' in error_class:
            return Response(
                error_handler.handle_business_rule_error(exc, request),
                status=exc.status_code
            )
        elif 'RateLimit' in error_class:
            response_data = error_handler.handle_validation_error(exc, request)
            if hasattr(exc, 'retry_after'):
                response_data['error']['retry_after'] = exc.retry_after
            return Response(
                response_data,
                status=exc.status_code
            )
    else:
        # Handle unexpected exceptions
        return Response(
            error_handler.handle_unexpected_error(exc, request),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def handle_django_validation_error(exc, request=None):
    """Handle Django validation errors"""
    error_handler = EnhancedErrorHandler()
    
    # Convert Django validation errors to our format
    errors = []
    if hasattr(exc, 'message_dict'):
        for field, messages in exc.message_dict.items():
            for message in messages:
                errors.append({
                    'field': field,
                    'message': str(message),
                    'code': getattr(exc, 'error_dict', {}).get(field, [{}])[0].get('code', 'invalid')
                })
    
    validation_error = ValidationException(
        detail='Validation failed',
        errors=errors
    )
    
    return error_handler.handle_validation_error(validation_error, request)