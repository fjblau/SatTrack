import { useState, useEffect, useRef, useCallback } from 'react'
import * as d3 from 'd3'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'

const NODE_COLORS = {
  object: '#2ecc71',
  parent_object: '#e67e22',
  fragmentation_event: '#e74c3c',
  operator: '#3498db',
  launch_vehicle: '#9b59b6',
  launch_site: '#1abc9c',
  unknown: '#95a5a6',
}

function buildGraph(chain, objectKey) {
  if (!chain) return { nodes: [], links: [] }
  const nodes = []
  const links = []
  const addNode = (id, label, type, synthetic = false) => {
    if (!id || nodes.find(n => n.id === id)) return
    nodes.push({ id, label, type, synthetic })
  }
  const addLink = (source, target, label) => {
    if (!source || !target) return
    links.push({ source, target, label })
  }

  const c = chain.chain || {}
  const canonical = c.object?.canonical || {}
  const rootId = objectKey
  addNode(rootId, canonical.object_name || canonical.name || objectKey, 'object')

  if (c.fragmented_from) {
    const pid = c.fragmented_from._key || c.fragmented_from._id
    addNode(pid, c.fragmented_from.canonical?.object_name || pid, 'parent_object')
    addLink(rootId, pid, 'fragmented from')
  }

  if (c.fragmentation_event) {
    const eid = c.fragmentation_event._key || c.fragmentation_event._id
    addNode(eid, c.fragmentation_event.name || eid, 'fragmentation_event')
    addLink(rootId, eid, 'caused by')
  }

  if (c.operator) {
    const oid = c.operator._key || c.operator._id
    addNode(oid, c.operator.name || oid, 'operator')
    addLink(rootId, oid, 'launched by')
  } else if (canonical.country_of_origin || canonical.country) {
    const label = canonical.country_of_origin || canonical.country
    const sid = `syn_country_${label}`
    addNode(sid, label, 'operator', true)
    addLink(rootId, sid, 'country of origin')
  }

  if (c.launch_vehicle) {
    const vid = c.launch_vehicle._key || c.launch_vehicle._id
    addNode(vid, c.launch_vehicle.name || vid, 'launch_vehicle')
    addLink(rootId, vid, 'via')
  }

  if (c.launch_site) {
    const sid = c.launch_site._key || c.launch_site._id
    addNode(sid, c.launch_site.name || sid, 'launch_site')
    addLink(rootId, sid, 'from')
  } else if (canonical.launch_site) {
    const sid = `syn_site_${canonical.launch_site}`
    addNode(sid, canonical.launch_site, 'launch_site', true)
    addLink(rootId, sid, 'launch site')
  }

  return { nodes, links }
}

function ProvenanceGraph({ chain, objectKey }) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!chain || !svgRef.current) return

    const { nodes, links } = buildGraph(chain, objectKey)
    if (nodes.length === 0) return

    const width = svgRef.current.clientWidth || 700
    const height = 420

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(50))

    const defs = svg.append('defs')
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#adb5bd')

    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', '#adb5bd')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrowhead)')

    const linkLabel = svg.append('g')
      .selectAll('text')
      .data(links)
      .enter()
      .append('text')
      .attr('font-size', '10px')
      .attr('fill', '#6c757d')
      .attr('text-anchor', 'middle')
      .text(d => d.label)

    const node = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
      )

    node.append('circle')
      .attr('r', 24)
      .attr('fill', d => NODE_COLORS[d.type] || NODE_COLORS.unknown)
      .attr('fill-opacity', d => d.synthetic ? 0.3 : 1)
      .attr('stroke', d => d.synthetic ? (NODE_COLORS[d.type] || NODE_COLORS.unknown) : '#fff')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', d => d.synthetic ? '5,3' : 'none')

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', '10px')
      .attr('fill', d => d.synthetic ? (NODE_COLORS[d.type] || NODE_COLORS.unknown) : '#fff')
      .attr('font-weight', 600)
      .text(d => {
        const words = d.label.split(/[\s-_]+/)
        return words.slice(0, 2).join(' ').slice(0, 14)
      })

    const tooltip = svg.append('g').attr('class', 'tooltip').style('pointer-events', 'none')
    const tooltipRect = tooltip.append('rect')
      .attr('rx', 4).attr('ry', 4)
      .attr('fill', '#fff').attr('stroke', '#dee2e6')
    const tooltipText = tooltip.append('text')
      .attr('font-size', '11px').attr('fill', '#212529')

    node
      .on('mouseenter', (event, d) => {
        tooltipText.text(d.synthetic ? `${d.label} (from canonical record)` : d.label)
        const bbox = tooltipText.node().getBBox()
        tooltipRect.attr('x', bbox.x - 6).attr('y', bbox.y - 4).attr('width', bbox.width + 12).attr('height', bbox.height + 8)
        tooltip.attr('transform', `translate(${d.x + 30},${d.y - 20})`).style('opacity', 1)
      })
      .on('mouseleave', () => tooltip.style('opacity', 0))

    tooltip.style('opacity', 0)

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      linkLabel
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => simulation.stop()
  }, [chain, objectKey])

  return <svg ref={svgRef} style={{ width: '100%', height: '420px', display: 'block' }} />
}

const LEGEND_ITEMS = Object.entries(NODE_COLORS).map(([type, color]) => ({
  type: type.replace(/_/g, ' '),
  color,
}))

