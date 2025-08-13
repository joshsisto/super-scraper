"""
Comprehensive error handling and graceful degradation for validation system.

This module provides robust error handling, recovery strategies, and graceful
degradation to ensure the validation system remains functional even when
individual components fail.
"""

import logging
import time
import asyncio
import functools
from typing import Dict, Any, Optional, Callable, Union, List, Type
from enum import Enum
from dataclasses import dataclass
import traceback


class ErrorSeverity(Enum):
    """Error severity levels for validation failures."""
    LOW = "low"           # Minor issues, validation can continue
    MEDIUM = "medium"     # Significant issues, some functionality may be limited
    HIGH = "high"         # Major issues, fallback mechanisms triggered
    CRITICAL = "critical" # System-level failures, validation may fail completely


class ErrorCategory(Enum):
    """Categories of validation errors."""
    CONFIGURATION = "configuration"     # Configuration-related errors
    NETWORK = "network"                 # Network/connectivity issues
    PARSING = "parsing"                 # Data parsing/processing errors
    VALIDATION = "validation"           # Core validation logic errors
    RESOURCE = "resource"               # Resource constraints (memory, timeout)
    SYSTEM = "system"                   # System-level errors
    INTEGRATION = "integration"         # Integration with scraper components


@dataclass
class ValidationError:
    """Container for validation error information."""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception: Optional[Exception] = None
    component: Optional[str] = None
    timestamp: float = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class ErrorRecoveryStrategy:
    """Base class for error recovery strategies."""
    
    def __init__(self, name: str, max_attempts: int = 3):
        self.name = name
        self.max_attempts = max_attempts
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    async def attempt_recovery(self, error: ValidationError, context: Dict[str, Any]) -> bool:
        """
        Attempt to recover from an error.
        
        Args:
            error: ValidationError instance
            context: Additional context for recovery
            
        Returns:
            True if recovery was successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement attempt_recovery")


class FallbackResponseDataStrategy(ErrorRecoveryStrategy):
    """Recovery strategy for response data collection failures."""
    
    def __init__(self):
        super().__init__("FallbackResponseData")
    
    async def attempt_recovery(self, error: ValidationError, context: Dict[str, Any]) -> bool:
        """Create minimal fallback response data."""
        try:
            url = context.get('url', 'unknown')
            fallback_data = {
                'url': url,
                'status_code': 200,  # Assume success for fallback
                'headers': {'content-type': 'text/html'},
                'content': '',
                'response_time': 0.0,
                'timestamp': time.time(),
                'collector_type': 'fallback',
                'fallback_reason': error.message
            }
            
            context['response_data'] = fallback_data
            self.logger.info(f"Created fallback response data for {url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Fallback response data creation failed: {e}")
            return False


class RetryWithBackoffStrategy(ErrorRecoveryStrategy):
    """Recovery strategy using exponential backoff retry."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 30.0):
        super().__init__("RetryWithBackoff")
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def attempt_recovery(self, error: ValidationError, context: Dict[str, Any]) -> bool:
        """Retry the operation with exponential backoff."""
        operation = context.get('retry_operation')
        if not operation:
            self.logger.error("No retry operation provided in context")
            return False
        
        for attempt in range(self.max_attempts):
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
            self.logger.info(f"Retry attempt {attempt + 1}/{self.max_attempts} after {delay}s delay")
            
            await asyncio.sleep(delay)
            
            try:
                result = await operation()
                if result:
                    self.logger.info(f"Retry successful on attempt {attempt + 1}")
                    return True
            except Exception as e:
                self.logger.warning(f"Retry attempt {attempt + 1} failed: {e}")
                continue
        
        self.logger.error(f"All {self.max_attempts} retry attempts failed")
        return False


class SimplifiedValidationStrategy(ErrorRecoveryStrategy):
    """Recovery strategy using simplified validation when full validation fails."""
    
    def __init__(self):
        super().__init__("SimplifiedValidation")
    
    async def attempt_recovery(self, error: ValidationError, context: Dict[str, Any]) -> bool:
        """Perform simplified validation with reduced requirements."""
        try:
            from validator import ValidationResult, BotDetectionSystem
            
            scraped_data = context.get('scraped_data', [])
            response_data = context.get('response_data', {})
            
            # Basic validation checks
            has_data = bool(scraped_data)
            status_ok = response_data.get('status_code', 0) in range(200, 300)
            
            # Create simplified result
            result = ValidationResult(
                is_successful=has_data and status_ok,
                is_blocked=not status_ok and response_data.get('status_code', 0) >= 400,
                bot_detection_system=BotDetectionSystem.NONE,
                confidence_score=0.5 if has_data else 0.0,
                issues=[] if has_data else ["No data extracted"],
                warnings=["Simplified validation used due to error"],
                metadata={
                    'simplified_validation': True,
                    'original_error': error.message,
                    'data_count': len(scraped_data) if scraped_data else 0
                }
            )
            
            context['validation_result'] = result
            self.logger.info("Simplified validation completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Simplified validation failed: {e}")
            return False


