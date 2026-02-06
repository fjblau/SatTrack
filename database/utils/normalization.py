import json
import os
from typing import Optional, Dict


class CountryNormalizer:
    """
    Country code and name normalization service.
    
    Normalizes various country codes and names to standardized ISO 3166-1 alpha-3 codes.
    Loads mappings from country_codes.json.
    """
    
    def __init__(self, country_codes_path: Optional[str] = None):
        """
        Initialize CountryNormalizer.
        
        Args:
            country_codes_path: Path to country_codes.json file.
                               If None, uses default path relative to this file.
        """
        if country_codes_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            country_codes_path = os.path.join(current_dir, '..', 'data', 'country_codes.json')
        
        self._load_country_codes(country_codes_path)
    
    def _load_country_codes(self, path: str) -> None:
        """Load country codes from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._country_mapping: Dict[str, str] = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Country codes file not found: {path}. "
                "Please ensure database/data/country_codes.json exists."
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in country codes file: {e}")
    
    def normalize(self, country: Optional[str]) -> Optional[str]:
        """
        Normalize country code or name to standardized ISO 3166-1 alpha-3 code.
        
        Args:
            country: Country code or name to normalize
        
        Returns:
            Normalized country code (ISO 3166-1 alpha-3 or organization code),
            or the original value if not found in mapping,
            or None if input is None/empty
        
        Examples:
            >>> normalizer = CountryNormalizer()
            >>> normalizer.normalize("US")
            'USA'
            >>> normalizer.normalize("United States")
            'USA'
            >>> normalizer.normalize("UK")
            'GBR'
            >>> normalizer.normalize(None)
            None
        """
        if not country or not country.strip():
            return None
        
        country_upper = country.strip().upper()
        
        return self._country_mapping.get(country_upper, country)
    
    def get_all_mappings(self) -> Dict[str, str]:
        """
        Get all country code mappings.
        
        Returns:
            Dictionary of all country code mappings
        """
        return self._country_mapping.copy()
    
    def has_mapping(self, country: str) -> bool:
        """
        Check if a country code or name has a mapping.
        
        Args:
            country: Country code or name to check
        
        Returns:
            True if mapping exists, False otherwise
        """
        if not country:
            return False
        
        country_upper = country.strip().upper()
        return country_upper in self._country_mapping


_global_normalizer: Optional[CountryNormalizer] = None


def get_country_normalizer() -> CountryNormalizer:
    """
    Get global CountryNormalizer instance (singleton).
    
    Returns:
        CountryNormalizer instance
    """
    global _global_normalizer
    if _global_normalizer is None:
        _global_normalizer = CountryNormalizer()
    return _global_normalizer


def normalize_country(country: Optional[str]) -> Optional[str]:
    """
    Convenience function to normalize country using global normalizer.
    
    This function maintains backward compatibility with the old db.normalize_country() function.
    
    Args:
        country: Country code or name to normalize
    
    Returns:
        Normalized country code or None
    """
    normalizer = get_country_normalizer()
    return normalizer.normalize(country)