function InfoRow({ label, value }) {
  if (value == null || value === '') return null
  return (
    <tr style={{ borderBottom: '1px solid #f1f3f5' }}>
      <td style={{ padding: '0.4rem 1rem', color: '#6c757d', fontWeight: 500, whiteSpace: 'nowrap', width: '35%', fontSize: '0.82rem' }}>{label}</td>
      <td style={{ padding: '0.4rem 1rem', color: '#212529', fontSize: '0.82rem' }}>{value}</td>
    </tr>
  )
}

function ObjectInfoPanel({ chain }) {
  const c = chain?.chain || {}
  const canonical = c.object?.canonical || {}

  if (!Object.keys(canonical).length) return null

  const orbit = canonical.orbit || {}
  const orbitParts = [
    orbit.apogee_km != null && `${orbit.apogee_km} km apogee`,
    orbit.perigee_km != null && `${orbit.perigee_km} km perigee`,
    orbit.inclination_degrees != null && `${orbit.inclination_degrees}° inc`,
    orbit.period_minutes != null && `${orbit.period_minutes} min period`,
  ].filter(Boolean)

  return (
    <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px', overflow: 'hidden', marginBottom: '1rem' }}>
      <div style={{ padding: '0.65rem 1rem', background: '#f8f9fa', borderBottom: '1px solid #dee2e6', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ fontWeight: 600, fontSize: '0.88rem' }}>Known Provenance Data</span>
        <span style={{ fontSize: '0.75rem', color: '#6c757d', background: '#e9ecef', borderRadius: '4px', padding: '0.1rem 0.45rem' }}>canonical record</span>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          <InfoRow label="Name" value={canonical.object_name || canonical.name} />
          <InfoRow label="NORAD ID" value={canonical.norad_cat_id} />
          <InfoRow label="COSPAR / Int'l Designator" value={canonical.international_designator} />
          <InfoRow label="Status" value={canonical.status} />
          <InfoRow label="Object Class" value={canonical.object_class} />
          <InfoRow label="Country of Origin" value={canonical.country_of_origin || canonical.country} />
          <InfoRow label="Launch Date" value={canonical.launch_date || canonical.date_of_launch} />
          <InfoRow label="Launch Site" value={canonical.launch_site} />
          <InfoRow label="Orbit" value={orbitParts.length ? orbitParts.join(', ') : null} />
          <InfoRow label="Orbital Band" value={canonical.orbital_band} />
          <InfoRow label="UN Registered" value={canonical.un_registered === 'T' ? 'Yes' : null} />
          <InfoRow label="Registration Number" value={canonical.registration_number} />
          <InfoRow label="Function" value={canonical.function} />
        </tbody>
      </table>
    </div>
  )
}

export default function ObjectProvenancePage() {
  const [identifier, setIdentifier] = useState('')
  const [inputValue, setInputValue] = useState('')
  const [chain, setChain] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const lookup = useCallback(async (key) => {
    if (!key) return
    setLoading(true)
    setError(null)
    setChain(null)
    try {
      const res = await apiFetch(API_ENDPOINTS.PROVENANCE.CHAIN(key))
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setChain(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSearch = () => {
    const key = inputValue.trim()
    if (!key) return
    setIdentifier(key)
    lookup(key)
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '0.5rem' }}>Object Provenance</h2>
      <p style={{ color: '#6c757d', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
        Enter an object identifier (document key, COSPAR, NORAD) to visualize its provenance chain.
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <input
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="e.g. 1999-025DEB or 25544"
          style={{ flex: 1, maxWidth: '360px', padding: '0.45rem 0.75rem', borderRadius: '6px', border: '1px solid #dee2e6', fontSize: '0.9rem' }}
        />
        <button
          onClick={handleSearch}
          disabled={loading || !inputValue.trim()}
          style={{ padding: '0.45rem 1.1rem', borderRadius: '6px', border: 'none', background: '#2980b9', color: '#fff', cursor: 'pointer', fontSize: '0.9rem' }}
        >
          {loading ? 'Loading…' : 'Look Up'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', background: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: '6px', color: '#721c24', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {chain && (
        <>
          <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px', overflow: 'hidden', marginBottom: '1rem' }}>
            <div style={{ padding: '0.75rem 1rem', background: '#f8f9fa', borderBottom: '1px solid #dee2e6', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ fontWeight: 600 }}>Provenance Chain: {identifier}</span>
              {chain.caveat && (
                <span style={{ fontSize: '0.78rem', color: '#856404', background: '#fff3cd', border: '1px solid #ffc107', borderRadius: '4px', padding: '0.15rem 0.5rem' }}>
                  {chain.caveat}
                </span>
              )}
            </div>
            <ProvenanceGraph chain={chain} objectKey={identifier} />
          </div>

          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.8rem', marginBottom: '1.5rem' }}>
            {LEGEND_ITEMS.map(({ type, color }) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: color }} />
                <span style={{ color: '#6c757d', textTransform: 'capitalize' }}>{type}</span>
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', border: '2px dashed #adb5bd', background: 'transparent' }} />
              <span style={{ color: '#6c757d' }}>dashed = derived from canonical record</span>
            </div>
          </div>

          <ObjectInfoPanel chain={chain} />
        </>
      )}

      {!chain && !loading && !error && (
        <div style={{ color: '#adb5bd', textAlign: 'center', padding: '3rem 0', fontSize: '0.95rem' }}>
          Enter an object identifier above to visualize its provenance chain.
        </div>
      )}
    </div>
  )
}
