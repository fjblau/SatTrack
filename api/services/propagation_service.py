import math
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import logging

from sgp4.api import Satrec, jday
from skyfield.api import load, wgs84, EarthSatellite
from skyfield.toposlib import GeographicPosition
from api.services.orbital_service import OrbitalService

logger = logging.getLogger(__name__)


class PropagationError(Exception):
    """Exception raised when orbit propagation fails"""
    pass


class PropagationService:
    """
    Service for propagating satellite orbits using SGP4 algorithm.
    
    This service takes TLE (Two-Line Element) data and calculates satellite
    positions at specified time intervals for one complete orbit.
    """
    
    EARTH_RADIUS_KM = 6371.0
    _timescale = None
    
    @classmethod
    def _get_timescale(cls):
        """Get or create Skyfield timescale (lazy loading)"""
        if cls._timescale is None:
            cls._timescale = load.timescale()
        return cls._timescale
    
    @staticmethod
    def _julian_date(dt: datetime) -> tuple[float, float]:
        """
        Convert datetime to Julian date components.
        
        Args:
            dt: datetime object in UTC
            
        Returns:
            Tuple of (jd, fr) where jd is Julian day and fr is fractional day
        """
        jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
        return jd, fr
    
    @classmethod
    def _eci_to_geodetic_accurate(cls, x_km: float, y_km: float, z_km: float, dt: datetime) -> Dict[str, float]:
        """
        Convert ECI coordinates to geodetic using accurate WGS84 ellipsoid model.
        
        This method properly accounts for:
        - Earth's rotation via GMST (Greenwich Mean Sidereal Time) correction
        - WGS84 ellipsoid shape for accurate altitude calculation
        - Proper coordinate frame transformations (ECI -> ECEF -> Geodetic)
        
        Args:
            x_km: X coordinate in kilometers (ECI/TEME frame from SGP4)
            y_km: Y coordinate in kilometers (ECI/TEME frame from SGP4)
            z_km: Z coordinate in kilometers (ECI/TEME frame from SGP4)
            dt: datetime for GMST calculation (must be UTC)
            
        Returns:
            Dictionary with latitude (degrees), longitude (degrees), and altitude (km)
        """
        ts = cls._get_timescale()
        t = ts.from_datetime(dt)
        
        from skyfield.positionlib import Geocentric
        from skyfield.units import Distance
        
        position = Geocentric(
            [Distance(km=x_km).au, Distance(km=y_km).au, Distance(km=z_km).au],
            t=t,
            center=399
        )
        
        geographic = wgs84.geographic_position_of(position)
        
        return {
            'latitude': geographic.latitude.degrees,
            'longitude': geographic.longitude.degrees,
            'altitude_km': geographic.elevation.km
        }
    
    @staticmethod
    def _eci_to_geodetic_simple(x_km: float, y_km: float, z_km: float) -> Dict[str, float]:
        """
        Convert ECI coordinates to geodetic using simplified spherical Earth model.
        
        DEPRECATED: This method uses simplified assumptions and produces errors:
        - Longitude error ~15-17° due to missing GMST (Earth rotation) correction
        - Altitude error ~6-13 km due to spherical Earth assumption
        - Latitude slightly inaccurate due to ignoring Earth's ellipsoid shape
        
        Kept for backward compatibility and debugging. Use _eci_to_geodetic_accurate instead.
        
        Args:
            x_km: X coordinate in kilometers (ECI frame)
            y_km: Y coordinate in kilometers (ECI frame)
            z_km: Z coordinate in kilometers (ECI frame)
            
        Returns:
            Dictionary with latitude (degrees), longitude (degrees), and altitude (km)
        """
        r = math.sqrt(x_km**2 + y_km**2 + z_km**2)
        
        longitude_rad = math.atan2(y_km, x_km)
        latitude_rad = math.asin(z_km / r)
        
        altitude_km = r - PropagationService.EARTH_RADIUS_KM
        
        return {
            'latitude': math.degrees(latitude_rad),
            'longitude': math.degrees(longitude_rad),
            'altitude_km': altitude_km
        }
    
    @classmethod
    def _calculate_position(cls, satellite: Satrec, dt: datetime) -> Dict[str, Any]:
        """
        Calculate satellite position at a specific time.
        
        Args:
            satellite: Initialized Satrec object
            dt: datetime for position calculation
            
        Returns:
            Dictionary with timestamp, ECI coordinates, and geodetic coordinates
            
        Raises:
            PropagationError: If propagation fails
        """
        jd, fr = PropagationService._julian_date(dt)
        
        error_code, position, velocity = satellite.sgp4(jd, fr)
        
        if error_code != 0:
            raise PropagationError(f"SGP4 propagation failed with error code {error_code}")
        
        x_km, y_km, z_km = position
        
        geodetic = cls._eci_to_geodetic_accurate(x_km, y_km, z_km, dt)
        
        return {
            'timestamp': dt.isoformat(),
            'eci': {
                'x_km': x_km,
                'y_km': y_km,
                'z_km': z_km
            },
            'geodetic': {
                'latitude': round(geodetic['latitude'], 6),
                'longitude': round(geodetic['longitude'], 6),
                'altitude_km': round(geodetic['altitude_km'], 2)
            }
        }
    
    @staticmethod
    def propagate_orbit(
        line1: str,
        line2: str,
        start_time: Optional[datetime] = None,
        interval_minutes: int = 1
    ) -> Dict[str, Any]:
        """
        Propagate satellite orbit for one complete orbital period.
        
        Args:
            line1: TLE line 1
            line2: TLE line 2
            start_time: Optional start time for propagation (defaults to current UTC)
            interval_minutes: Time interval in minutes between calculated positions
            
        Returns:
            Dictionary containing:
            - tle_epoch_position: Position at TLE epoch time
            - current_position: Position at start_time
            - future_positions: List of positions for one complete orbit starting from start_time
            - orbital_period_minutes: Orbital period in minutes
            - interval_minutes: Interval used for calculations
            - num_positions: Number of future positions calculated
            
        Raises:
            PropagationError: If TLE is invalid or propagation fails
            ValueError: If interval_minutes is invalid
        """
        if interval_minutes <= 0:
            raise ValueError("interval_minutes must be positive")
        
        if interval_minutes > 60:
            raise ValueError("interval_minutes must be <= 60")
        
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        
        try:
            satellite = Satrec.twoline2rv(line1, line2)
        except Exception as e:
            logger.error(f"Failed to parse TLE: {e}")
            raise PropagationError(f"Invalid TLE format: {str(e)}")
        
        tle_epoch = OrbitalService.extract_tle_epoch(line1)
        if tle_epoch is None:
            raise PropagationError("Failed to extract TLE epoch")
        
        try:
            orbital_params = OrbitalService.calculate_orbital_parameters(line2)
            period_minutes = orbital_params['period_minutes']
        except Exception as e:
            logger.error(f"Failed to calculate orbital period: {e}")
            raise PropagationError(f"Failed to calculate orbital period: {str(e)}")
        
        try:
            tle_epoch_position = PropagationService._calculate_position(satellite, tle_epoch)
        except PropagationError as e:
            logger.error(f"Failed to calculate TLE epoch position: {e}")
            raise PropagationError(f"Failed to calculate TLE epoch position: {str(e)}")
        
        try:
            current_position = PropagationService._calculate_position(satellite, start_time)
        except PropagationError as e:
            logger.error(f"Failed to calculate current position: {e}")
            raise PropagationError(f"Failed to calculate current position: {str(e)}")
        
        num_positions = int(period_minutes / interval_minutes) + 1
        
        future_positions = []
        for i in range(num_positions):
            position_time = start_time + timedelta(minutes=i * interval_minutes)
            
            try:
                position = PropagationService._calculate_position(satellite, position_time)
                future_positions.append(position)
            except PropagationError as e:
                logger.warning(f"Failed to calculate position at {position_time}: {e}")
                continue
        
        if not future_positions:
            raise PropagationError("Failed to calculate any positions")
        
        return {
            'tle_epoch_position': tle_epoch_position,
            'current_position': current_position,
            'future_positions': future_positions,
            'orbital_period_minutes': round(period_minutes, 2),
            'interval_minutes': interval_minutes,
            'num_positions': len(future_positions),
            'tle_epoch': tle_epoch.isoformat()
        }


propagation_service = PropagationService()
