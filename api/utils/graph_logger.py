"""
Enhanced logging utilities for graph operations.
"""
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional
from datetime import datetime

logger = logging.getLogger("graph_analytics")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_query_performance(operation_name: str):
    """
    Decorator to log performance metrics for graph operations.
    
    Args:
        operation_name: Name of the operation being performed
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            logger.info(f"Starting {operation_name}")
            
            try:
                result = func(*args, **kwargs)
                elapsed_time = time.time() - start_time
                
                result_size = len(result) if isinstance(result, (list, dict)) else "N/A"
                
                logger.info(
                    f"Completed {operation_name} in {elapsed_time:.2f}s "
                    f"(result size: {result_size})"
                )
                
                # Log slow queries
                if elapsed_time > 5.0:
                    logger.warning(
                        f"SLOW QUERY: {operation_name} took {elapsed_time:.2f}s"
                    )
                
                return result
            
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(
                    f"Error in {operation_name} after {elapsed_time:.2f}s: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator


def log_cache_operation(cache_name: str, operation: str, hit: bool = None):
    """
    Log cache operations for monitoring.
    
    Args:
        cache_name: Name of the cache
        operation: Type of operation (get, set, clear)
        hit: Whether cache hit occurred (for get operations)
    """
    if operation == "get" and hit is not None:
        status = "HIT" if hit else "MISS"
        logger.debug(f"Cache {cache_name} - {status}")
    elif operation == "set":
        logger.debug(f"Cache {cache_name} - SET")
    elif operation == "clear":
        logger.info(f"Cache {cache_name} - CLEARED")


def log_query_start(
    query_type: str,
    params: Optional[dict] = None
):
    """
    Log the start of a query with parameters.
    
    Args:
        query_type: Type of graph query
        params: Query parameters
    """
    param_str = f" with params {params}" if params else ""
    logger.info(f"Query started: {query_type}{param_str}")


def log_query_end(
    query_type: str,
    result_count: int,
    elapsed_time: float,
    cached: bool = False
):
    """
    Log query completion with metrics.
    
    Args:
        query_type: Type of graph query
        result_count: Number of results returned
        elapsed_time: Time taken in seconds
        cached: Whether result was served from cache
    """
    cache_str = " (cached)" if cached else ""
    logger.info(
        f"Query completed: {query_type} - {result_count} results in "
        f"{elapsed_time:.3f}s{cache_str}"
    )
    
    if elapsed_time > 10.0:
        logger.warning(
            f"SLOW QUERY: {query_type} took {elapsed_time:.2f}s with "
            f"{result_count} results"
        )


def log_error(operation: str, error: Exception):
    """
    Log error with context.
    
    Args:
        operation: Name of operation that failed
        error: Exception that occurred
    """
    logger.error(f"Error in {operation}: {type(error).__name__}: {str(error)}")


class QueryMetrics:
    """
    Track query performance metrics.
    """
    
    def __init__(self):
        self.queries = []
        self.start_time = None
    
    def start(self, query_type: str, params: dict = None):
        """Start tracking a query."""
        self.start_time = time.time()
        log_query_start(query_type, params)
    
    def end(
        self,
        query_type: str,
        result_count: int = 0,
        cached: bool = False
    ):
        """End tracking and log metrics."""
        if self.start_time is None:
            return
        
        elapsed = time.time() - self.start_time
        log_query_end(query_type, result_count, elapsed, cached)
        
        self.queries.append({
            "query_type": query_type,
            "result_count": result_count,
            "elapsed_time": elapsed,
            "cached": cached,
            "timestamp": datetime.now().isoformat()
        })
        
        self.start_time = None
    
    def get_summary(self) -> dict:
        """Get summary of query metrics."""
        if not self.queries:
            return {"total_queries": 0}
        
        total = len(self.queries)
        cached = sum(1 for q in self.queries if q["cached"])
        avg_time = sum(q["elapsed_time"] for q in self.queries) / total
        
        return {
            "total_queries": total,
            "cached_queries": cached,
            "cache_hit_rate": f"{cached/total*100:.1f}%",
            "avg_response_time": f"{avg_time:.3f}s",
            "slowest_query": max(
                self.queries,
                key=lambda q: q["elapsed_time"]
            )["query_type"],
            "slowest_time": f"{max(q['elapsed_time'] for q in self.queries):.2f}s"
        }
