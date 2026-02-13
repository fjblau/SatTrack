"""
Pagination utilities for graph query results.
"""
from typing import Dict, Any, List, Optional
from fastapi import Query


class PaginationParams:
    """
    Standard pagination parameters for API endpoints.
    """
    
    def __init__(
        self,
        offset: int = Query(
            default=0,
            description="Number of results to skip",
            ge=0
        ),
        limit: int = Query(
            default=50,
            description="Maximum number of results to return",
            ge=1,
            le=1000
        )
    ):
        self.offset = offset
        self.limit = limit
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for caching."""
        return {
            "offset": self.offset,
            "limit": self.limit
        }


def create_pagination_response(
    data: List[Any],
    total_count: int,
    offset: int,
    limit: int,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized paginated response.
    
    Args:
        data: List of result items for current page
        total_count: Total number of items available
        offset: Current offset
        limit: Current limit
        additional_data: Optional additional data to include in response
    
    Returns:
        Paginated response dictionary with metadata
    """
    response = {
        "items": data,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "total": total_count,
            "returned": len(data),
            "has_more": (offset + len(data)) < total_count,
            "next_offset": offset + len(data) if (offset + len(data)) < total_count else None
        }
    }
    
    if additional_data:
        response.update(additional_data)
    
    return response


def paginate_in_memory(
    items: List[Any],
    offset: int = 0,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Paginate a list of items that's already in memory.
    
    Args:
        items: List of items to paginate
        offset: Number of items to skip
        limit: Maximum number of items to return
    
    Returns:
        Paginated response
    """
    total_count = len(items)
    paginated_items = items[offset:offset + limit]
    
    return create_pagination_response(
        data=paginated_items,
        total_count=total_count,
        offset=offset,
        limit=limit
    )


def get_aql_pagination_clause(offset: int, limit: int) -> str:
    """
    Generate AQL LIMIT clause for pagination.
    
    Args:
        offset: Number of results to skip
        limit: Maximum number of results to return
    
    Returns:
        AQL LIMIT clause string
    """
    return f"LIMIT {offset}, {limit}"
