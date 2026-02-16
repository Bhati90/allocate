# allocation_app/pagination.py

from rest_framework.pagination import PageNumberPagination

class StandardResultsPagination(PageNumberPagination):
    """Standard pagination for most endpoints"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class CompletedAllocationsPagination(PageNumberPagination):
    """Pagination for completed allocations"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

class PendingJobsPagination(PageNumberPagination):
    """Pagination for pending jobs"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50