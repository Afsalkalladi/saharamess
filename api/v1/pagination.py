from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination, CursorPagination
from rest_framework.response import Response
from collections import OrderedDict
from django.utils import timezone


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for most API endpoints."""
    
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Custom paginated response format."""
        return Response(OrderedDict([
            ('success', True),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('current_page', self.page.number),
            ('total_pages', self.page.paginator.num_pages),
            ('results', data),
            ('pagination_info', {
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
                'start_index': self.page.start_index(),
                'end_index': self.page.end_index(),
            }),
            ('timestamp', timezone.now().isoformat())
        ]))


class LargeResultsSetPagination(PageNumberPagination):
    """Pagination for large datasets like scan events."""
    
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    
    def get_paginated_response(self, data):
        """Custom paginated response for large datasets."""
        return Response(OrderedDict([
            ('success', True),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('current_page', self.page.number),
            ('total_pages', self.page.paginator.num_pages),
            ('results', data),
            ('performance_info', {
                'page_load_time': getattr(self, 'load_time', None),
                'query_count': getattr(self, 'query_count', None),
            }),
            ('timestamp', timezone.now().isoformat())
        ]))


class SmallResultsSetPagination(PageNumberPagination):
    """Pagination for small datasets like admin lists."""
    
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    
    def get_paginated_response(self, data):
        """Custom paginated response for small datasets."""
        return Response(OrderedDict([
            ('success', True),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('current_page', self.page.number),
            ('total_pages', self.page.paginator.num_pages),
            ('results', data),
            ('timestamp', timezone.now().isoformat())
        ]))


class CustomLimitOffsetPagination(LimitOffsetPagination):
    """Limit/offset pagination for flexible data access."""
    
    default_limit = 25
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 200
    
    def get_paginated_response(self, data):
        """Custom limit/offset response format."""
        next_url = self.get_next_link()
        previous_url = self.get_previous_link()
        
        return Response(OrderedDict([
            ('success', True),
            ('count', self.count),
            ('next', next_url),
            ('previous', previous_url),
            ('limit', self.limit),
            ('offset', self.offset),
            ('results', data),
            ('pagination_info', {
                'has_next': next_url is not None,
                'has_previous': previous_url is not None,
                'remaining': max(0, self.count - (self.offset + self.limit)),
            }),
            ('timestamp', timezone.now().isoformat())
        ]))


class TimeBasedCursorPagination(CursorPagination):
    """Cursor pagination based on creation time for real-time data."""
    
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_at'
    cursor_query_param = 'cursor'
    cursor_query_description = 'The pagination cursor value.'
    
    def get_paginated_response(self, data):
        """Custom cursor-based response format."""
        return Response(OrderedDict([
            ('success', True),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('results', data),
            ('cursor_info', {
                'has_next': self.has_next,
                'has_previous': self.has_previous,
                'ordering': self.ordering,
            }),
            ('timestamp', timezone.now().isoformat())
        ]))


class ScanEventPagination(CursorPagination):
    """Special pagination for scan events with high frequency."""
    
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    ordering = '-scanned_at'
    cursor_query_param = 'cursor'
    
    def get_paginated_response(self, data):
        """Custom response for scan events."""
        return Response(OrderedDict([
            ('success', True),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('results', data),
            ('scan_info', {
                'total_events': getattr(self, 'total_count', None),
                'time_range': getattr(self, 'time_range', None),
                'has_more': self.has_next,
            }),
            ('timestamp', timezone.now().isoformat())
        ]))


class AuditLogPagination(CursorPagination):
    """Pagination for audit logs with chronological ordering."""
    
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_at'
    cursor_query_param = 'cursor'
    
    def get_paginated_response(self, data):
        """Custom response for audit logs."""
        return Response(OrderedDict([
            ('success', True),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('results', data),
            ('audit_info', {
                'chronological_order': True,
                'has_more_recent': self.has_previous,
                'has_more_historical': self.has_next,
                'retention_period': '90 days',
            }),
            ('timestamp', timezone.now().isoformat())
        ]))


