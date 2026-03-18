# Observations Import API

This document describes the API endpoint for submitting satellite observations.

---

## Authentication

All requests must include a Bearer token in the `Authorization` header.

```
Authorization: Bearer <token>
```

Tokens are obtained via the login endpoint. Contact the platform administrator to receive credentials.

---

## Import Endpoint

### `POST /v2/observations/import`

Submits a batch of observations. Each observation is validated, checked for duplicates, and checked against the list of tracked objects before being stored.

**Up to ~100 observations per object per week** is the expected volume. Batching multiple observations in a single request is recommended.

#### Request

**Content-Type:** `application/json`

**Body:**

```json
{
  "observations": [
    { ... },
    { ... }
  ]
}
```

The `observations` array must contain at least one item.

---

#### Observation Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `norad_id` | integer | **Yes** | NORAD catalog number of the object. Must be a positive integer. |
| `observation_epoch` | string | **Yes** | Timestamp of the observation in ISO 8601 format (e.g. `2026-03-01T12:00:00Z`). |
| `source` | string | **Yes** | Identifier of the data source or ground station (e.g. `"ground_station_A"`). Must not be blank. |
| `object_name` | string | No | Human-readable name of the object (e.g. `"ISS (ZARYA)"`). |
| `object_type` | string | No | Classification of the object (e.g. `"payload"`, `"debris"`, `"rocket body"`). |
| `origin_country` | string | No | Country of origin (e.g. `"US"`, `"RU"`). |
| `derived_health_score` | float | No | Health score between `0.0` and `100.0`. |
| `estimated_mass_kg` | float | No | Estimated mass in kilograms. Must be `≥ 0`. |
| `spin_rate_rpm` | float | No | Spin rate in revolutions per minute. Must be `≥ 0`. |
| `thermal` | object | No | Thermal data. See [Thermal Object](#thermal-object) below. |

##### Thermal Object

| Field | Type | Required | Description |
|---|---|---|---|
| `anomaly_flag` | boolean | No | `true` if a thermal anomaly was detected. |

Additional fields may be included in the `thermal` object and will be stored as-is.

---

#### Validation Rules

- `norad_id` must be a positive integer (`> 0`)
- `observation_epoch` must be a valid ISO 8601 datetime string
- `source` must not be empty or whitespace-only
- `estimated_mass_kg` must be `≥ 0` if provided
- `spin_rate_rpm` must be `≥ 0` if provided
- `derived_health_score` must be between `0.0` and `100.0` inclusive if provided

Any request that fails these validations returns HTTP `422 Unprocessable Entity` with field-level error details.

---

#### Duplicate Detection

An observation is considered a **duplicate** if a record with the same `(norad_id, observation_epoch, source)` combination already exists in the database. Duplicates are silently skipped and counted in the response — they do not cause the request to fail.

This also applies within a single batch: if the same `(norad_id, observation_epoch, source)` appears more than once in one request, only the first occurrence is inserted.

---

#### Tracked Objects

Observations are only accepted for objects that have been enabled for tracking. If a `norad_id` is not on the allowed list, the observation is rejected with an error entry in the response. It does **not** cause the entire request to fail.

Contact the platform administrator to add objects to the tracked list.

---

#### Response

HTTP `200 OK`

```json
{
  "total_submitted": 3,
  "inserted": 1,
  "skipped_duplicates": 1,
  "skipped_not_allowed": 1,
  "errors": [
    {
      "norad_id": 99999,
      "observation_epoch": "2026-03-03T12:00:00Z",
      "source": "ground_station_A",
      "error": "norad_id not in allowed tracking list"
    }
  ]
}
```

| Field | Description |
|---|---|
| `total_submitted` | Total number of observations in the request. |
| `inserted` | Number of new observations successfully stored. |
| `skipped_duplicates` | Number of observations skipped because they already exist. |
| `skipped_not_allowed` | Number of observations rejected because the `norad_id` is not tracked. |
| `errors` | List of per-record error details (not-allowed and insert failures). |

---

#### Error Responses

| Status | Reason |
|---|---|
| `401 Unauthorized` | Missing or invalid Bearer token. |
| `422 Unprocessable Entity` | Request body failed schema or field validation. Includes field-level error detail. |
| `503 Service Unavailable` | Database is temporarily unavailable. Retry after a short delay. |

---

## Full Request Example

```json
POST /v2/observations/import
Authorization: Bearer <token>
Content-Type: application/json

{
  "observations": [
    {
      "norad_id": 25544,
      "observation_epoch": "2026-03-01T08:30:00Z",
      "source": "ground_station_A",
      "object_name": "ISS (ZARYA)",
      "object_type": "payload",
      "origin_country": "US",
      "derived_health_score": 91.2,
      "estimated_mass_kg": 419725.0,
      "spin_rate_rpm": 0.0,
      "thermal": {
        "anomaly_flag": false
      }
    },
    {
      "norad_id": 25544,
      "observation_epoch": "2026-03-02T08:30:00Z",
      "source": "ground_station_A",
      "derived_health_score": 89.5
    }
  ]
}
```

**Response:**

```json
{
  "total_submitted": 2,
  "inserted": 2,
  "skipped_duplicates": 0,
  "skipped_not_allowed": 0,
  "errors": []
}
```
