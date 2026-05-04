import { useState, useEffect, useCallback } from 'react'
import apiFetch from './apiFetch'
import { API_ENDPOINTS } from '../config/constants'

export function useObject(identifier) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!identifier) {
      setData(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    apiFetch(API_ENDPOINTS.OBJECTS.GET(identifier))
      .then(res => res.json())
      .then(json => {
        if (!cancelled) setData(json.data || null)
      })
      .catch(err => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [identifier])

  return { data, loading, error }
}

export function useProvenanceChain(objectKey, { minConfidence } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetch = useCallback(() => {
    if (!objectKey) {
      setData(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    const url = new URL(API_ENDPOINTS.PROVENANCE.CHAIN(objectKey), window.location.origin)
    if (minConfidence != null) url.searchParams.set('min_confidence', minConfidence)
    apiFetch(url.pathname + url.search)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(json => {
        if (!cancelled) setData(json)
      })
      .catch(err => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [objectKey, minConfidence])

  useEffect(() => {
    const cancel = fetch()
    return cancel
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function useFragmentationEvents({ limit = 100, skip = 0 } = {}) {
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const aql = `
FOR ev IN fragmentation_events
  SORT ev.epoch DESC
  LIMIT ${skip}, ${limit}
  RETURN {
    _key: ev._key,
    _id: ev._id,
    name: ev.name,
    epoch: ev.epoch,
    event_type: ev.event_type,
    parent_cospar: ev.parent_cospar,
    orbital_regime: ev.orbital_regime,
    fragment_count: ev.fragment_count
  }
`.trim()

    const countAql = 'RETURN LENGTH(fragmentation_events)'

    Promise.all([
      apiFetch(API_ENDPOINTS.OBSERVATION_ANALYTICS.AQL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: aql }),
      }).then(r => r.json()),
      apiFetch(API_ENDPOINTS.OBSERVATION_ANALYTICS.AQL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: countAql }),
      }).then(r => r.json()),
    ])
      .then(([eventsRes, countRes]) => {
        if (!cancelled) {
          setData(eventsRes.data || [])
          setTotal(countRes.data?.[0] || 0)
        }
      })
      .catch(err => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [limit, skip])

  return { data, total, loading, error }
}
