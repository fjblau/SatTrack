import math
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from config import config


class OrbitalService:
    """
    Unified service for orbital calculations from TLE data.
    
    This service consolidates orbital mechanics calculations that were previously
    duplicated across api.py and mqtt_publisher.py.
    """
    
    GM = config.orbital.GM
    EARTH_RADIUS_KM = config.orbital.EARTH_RADIUS_KM
    
    @staticmethod
    def calculate_orbital_parameters(tle_line2: str) -> Dict[str, Any]:
        """
        Calculate orbital parameters from TLE line 2.
        
        Args:
            tle_line2: TLE line 2 string (NORAD format)
        
        Returns:
            Dictionary with orbital parameters:
            - apogee_km: Apogee altitude (km above Earth surface)
            - perigee_km: Perigee altitude (km above Earth surface)
            - inclination_degrees: Orbital inclination
            - period_minutes: Orbital period
            - semi_major_axis_km: Semi-major axis
            - eccentricity: Orbital eccentricity
            - mean_motion_rev_day: Mean motion (revolutions per day)
        
        Raises:
            ValueError: If TLE line 2 is invalid
        """
        try:
            inclination = float(tle_line2[8:16])
            eccentricity = float('0.' + tle_line2[26:33])
            mean_motion_rev_day = float(tle_line2[52:63])
            
            period_minutes = 1440.0 / mean_motion_rev_day
            
            n_rad_per_sec = (mean_motion_rev_day * 2 * math.pi) / 86400.0
            semi_major_axis = (OrbitalService.GM / (n_rad_per_sec * n_rad_per_sec)) ** (1.0/3.0)
            
            apogee = semi_major_axis * (1 + eccentricity) - OrbitalService.EARTH_RADIUS_KM
            perigee = semi_major_axis * (1 - eccentricity) - OrbitalService.EARTH_RADIUS_KM
            
            return {
                'apogee_km': round(apogee, 2),
                'perigee_km': round(perigee, 2),
                'inclination_degrees': round(inclination, 2),
                'period_minutes': round(period_minutes, 2),
                'semi_major_axis_km': round(semi_major_axis, 2),
                'eccentricity': round(eccentricity, 6),
                'mean_motion_rev_day': round(mean_motion_rev_day, 6)
            }
        except (IndexError, ValueError) as e:
            raise ValueError(f"Invalid TLE line 2 format: {str(e)}")
    
    @staticmethod
    def get_orbital_period(mean_motion_rev_day: float) -> float:
        """
        Calculate orbital period from mean motion.
        
        Args:
            mean_motion_rev_day: Mean motion in revolutions per day
        
        Returns:
            Orbital period in minutes
        """
        return 1440.0 / mean_motion_rev_day
    
    @staticmethod
    def get_semi_major_axis(mean_motion_rev_day: float) -> float:
        """
        Calculate semi-major axis from mean motion.
        
        Args:
            mean_motion_rev_day: Mean motion in revolutions per day
        
        Returns:
            Semi-major axis in kilometers
        """
        n_rad_per_sec = (mean_motion_rev_day * 2 * math.pi) / 86400.0
        return (OrbitalService.GM / (n_rad_per_sec * n_rad_per_sec)) ** (1.0/3.0)
    
    @staticmethod
    def calculate_apogee_perigee(semi_major_axis_km: float, eccentricity: float) -> tuple[float, float]:
        """
        Calculate apogee and perigee from semi-major axis and eccentricity.
        
        Args:
            semi_major_axis_km: Semi-major axis in kilometers
            eccentricity: Orbital eccentricity (0-1)
        
        Returns:
            Tuple of (apogee_km, perigee_km) - altitudes above Earth surface
        """
        apogee = semi_major_axis_km * (1 + eccentricity) - OrbitalService.EARTH_RADIUS_KM
        perigee = semi_major_axis_km * (1 - eccentricity) - OrbitalService.EARTH_RADIUS_KM
        return apogee, perigee
    
    @staticmethod
    def extract_tle_epoch(tle_line1: str) -> Optional[datetime]:
        """
        Extract epoch timestamp from TLE line 1.
        
        Args:
            tle_line1: TLE line 1 string
        
        Returns:
            datetime object in UTC timezone, or None if parsing fails
        """
        try:
            epoch_year = int(tle_line1[18:20])
            epoch_day = float(tle_line1[20:32])
            
            year = 2000 + epoch_year if epoch_year < 57 else 1900 + epoch_year
            
            epoch_date = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=epoch_day - 1)
            
            return epoch_date
        except (IndexError, ValueError):
            return None
    
    @staticmethod
    def calculate_orbital_state(
        tle_line1: str,
        tle_line2: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate complete orbital state from TLE.
        
        This is a comprehensive calculation that includes all orbital parameters.
        Compatible with the api.py calculate_orbital_state function.
        
        Args:
            tle_line1: TLE line 1 string
            tle_line2: TLE line 2 string
            timestamp: Optional timestamp for calculation (default: current UTC time)
        
        Returns:
            Dictionary with orbital state including:
            - orbital_parameters: apogee, perigee, period, etc.
            - epoch: TLE epoch timestamp
            - timestamp: Calculation timestamp
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        try:
            orbital_params = OrbitalService.calculate_orbital_parameters(tle_line2)
            epoch = OrbitalService.extract_tle_epoch(tle_line1)
            
            result = {
                **orbital_params,
                'epoch': epoch.isoformat() if epoch else None,
                'timestamp': timestamp.isoformat(),
            }
            
            return result
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': timestamp.isoformat()
            }
    
    @staticmethod
    def classify_orbital_band(apogee_km: float, perigee_km: float) -> str:
        """
        Classify satellite into orbital band based on altitude.
        
        Args:
            apogee_km: Apogee altitude in kilometers
            perigee_km: Perigee altitude in kilometers
        
        Returns:
            Orbital band classification: LEO, MEO, GEO, or HEO
        """
        avg_altitude = (apogee_km + perigee_km) / 2
        altitude_diff = abs(apogee_km - perigee_km)
        
        if altitude_diff > 10000:
            return "HEO"
        elif avg_altitude < 2000:
            return "LEO"
        elif 35586 <= avg_altitude <= 35986:
            return "GEO"
        elif avg_altitude < 35786:
            return "MEO"
        else:
            return "HEO"
    
    @staticmethod
    def parse_scientific_notation(field: str) -> float:
        """
        Parse TLE scientific notation format (assumed decimal point).
        
        Format: ±.NNNNN±N where:
        - First ± is sign
        - NNNNN is mantissa
        - ±N is exponent
        
        Example: " 10270-3" = 0.10270 x 10^-3 = 0.00010270
        
        Args:
            field: Scientific notation string from TLE
        
        Returns:
            Parsed floating point value
        """
        field = field.strip()
        if not field or field == '00000-0' or field == '00000+0':
            return 0.0
        
        try:
            if '-' in field[1:]:
                parts = field.split('-')
                mantissa = float('0.' + parts[0].strip())
                exponent = -int(parts[1])
            elif '+' in field[1:]:
                parts = field.split('+')
                mantissa = float('0.' + parts[0].strip())
                exponent = int(parts[1])
            else:
                return float(field)
            
            return mantissa * (10 ** exponent)
        except Exception:
            return 0.0


orbital_service = OrbitalService()
