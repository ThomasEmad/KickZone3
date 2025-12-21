"""
Centralized error handling and security monitoring middleware.
This module provides comprehensive request/response logging, error handling, and security monitoring.
"""

import json
import time
import logging
import traceback
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import MiddlewareNotUsed
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.conf import settings
from django.db import OperationalError, IntegrityError
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt

# Configure middleware logger
middleware_logger = logging.getLogger('kickzone.middleware.security')
request_logger = logging.getLogger('kickzone.middleware.requests')
error_logger = logging.getLogger('kickzone.middleware.errors')


class SecurityMiddleware:
    """Middleware for security monitoring and threat detection"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.api_rate_limits = getattr(settings, 'API_RATE_LIMITS', {})
        
    def __call__(self, request):
        # Security checks before processing request
        if not self._security_checks_pass(request):
            return HttpResponseForbidden(
                json.dumps({'error': 'Access denied due to security policy.'}),
                content_type='application/json'
            )
        
        response = self.get_response(request)
        return response
    
    def _security_checks_pass(self, request):
        """Perform security checks on the request"""
        # Check User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if self._is_suspicious_user_agent(user_agent):
            middleware_logger.warning(
                f"Suspicious User-Agent detected: {user_agent[:100]}",
                extra={'suspicious_ua': True, 'ip': self._get_client_ip(request)}
            )
            return False
        
        # Check for SQL injection patterns
        if self._contains_sql_injection(request):
            middleware_logger.warning(
                f"SQL injection attempt detected from {self._get_client_ip(request)}",
                extra={'sql_injection_attempt': True, 'path': request.path}
            )
            return False
        
        # Check request size
        if self._is_request_too_large(request):
            middleware_logger.warning(
                f"Request too large from {self._get_client_ip(request)}",
                extra={'large_request': True, 'content_length': request.META.get('CONTENT_LENGTH')}
            )
            return False
        
        return True
    
    def _is_suspicious_user_agent(self, user_agent):
        """Check for suspicious User-Agent patterns"""
        if not user_agent:
            return True  # Empty User-Agent is suspicious
        
        suspicious_patterns = [
            r'(sqlmap|nikto|nessus|openvas|nmap|masscan|acunetix)',
            r'(bot|crawler|spider|scraper)',
            r'(java|perl|ruby|go-http-client)',
            r'(libwww-perl|lwp-trivial|fetch|twit)',
        ]
        
        # Allow common testing tools in development/testing environments
        if not settings.DEBUG:
            suspicious_patterns.extend([
                r'(curl|wget|python-requests|httpclient)',
            ])
        
        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return True
        
        return False
    
    def _contains_sql_injection(self, request):
        """Check for SQL injection patterns in request"""
        # Check query parameters
        for key, value in request.GET.items():
            if self._is_sql_injection_pattern(str(value)):
                return True
        
        # Check request body for POST/PUT/PATCH
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'data'):
                    body_data = request.data
                else:
                    body_data = getattr(request, 'POST', {})
                
                if isinstance(body_data, dict):
                    for key, value in body_data.items():
                        if self._is_sql_injection_pattern(str(value)):
                            return True
            except:
                pass  # If we can't parse the body, skip this check
        
        return False
    
    def _is_sql_injection_pattern(self, text):
        """Check if text contains SQL injection patterns"""
        if not text:
            return False
        
        sql_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
            r'(\b(OR|AND)\s+[\'"]?[\d]+[\'"]?\s*=\s*[\'"]?[\d]+[\'"]?\b)',
            r'(\'\s*OR\s*\'\s*=\s*\'\s*)',
            r'(\-\-)',
            r'(\b(CHAR|ASCII|HEX|LOAD_FILE|INTO\s+OUTFILE)\s*\()',
            r'(\b(INFORMATION_SCHEMA|SYSCAT|SYSOBJECTS|SYS\.)\b)',
            r'(\b(XP_CMDSHELL|SP_EXECUTESQL|DECLARE|CAST\()\b)',
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_request_too_large(self, request):
        """Check if request size exceeds limits"""
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                size = int(content_length)
                max_size = getattr(settings, 'MAX_REQUEST_SIZE', 10 * 1024 * 1024)  # 10MB default
                return size > max_size
            except ValueError:
                pass
        return False
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RequestLoggingMiddleware:
    """Middleware for comprehensive request logging"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        start_time = time.time()
        
        # Generate unique request ID
        request_id = f"{int(start_time * 1000000)}-{id(request)}"
        request.request_id = request_id
        
        # Log request
        self._log_request(request, start_time, request_id)
        
        # Process request
        response = self.get_response(request)
        
        # Log response
        process_time = time.time() - start_time
        self._log_response(request, response, process_time, request_id)
        
        # Add headers
        response['X-Request-ID'] = request_id
        response['X-Process-Time'] = f"{process_time:.3f}s"
        
        return response
    
    def _log_request(self, request, start_time, request_id):
        """Log incoming request"""
        client_ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Sanitize sensitive data from query params
        safe_query_params = {}
        for key, value in request.GET.items():
            if key.lower() in ['password', 'token', 'key', 'secret']:
                safe_query_params[key] = '[REDACTED]'
            else:
                safe_query_params[key] = str(value)[:100]  # Truncate long values
        
        request_logger.info(
            f"REQUEST {request_id}: {request.method} {request.path}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'query_params': safe_query_params,
                'client_ip': client_ip,
                'user_agent': user_agent[:200],  # Truncate long User-Agent
                'user_id': user_id,
                'content_type': request.META.get('CONTENT_TYPE', ''),
                'content_length': request.META.get('CONTENT_LENGTH', 0),
                'timestamp': datetime.fromtimestamp(start_time).isoformat(),
                'event_type': 'request_start'
            }
        )
    
    def _log_response(self, request, response, process_time, request_id):
        """Log response"""
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = 'error'
        elif response.status_code >= 400:
            log_level = 'warning'
        else:
            log_level = 'info'
        
        # Log the response
        getattr(request_logger, log_level)(
            f"RESPONSE {request_id}: {response.status_code} ({process_time:.3f}s)",
            extra={
                'request_id': request_id,
                'status_code': response.status_code,
                'process_time': process_time,
                'client_ip': client_ip,
                'user_id': user_id,
                'response_headers': dict(response.items()),
                'event_type': 'response_complete'
            }
        )
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ErrorHandlingMiddleware:
    """Middleware for centralized error handling and reporting"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            return self._handle_exception(request, e)
    
    def _handle_exception(self, request, exception):
        """Handle exceptions and provide appropriate responses"""
        # Log the exception
        self._log_exception(request, exception)
        
        # Determine response based on exception type
        if hasattr(exception, 'status_code'):
            status_code = exception.status_code
        elif isinstance(exception, (OperationalError, IntegrityError)):
            status_code = 503  # Service unavailable for database errors
        elif isinstance(exception, PermissionError):
            status_code = 403
        elif isinstance(exception, FileNotFoundError):
            status_code = 404
        else:
            status_code = 500
        
        # Create appropriate error response
        if status_code == 500:
            error_message = "An internal server error occurred. Please try again later."
            error_code = "INTERNAL_ERROR"
        elif status_code == 403:
            error_message = "You don't have permission to access this resource."
            error_code = "PERMISSION_DENIED"
        elif status_code == 404:
            error_message = "The requested resource was not found."
            error_code = "NOT_FOUND"
        elif status_code == 503:
            error_message = "Service temporarily unavailable. Please try again later."
            error_code = "SERVICE_UNAVAILABLE"
        else:
            error_message = str(exception)
            error_code = "UNKNOWN_ERROR"
        
        # Create JSON response
        error_response = {
            'error': {
                'code': error_code,
                'message': error_message,
                'timestamp': timezone.now().isoformat(),
                'request_id': getattr(request, 'request_id', 'unknown')
            }
        }
        
        # Don't expose sensitive error details in production
        if settings.DEBUG:
            error_response['error']['details'] = {
                'exception_type': type(exception).__name__,
                'traceback': traceback.format_exc()
            }
        
        return JsonResponse(error_response, status=status_code)
    
    def _log_exception(self, request, exception):
        """Log exception with context"""
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        request_id = getattr(request, 'request_id', 'unknown')
        
        error_logger.error(
            f"EXCEPTION {request_id}: {type(exception).__name__}: {str(exception)}",
            exc_info=True,
            extra={
                'request_id': request_id,
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'traceback': traceback.format_exc(),
                'method': request.method,
                'path': request.path,
                'client_ip': client_ip,
                'user_id': user_id,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'query_params': dict(request.GET.items()),
                'event_type': 'exception_occurred'
            }
        )
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RateLimitMiddleware:
    """Middleware for rate limiting based on IP and user"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.default_limits = getattr(settings, 'DEFAULT_RATE_LIMITS', {
            'requests_per_hour': 1000,
            'requests_per_minute': 100,
            'requests_per_second': 10
        })
    
    def __call__(self, request):
        # Skip rate limiting for certain paths
        if self._should_skip_rate_limit(request):
            return self.get_response(request)
        
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Check rate limits
        if not self._check_rate_limits(request, client_ip, user_id):
            error_response = {
                'error': {
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'message': 'Rate limit exceeded. Please try again later.',
                    'retry_after': 3600  # 1 hour in seconds
                }
            }
            return JsonResponse(error_response, status=429)
        
        response = self.get_response(request)
        return response
    
    def _should_skip_rate_limit(self, request):
        """Check if rate limiting should be skipped for this request"""
        skip_paths = getattr(settings, 'SKIP_RATE_LIMIT_PATHS', [
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
            '/status/'
        ])
        
        return any(request.path.startswith(path) for path in skip_paths)
    
    def _check_rate_limits(self, request, client_ip, user_id):
        """Check various rate limits"""
        # Get limits (user-specific or default)
        limits = self._get_rate_limits(user_id)
        
        # Check per-second limit
        if not self._check_single_limit(request, client_ip, user_id, 'second', limits['requests_per_second']):
            return False
        
        # Check per-minute limit
        if not self._check_single_limit(request, client_ip, user_id, 'minute', limits['requests_per_minute']):
            return False
        
        # Check per-hour limit
        if not self._check_single_limit(request, client_ip, user_id, 'hour', limits['requests_per_hour']):
            return False
        
        return True
    
    def _check_single_limit(self, request, client_ip, user_id, period, limit):
        """Check a single rate limit"""
        if limit <= 0:  # No limit
            return True
        
        # Create cache key
        if user_id:
            key = f"rate_limit_{period}_{user_id}"
        else:
            key = f"rate_limit_{period}_{client_ip}"
        
        # Get current count
        current_count = cache.get(key, 0)
        
        if current_count >= limit:
            # Log rate limit exceeded
            middleware_logger.warning(
                f"Rate limit exceeded for {period} period",
                extra={
                    'client_ip': client_ip,
                    'user_id': user_id,
                    'period': period,
                    'limit': limit,
                    'current_count': current_count,
                    'path': request.path,
                    'method': request.method
                }
            )
            return False
        
        # Increment counter
        timeout = {'second': 1, 'minute': 60, 'hour': 3600}[period]
        cache.set(key, current_count + 1, timeout)
        
        return True
    
    def _get_rate_limits(self, user_id):
        """Get rate limits for user (can be customized per user type)"""
        if user_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                
                # Different limits for different user types
                if user.user_type == 'admin':
                    return {
                        'requests_per_hour': 10000,
                        'requests_per_minute': 1000,
                        'requests_per_second': 50
                    }
                elif user.user_type == 'owner':
                    return {
                        'requests_per_hour': 5000,
                        'requests_per_minute': 500,
                        'requests_per_second': 25
                    }
            except:
                pass
        
        return self.default_limits
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Import required modules
import re