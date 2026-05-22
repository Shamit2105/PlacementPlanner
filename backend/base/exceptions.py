import logging
import traceback
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework import status

# Initialize the base logger
logger = logging.getLogger('base')

class PRValidationError(APIException):
    """Custom Validation Error for business logic."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid input provided.'
    default_code = 'invalid_input'

def custom_exception_handler(exc, context):
    """
    Intercepts ALL exceptions in the application.
    Standardizes the JSON response format and logs the exact error details.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # Extract request information for the log
    request = context.get('request')
    view = context.get('view')
    user = request.user.email if request and request.user.is_authenticated else 'Anonymous'
    path = request.path if request else 'Unknown path'
    method = request.method if request else 'Unknown method'

    if response is not None:
        # This is a known DRF error (e.g., Validation, Authentication)
        custom_response_data = {
            'success': False,
            'error_type': exc.__class__.__name__,
            'message': 'A validation or client error occurred.',
            'details': response.data  # The exact fields that failed
        }
        response.data = custom_response_data
        
        # Log it as a warning since the client just messed up the input
        logger.warning(
            f"Client Error [{response.status_code}] | User: {user} | "
            f"Endpoint: {method} {path} | Details: {response.data}"
        )

    else:
        # This is an UNHANDLED Python exception (Server Crash)
        # We must log the complete traceback to fix the bug later.
        error_traceback = traceback.format_exc()
        
        logger.critical(
            f"CRITICAL SYSTEM FAILURE | User: {user} | Endpoint: {method} {path}\n"
            f"Exception: {str(exc)}\n"
            f"Traceback:\n{error_traceback}"
        )

        # Send a clean, standardized error back to the frontend
        custom_response_data = {
            'success': False,
            'error_type': 'InternalServerError',
            'message': 'A critical server error occurred. Our engineering team has been notified.',
            'details': str(exc) # You can remove this line in strict production to hide system details completely
        }
        
        response = Response(custom_response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response