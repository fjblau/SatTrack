import math
from typing import Dict, Any


def convert_to_norad_format(designator: str) -> str | None:
    """
    Convert YYYY-NNNSSS format to YYNNNSSG format.
    
    Example: '2024-001A' -> '24001A'
    """
    try:
        parts = designator.split('-')
        if len(parts) >= 2:
            year = parts[0]
            rest = '-'.join(parts[1:])
            yy = year[-2:]
            
            if '-' in rest:
                seq, piece = rest.split('-')
            else:
                if rest[-1].isalpha():
                    seq = rest[:-1]
                    piece = rest[-1]
                else:
                    seq = rest
                    piece = ""
            
            if piece:
                return f"{yy}{int(seq):0>3}{piece}"
            else:
                return f"{yy}{int(seq):0>3}"
    except:
        pass
    return None


def filter_nan_values(data: Dict[str, Any], recursive: bool = True) -> Dict[str, Any]:
    """
    Filter out NaN and Inf values from a dictionary.
    Also removes MongoDB special fields like '_id'.
    
    Args:
        data: Dictionary to filter
        recursive: Whether to recursively filter nested dictionaries
    
    Returns:
        Filtered dictionary
    """
    filtered = {}
    
    for k, v in data.items():
        if k == '_id':
            continue
        
        if isinstance(v, dict) and recursive:
            filtered_nested = filter_nan_values(v, recursive=True)
            if filtered_nested:
                filtered[k] = filtered_nested
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            continue
        else:
            filtered[k] = v
    
    return filtered
