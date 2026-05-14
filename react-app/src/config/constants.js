export const API_ENDPOINTS = {
  COUNTRIES: '/v2/countries',
  STATUSES: '/v2/statuses',
  ORBITAL_BANDS: '/v2/orbital-bands',
  CONGESTION_RISKS: '/v2/congestion-risks',
  OBJECT_TYPES: '/v2/object-types',
  SEARCH: '/v2/search',
  SATELLITE_DETAIL: '/v2/satellite',

  OBJECTS: {
    SEARCH: '/v2/objects',
    GET: (identifier) => `/v2/objects/${encodeURIComponent(identifier)}`,
    BY_CLASS: (objectClass) => `/v2/objects/by-class/${encodeURIComponent(objectClass)}`,
    BY_ALIAS: (aliasType, value) => `/v2/objects/by-alias/${encodeURIComponent(aliasType)}/${encodeURIComponent(value)}`,
    STATS: '/v2/objects/stats',
  },

  PROVENANCE: {
    CHAIN: (objectKey) => `/v2/provenance/objects/${encodeURIComponent(objectKey)}/chain`,
    SIBLINGS: (objectKey) => `/v2/provenance/objects/${encodeURIComponent(objectKey)}/siblings`,
    EVENT: (eventKey) => `/v2/provenance/events/${encodeURIComponent(eventKey)}`,
    LAUNCH: (launchKey) => `/v2/provenance/launches/${encodeURIComponent(launchKey)}`,
    ENTITY: (entityKey) => `/v2/provenance/entities/${encodeURIComponent(entityKey)}`,
    SUMMARY: '/v2/provenance/summary',
  },

  ADMIN: {
    DISCOS_STATUS: '/v2/admin/discos-status',
  },
  TLE: '/v2/tle',
  TLE_INTLDES: '/v2/tle/intldes',
  OBSERVATIONS: '/v2/observations',
  OBSERVATION_ANALYTICS: {
    HEALTH: '/v2/observations/analytics/health-over-time',
    ANOMALIES: '/v2/observations/analytics/anomaly-distribution',
    SOURCES: '/v2/observations/analytics/source-distribution',
    AQL: '/v2/observations/aql',
  },
  
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
    SATELLITE_OBSERVATIONS: '/v2/graphs/satellite-observations',
    OBSERVATION_NEIGHBORHOOD: '/v2/graphs/observations/neighborhood',
    OBSERVATION_SOURCE_NETWORK: '/v2/graphs/observations/source-network',
    OBSERVATION_TEMPORAL_CHAIN: '/v2/graphs/observations/temporal-chain',
    OBSERVATION_ANOMALY_CORRELATION: '/v2/graphs/observations/anomaly-correlation',
    OBSERVATION_GRAPH_STATS: '/v2/graphs/observations/graph-stats',
    OBSERVATION_POPULATE_EDGES: '/v2/graphs/observations/populate-edges',
  },
  
  DOCUMENTS: {
    RESOLVE: '/api/documents/resolve',
    METADATA: '/api/documents/metadata',
  },

  AGENT: {
    ASK: '/v2/ask',
    STATUS: '/v2/ask/status',
    AQL: '/v2/aql',
    KESTREL_MISSION: '/v2/kestrel-mission',
  },

  KESTREL: {
    MANEUVER_PLAN: '/v2/kestrel/maneuver-plan',
    MANEUVER_PLANS: '/v2/kestrel/maneuver-plans',
    MANEUVER_PLAN_GET: (id) => `/v2/kestrel/maneuver-plans/${id}`,
    MANEUVER_PLAN_DELETE: (id) => `/v2/kestrel/maneuver-plans/${id}`,
  },

  EPHEMERIS: {
    BASE: '/v2/ephemeris',
    GENERATE: '/v2/ephemeris/generate',
    LIST: '/v2/ephemeris',
    GET: (id) => `/v2/ephemeris/${id}`,
    CZML: (id) => `/v2/ephemeris/${id}/czml`,
    DELETE: (id) => `/v2/ephemeris/${id}`,
  },

  INSURANCE: {
    DASHBOARD: (carrierId = 'acme_re') => `/v2/insurance/book/dashboard?carrier_id=${carrierId}`,
    ASSETS: (carrierId = 'acme_re', page = 0, limit = 20, shell = '', riskBand = '') => {
      let url = `/v2/insurance/book/assets?carrier_id=${carrierId}&page=${page}&limit=${limit}`
      if (shell) url += `&shell=${encodeURIComponent(shell)}`
      if (riskBand) url += `&risk_band=${encodeURIComponent(riskBand)}`
      return url
    },
    EVENTS: (page = 0, limit = 20) => `/v2/insurance/events?page=${page}&limit=${limit}`,
    EVENT_WITNESSES: (eventId) => `/v2/insurance/event/${encodeURIComponent(eventId)}/witnesses`,
    COVERAGE: (carrierId = 'acme_re') => `/v2/insurance/book/coverage?carrier_id=${carrierId}`,
    CONSTELLATION: '/v2/insurance/constellation/status',
    ASSET_COVERAGE: (satelliteId) => `/v2/insurance/asset/${encodeURIComponent(satelliteId)}/coverage`,
    ASSET_RISK_SCORE: (satelliteId) => `/v2/insurance/asset/${encodeURIComponent(satelliteId)}/risk_score`,
    ASSET_PREDICTION: (satelliteId) => `/v2/insurance/asset/${encodeURIComponent(satelliteId)}/prediction`,
    ASSET_TASKING: (satelliteId) => `/v2/insurance/asset/${encodeURIComponent(satelliteId)}/tasking`,
    EXPORT_EVIDENCE: (lossEventId) => `/v2/insurance/export/evidence/${encodeURIComponent(lossEventId)}`,
    VERIFY: (hash) => `/v2/insurance/evidence/${encodeURIComponent(hash)}/verify`,
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

export const OBJECT_CLASSES = [
  'Payload',
  'Rocket Body',
  'Mission-Related Object',
  'Rocket Fragmentation Debris',
  'Payload Fragmentation Debris',
  'Unknown',
]

export const FILTER_LABELS = {
  ALL_COUNTRIES: 'All Countries',
  ALL_STATUSES: 'All Statuses',
  ALL_ORBITAL_BANDS: 'All Orbital Bands',
  ALL_CONGESTION_RISKS: 'All Congestion Risks',
  ALL_OBJECT_CLASSES: 'All Object Classes',
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
