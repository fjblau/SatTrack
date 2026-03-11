export const API_ENDPOINTS = {
  COUNTRIES: '/v2/countries',
  STATUSES: '/v2/statuses',
  ORBITAL_BANDS: '/v2/orbital-bands',
  CONGESTION_RISKS: '/v2/congestion-risks',
  OBJECT_TYPES: '/v2/object-types',
  SEARCH: '/v2/search',
  SATELLITE_DETAIL: '/v2/satellite',
  TLE: '/v2/tle',
  
  GRAPHS: {
    STATS: '/v2/graphs/stats',
    CONSTELLATION: '/v2/graphs/constellation',
    REGISTRATION_DOCUMENT: '/v2/graphs/registration-document',
    REGISTRATION_DOCUMENTS_ANALYTICS: '/v2/graphs/registration-documents-analytics',
    FUNCTION_SIMILARITY: '/v2/graphs/function-similarity',
    COUNTRY_RELATIONS: '/v2/graphs/country-relations',
    TIMELINE_FILTER_OPTIONS: '/v2/graphs/timeline/filter-options',
    TIMELINE_YEARLY: '/v2/graphs/timeline/yearly',
    LAUNCH_TIMELINE_BREAKDOWN: '/v2/graphs/launch-timeline/breakdown',
    LAUNCH_TIMELINE_MONTHLY: '/v2/graphs/launch-timeline/monthly',
    LAUNCH_TIMELINE_BREAKDOWN_MONTHLY: '/v2/graphs/launch-timeline/breakdown/monthly',
    PATHS: '/v2/graphs/paths',
    CENTRALITY: '/v2/graphs/analytics/centrality',
    COLLISION_RISKS: '/v2/graphs/collision-risks',
    COLLISION_RISKS_NETWORK: '/v2/graphs/collision-risks/network/graph',
    COLLISION_RISKS_CLUSTERS: '/v2/graphs/collision-risks/clusters',
    CROSS_CONSTELLATION_PROXIMITY: '/v2/graphs/cross-constellation-proximity',
    COUNTRY_COOPERATION: '/v2/graphs/country-cooperation-network',
    FUNCTION_CLUSTERS: '/v2/graphs/function-clusters',
    LINEAGE: '/v2/graphs/lineage',
    COMMUNITIES: '/v2/graphs/communities',
    EVOLUTION_TIMELINE: '/v2/graphs/evolution/timeline',
    EVOLUTION_SNAPSHOT: '/v2/graphs/evolution/snapshot',
  },
  
  DOCUMENTS: {
    RESOLVE: '/api/documents/resolve',
    METADATA: '/api/documents/metadata',
  },
}

export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 50,
}

export const ORBITAL_RANGES = {
  APOGEE: {
    MIN: 0,
    MAX: 100000,
  },
  PERIGEE: {
    MIN: 0,
    MAX: 100000,
  },
  INCLINATION: {
    MIN: 0,
    MAX: 180,
  },
}

export const ORBITAL_PROXIMITY = {
  APOGEE_PERIGEE_THRESHOLD_KM: 50,
  INCLINATION_THRESHOLD_DEGREES: 5,
}

export const NUMBER_FORMATS = {
  ORBITAL_DECIMAL_PLACES: 2,
  LARGE_NUMBERS_DECIMAL_PLACES: 0,
}

export const SATELLITE_STATUS = {
  DECAYED: 'decayed',
  DEORBITED: 'deorbited',
}

export const FILTER_LABELS = {
  ALL_COUNTRIES: 'All Countries',
  ALL_STATUSES: 'All Statuses',
  ALL_ORBITAL_BANDS: 'All Orbital Bands',
  ALL_CONGESTION_RISKS: 'All Congestion Risks',
  ALL_OBJECT_TYPES: 'All Object Types',
}

export const UI_TEXT = {
  LOADING: 'Loading...',
  NO_OBJECTS_FOUND: 'No objects found. Try adjusting your filters.',
  SELECT_ROW: 'Select a row to view detailed information',
  SEARCH_PLACEHOLDER: 'Registration or name...',
  TIMELINE_COVERAGE: '98.6% coverage',
  PROXIMITY_DESCRIPTION: 'Satellites with similar orbits (within ±50km apogee/perigee, ±5° inclination)',
  SELECT_MULTIPLE_CATEGORIES: 'Click to select multiple categories',
  SHIFT_SELECT_COUNTRIES: 'Shift-click to select multiple countries',
}

export const EXTERNAL_URLS = {
  N2YO_SATELLITE: 'https://www.n2yo.com/satellite/?s=',
}

export const GRAPH_SETTINGS = {
  FUNCTION_SIMILARITY_LIMIT: 10,
  COUNTRY_RELATIONS_MIN_SATELLITES: 10,
  COUNTRY_RELATIONS_LIMIT: 100,
  EXCLUDED_CONSTELLATIONS: ['Other'],
}

export const CHART_DIMENSIONS = {
  TIMELINE: {
    WIDTH: 1400,
    HEIGHT: 500,
    PADDING: { top: 40, right: 40, bottom: 60, left: 80 },
  },
}

export const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