class ValidationErrorHandler:
    """
    Comprehensive error handler for validation operations.
    
    Provides error classification, recovery strategies, and graceful degradation
    to ensure validation system reliability.
    """
    
    def __init__(self, config: Optional[Any] = None):
        """
        Initialize error handler.
        
        Args:
            config: ValidationConfig instance or None for defaults
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.errors: List[ValidationError] = []
        self.error_counts: Dict[str, int] = {}
        
        # Initialize recovery strategies
        self.recovery_strategies = {
            ErrorCategory.NETWORK: [
                RetryWithBackoffStrategy(base_delay=2.0, max_delay=60.0),
                FallbackResponseDataStrategy()
            ],
            ErrorCategory.PARSING: [
                RetryWithBackoffStrategy(base_delay=0.5, max_delay=5.0),
                SimplifiedValidationStrategy()
            ],
            ErrorCategory.VALIDATION: [
                SimplifiedValidationStrategy()
            ],
            ErrorCategory.RESOURCE: [
                RetryWithBackoffStrategy(base_delay=5.0, max_delay=120.0),
                SimplifiedValidationStrategy()
            ],
            ErrorCategory.CONFIGURATION: [
                FallbackResponseDataStrategy()
            ],
            ErrorCategory.INTEGRATION: [
                RetryWithBackoffStrategy(base_delay=1.0, max_delay=10.0),
                FallbackResponseDataStrategy(),
                SimplifiedValidationStrategy()
            ],
            ErrorCategory.SYSTEM: [
                SimplifiedValidationStrategy()
            ]
        }
    
    def classify_error(self, exception: Exception, component: str = None) -> ValidationError:
        """
        Classify an error based on its type and context.
        
        Args:
            exception: The exception that occurred
            component: Component where the error occurred
            
        Returns:
            ValidationError with classified category and severity
        """
        error_message = str(exception)
        error_type = type(exception).__name__
        
        # Network-related errors
        if any(keyword in error_message.lower() for keyword in 
               ['timeout', 'connection', 'network', 'dns', 'socket']):
            category = ErrorCategory.NETWORK
            severity = ErrorSeverity.MEDIUM
        
        # Parsing/data errors
        elif any(keyword in error_message.lower() for keyword in 
                 ['parse', 'decode', 'json', 'csv', 'format', 'encoding']):
            category = ErrorCategory.PARSING
            severity = ErrorSeverity.LOW
        
        # Resource constraints
        elif any(keyword in error_message.lower() for keyword in 
                 ['memory', 'resource', 'limit', 'quota', 'capacity']):
            category = ErrorCategory.RESOURCE
            severity = ErrorSeverity.HIGH
        
        # Configuration errors
        elif any(keyword in error_message.lower() for keyword in 
                 ['config', 'setting', 'parameter', 'option', 'environment']):
            category = ErrorCategory.CONFIGURATION
            severity = ErrorSeverity.MEDIUM
        
        # Integration errors
        elif any(keyword in error_message.lower() for keyword in 
                 ['import', 'module', 'attribute', 'method', 'interface']):
            category = ErrorCategory.INTEGRATION
            severity = ErrorSeverity.HIGH
        
        # Validation-specific errors
        elif component and 'validator' in component.lower():
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.MEDIUM
        
        # System-level errors
        elif error_type in ['SystemError', 'OSError', 'PermissionError']:
            category = ErrorCategory.SYSTEM
            severity = ErrorSeverity.CRITICAL
        
        # Default classification
        else:
            category = ErrorCategory.SYSTEM
            severity = ErrorSeverity.MEDIUM
        
        return ValidationError(
            category=category,
            severity=severity,
            message=error_message,
            exception=exception,
            component=component
        )
    
    async def handle_error(
        self,
        error: Union[Exception, ValidationError],
        context: Dict[str, Any],
        component: str = None
    ) -> bool:
        """
        Handle an error with appropriate recovery strategies.
        
        Args:
            error: Exception or ValidationError instance
            context: Context for error recovery
            component: Component where error occurred
            
        Returns:
            True if error was successfully handled/recovered, False otherwise
        """
        # Convert Exception to ValidationError if needed
        if isinstance(error, Exception):
            validation_error = self.classify_error(error, component)
        else:
            validation_error = error
        
        # Record the error
        self.record_error(validation_error)
        
        # Log the error
        self.logger.error(
            f"[{validation_error.category.value.upper()}] "
            f"[{validation_error.severity.value.upper()}] "
            f"{validation_error.message}"
            + (f" in {validation_error.component}" if validation_error.component else "")
        )
        
        # Attempt recovery based on error category
        recovery_successful = await self._attempt_recovery(validation_error, context)
        
        # Update error record with recovery status
        validation_error.recovery_attempted = True
        validation_error.recovery_successful = recovery_successful
        
        if recovery_successful:
            self.logger.info(f"Successfully recovered from {validation_error.category.value} error")
        else:
            self.logger.error(f"Failed to recover from {validation_error.category.value} error")
        
        return recovery_successful
    
    async def _attempt_recovery(
        self,
        error: ValidationError,
        context: Dict[str, Any]
    ) -> bool:
        """Attempt recovery using appropriate strategies."""
        strategies = self.recovery_strategies.get(error.category, [])
        
        if not strategies:
            self.logger.warning(f"No recovery strategies available for {error.category.value}")
            return False
        
        for strategy in strategies:
            try:
                self.logger.info(f"Attempting recovery with {strategy.name}")
                success = await strategy.attempt_recovery(error, context)
                
                if success:
                    self.logger.info(f"Recovery successful with {strategy.name}")
                    return True
                else:
                    self.logger.warning(f"Recovery failed with {strategy.name}")
                    
            except Exception as e:
                self.logger.error(f"Recovery strategy {strategy.name} raised exception: {e}")
                continue
        
        return False
    
    def record_error(self, error: ValidationError) -> None:
        """Record error for statistics and analysis."""
        self.errors.append(error)
        
        # Keep only recent errors (last 1000)
        if len(self.errors) > 1000:
            self.errors = self.errors[-1000:]
        
        # Update error counts
        error_key = f"{error.category.value}_{error.severity.value}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics and analysis."""
        if not self.errors:
            return {'total_errors': 0, 'error_counts': {}, 'recent_errors': []}
        
        # Calculate statistics
        total_errors = len(self.errors)
        recent_errors = [
            {
                'category': e.category.value,
                'severity': e.severity.value,
                'message': e.message,
                'component': e.component,
                'timestamp': e.timestamp,
                'recovery_successful': e.recovery_successful
            }
            for e in self.errors[-10:]  # Last 10 errors
        ]
        
        # Recovery success rate
        recovery_attempts = sum(1 for e in self.errors if e.recovery_attempted)
        recovery_successes = sum(1 for e in self.errors if e.recovery_successful)
        recovery_rate = recovery_successes / recovery_attempts if recovery_attempts > 0 else 0
        
        # Error trends (last hour)
        current_time = time.time()
        recent_errors_count = sum(
            1 for e in self.errors
            if current_time - e.timestamp < 3600  # Last hour
        )
        
        return {
            'total_errors': total_errors,
            'error_counts': self.error_counts.copy(),
            'recent_errors': recent_errors,
            'recovery_attempts': recovery_attempts,
            'recovery_successes': recovery_successes,
            'recovery_rate': recovery_rate,
            'recent_errors_count': recent_errors_count
        }
    
    def clear_error_history(self) -> None:
        """Clear error history and statistics."""
        self.errors.clear()
        self.error_counts.clear()
        self.logger.info("Error history cleared")