class ReportPagination(PageNumberPagination):
    """Pagination for reports and analytics."""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Custom response for reports."""
        return Response(OrderedDict([
            ('success', True),
            ('report_metadata', {
                'total_records': self.page.paginator.count,
                'current_page': self.page.number,
                'total_pages', self.page.paginator.num_pages),
                'page_size': self.page_size,
                'generated_at': timezone.now().isoformat(),
            }),
            ('navigation', {
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            }),
            ('data', data),
            ('export_options', {
                'csv_url': getattr(self, 'csv_export_url', None),
                'excel_url': getattr(self, 'excel_export_url', None),
            })
        ]))


class InfinitePagination(CursorPagination):
    """Infinite scroll pagination for mobile apps."""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50
    ordering = '-created_at'
    cursor_query_param = 'cursor'
    
    def get_paginated_response(self, data):
        """Optimized response for infinite scroll."""
        return Response(OrderedDict([
            ('success', True),
            ('results', data),
            ('has_more', self.has_next),
            ('next_cursor', self.get_next_link()),
            ('count', len(data)),
            ('timestamp', timezone.now().isoformat())
        ]))


class SearchResultsPagination(PageNumberPagination):
    """Pagination for search results with relevance scoring."""
    
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50
    
    def get_paginated_response(self, data):
        """Custom response for search results."""
        return Response(OrderedDict([
            ('success', True),
            ('search_info', {
                'total_results': self.page.paginator.count,
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'results_per_page': self.page_size,
                'search_time_ms': getattr(self, 'search_time', None),
            }),
            ('navigation', {
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            }),
            ('results', data),
            ('suggestions', getattr(self, 'search_suggestions', [])),
            ('timestamp', timezone.now().isoformat())
        ]))


class DashboardPagination(PageNumberPagination):
    """Pagination for dashboard widgets and summaries."""
    
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 25
    
    def get_paginated_response(self, data):
        """Minimal response for dashboard widgets."""
        return Response(OrderedDict([
            ('success', True),
            ('data', data),
            ('meta', {
                'count': self.page.paginator.count,
                'page': self.page.number,
                'pages': self.page.paginator.num_pages,
                'has_more': self.page.has_next(),
            }),
            ('navigation', {
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            })
        ]))


# Custom pagination with caching
class CachedPagination(StandardResultsSetPagination):
    """Pagination with Redis caching for expensive queries."""
    
    cache_timeout = 300  # 5 minutes
    
    def paginate_queryset(self, queryset, request, view=None):
        """Override to add caching layer."""
        from django.core.cache import cache
        
        # Create cache key based on query parameters
        cache_key = self._get_cache_key(request, view)
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # If not in cache, paginate normally
        result = super().paginate_queryset(queryset, request, view)
        
        # Cache the result
        if result:
            cache.set(cache_key, result, self.cache_timeout)
        
        return result
    
    def _get_cache_key(self, request, view):
        """Generate cache key from request parameters."""
        import hashlib
        
        # Include relevant parameters in cache key
        key_parts = [
            view.__class__.__name__ if view else 'unknown',
            request.GET.urlencode(),
            str(self.page_size),
        ]
        
        key_string = '|'.join(key_parts)
        return f"pagination:{hashlib.md5(key_string.encode()).hexdigest()}"


# Performance monitoring pagination
class MonitoredPagination(StandardResultsSetPagination):
    """Pagination with performance monitoring."""
    
    def paginate_queryset(self, queryset, request, view=None):
        """Override to add performance monitoring."""
        import time
        from django.db import connection
        
        # Record start time and query count
        start_time = time.time()
        start_queries = len(connection.queries)
        
        # Perform pagination
        result = super().paginate_queryset(queryset, request, view)
        
        # Calculate performance metrics
        end_time = time.time()
        end_queries = len(connection.queries)
        
        self.load_time = round((end_time - start_time) * 1000, 2)  # milliseconds
        self.query_count = end_queries - start_queries
        
        # Log slow queries
        if self.load_time > 1000:  # More than 1 second
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Slow pagination query: {self.load_time}ms, {self.query_count} queries",
                extra={
                    'view': view.__class__.__name__ if view else 'unknown',
                    'load_time': self.load_time,
                    'query_count': self.query_count,
                    'page_size': self.page_size,
                }
            )
        
        return result


# Pagination for different use cases
PAGINATION_CLASSES = {
    'standard': StandardResultsSetPagination,
    'large': LargeResultsSetPagination,
    'small': SmallResultsSetPagination,
    'cursor': TimeBasedCursorPagination,
    'limit_offset': CustomLimitOffsetPagination,
    'scan_events': ScanEventPagination,
    'audit_logs': AuditLogPagination,
    'reports': ReportPagination,
    'infinite': InfinitePagination,
    'search': SearchResultsPagination,
    'dashboard': DashboardPagination,
    'cached': CachedPagination,
    'monitored': MonitoredPagination,
}


def get_pagination_class(pagination_type='standard'):
    """Get pagination class by type."""
    return PAGINATION_CLASSES.get(pagination_type, StandardResultsSetPagination)