from typing import Dict, Any


def get_nested_field(obj: Dict[str, Any], path: str) -> Any:
    """
    Safely access nested dictionary fields using dot notation.
    
    Args:
        obj: Dictionary to access
        path: Dot-separated path (e.g., "kaggle.orbital_band" or "canonical.orbit.apogee_km")
    
    Returns:
        Value at the path, or None if path doesn't exist
    
    Examples:
        get_nested_field({"a": {"b": {"c": 1}}}, "a.b.c") -> 1
        get_nested_field({"a": {"b": 2}}, "a.x.y") -> None
    """
    keys = path.split(".")
    current = obj
    
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    
    return current


def set_nested_field(obj: Dict[str, Any], path: str, value: Any) -> bool:
    """
    Safely set nested dictionary fields using dot notation.
    Creates intermediate dictionaries if they don't exist.
    
    Args:
        obj: Dictionary to modify
        path: Dot-separated path (e.g., "canonical.orbital_band")
        value: Value to set
    
    Returns:
        True if successful, False otherwise
    
    Examples:
        set_nested_field({}, "a.b.c", 1) -> {"a": {"b": {"c": 1}}}
        set_nested_field({"a": {}}, "a.b", 2) -> {"a": {"b": 2}}
    """
    keys = path.split(".")
    current = obj
    
    for i, key in enumerate(keys[:-1]):
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            return False
        current = current[key]
    
    current[keys[-1]] = value
    return True