def with_error_handling(
    error_handler: ValidationErrorHandler,
    component: str = None,
    return_on_error: Any = None
):
    """
    Decorator for adding error handling to functions.
    
    Args:
        error_handler: ValidationErrorHandler instance
        component: Component name for error classification
        return_on_error: Value to return if error handling fails
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': args,
                    'kwargs': kwargs
                }
                
                handled = await error_handler.handle_error(e, context, component)
                
                if not handled:
                    if return_on_error is not None:
                        return return_on_error
                    raise
                
                # Try to extract result from context if recovery was successful
                return context.get('validation_result', return_on_error)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # For sync functions, we can't use async error handling
                # Just log and re-raise or return default
                error_handler.logger.error(f"Error in {func.__name__}: {e}")
                error_handler.record_error(
                    error_handler.classify_error(e, component)
                )
                
                if return_on_error is not None:
                    return return_on_error
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Example usage and testing
if __name__ == "__main__":
    async def example_usage():
        """Example of how to use the error handling system."""
        from validation_config import ValidationConfig
        
        config = ValidationConfig()
        error_handler = ValidationErrorHandler(config)
        
        # Example: Simulate network error
        try:
            raise ConnectionError("Network timeout occurred")
        except Exception as e:
            context = {'url': 'https://example.com'}
            handled = await error_handler.handle_error(e, context, 'network_test')
            print(f"Network error handled: {handled}")
        
        # Example: Simulate parsing error
        try:
            raise ValueError("Invalid JSON format in response")
        except Exception as e:
            context = {'data': 'invalid_json'}
            handled = await error_handler.handle_error(e, context, 'parser')
            print(f"Parsing error handled: {handled}")
        
        # Show error statistics
        stats = error_handler.get_error_statistics()
        print("\nError Statistics:")
        for key, value in stats.items():
            if key != 'recent_errors':  # Skip detailed list for cleaner output
                print(f"  {key}: {value}")
        
        # Example of decorator usage
        @with_error_handling(error_handler, 'test_component', return_on_error={'status': 'error'})
        async def test_function():
            raise RuntimeError("Test error")
        
        result = await test_function()
        print(f"\nDecorator result: {result}")
    
    asyncio.run(example_usage())