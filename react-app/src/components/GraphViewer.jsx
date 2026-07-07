import apiFetch from '../utils/apiFetch'
import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import cola from 'cytoscape-cola'
import './GraphViewer.css'

cytoscape.use(cola)

const normalizeId = (id) => (id && typeof id === 'string') ? id.replace(/^satellites\//, 'objects/') : id

function GraphViewer({ graphType, selectedConstellation, selectedOrbitalBand, selectedFunctionCategories, selectedOrbitalBands, selectedCountries, pathData, centralityData, centralityMetric, collisionRiskData, collisionViewType, selectedSatellite, communityAlgorithm, communityMinSize, constellationBrowserData, neighborhoodData, functionClusters }) {
  const cyRef = useRef(null)
  const containerRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)
  const [layout, setLayout] = useState('cola')
  const [countryGraphData, setCountryGraphData] = useState(null)
  const [functionGraphData, setFunctionGraphData] = useState(null)
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, node: null })
  const [detailPanel, setDetailPanel] = useState({ visible: false, type: null, data: null })
  const [functionViewMode, setFunctionViewMode] = useState('aggregate')
  const [selectedClusterId, setSelectedClusterId] = useState(null)

  useEffect(() => {
    if (containerRef.current && !cyRef.current) {
      cyRef.current = cytoscape({
        container: containerRef.current,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': '#3498db',
              'label': 'data(label)',
              'width': 30,
              'height': 30,
              'font-size': '12px',
              'text-valign': 'center',
              'text-halign': 'center',
              'color': '#2c3e50',
              'text-outline-width': 2,
              'text-outline-color': '#fff',
              'text-wrap': 'wrap'
            }
          },
          {
            selector: 'node[node_size]',
            style: {
              'width': 'data(node_size)',
              'height': 'data(node_size)'
            }
          },
          {
            selector: 'node[background_color]',
            style: {
              'background-color': 'data(background_color)'
            }
          },
          {
            selector: 'node[is_hub]',
            style: {
              'background-color': '#e74c3c',
              'width': 50,
              'height': 50,
              'font-size': '12px',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'node[is_source]',
            style: {
              'background-color': '#2ecc71',
              'border-width': 4,
              'border-color': '#27ae60',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'node[type="registration_document"]',
            style: {
              'background-color': '#2ecc71',
              'shape': 'rectangle',
              'width': 60,
              'height': 40
            }
          },
          {
            selector: 'node[congestion_risk="low"]',
            style: {
              'background-color': '#27ae60',
              'border-width': 2,
              'border-color': '#1e8449'
            }
          },
          {
            selector: 'node[congestion_risk="medium"]',
            style: {
              'background-color': '#f39c12',
              'border-width': 2,
              'border-color': '#d68910'
            }
          },
          {
            selector: 'node[congestion_risk="high"]',
            style: {
              'background-color': '#e74c3c',
              'border-width': 2,
              'border-color': '#cb4335'
            }
          },
          {
            selector: 'node[congestion_risk="critical"]',
            style: {
              'background-color': '#c0392b',
              'border-width': 2,
              'border-color': '#922b21'
            }
          },
          {
            selector: 'node[edge_count >= 8]',
            style: {
              'border-width': 4,
              'border-style': 'double'
            }
          },
          {
            selector: 'node[edge_count >= 5][edge_count < 8]',
            style: {
              'border-width': 3
            }
          },
          {
            selector: 'edge',
            style: {
              'width': 2,
              'line-color': '#95a5a6',
              'target-arrow-color': '#95a5a6',
              'target-arrow-shape': 'none',
              'curve-style': 'bezier',
              'font-size': '8px',
              'text-background-color': '#fff',
              'text-background-opacity': 0.8,
              'text-background-padding': '2px'
            }
          },
          {
            selector: 'edge[edge_label]',
            style: {
              'label': 'data(edge_label)',
              'font-size': '12px',
              'font-weight': 'bold',
              'text-background-color': '#fff',
              'text-background-opacity': 0.9,
              'text-background-padding': '3px',
              'text-background-shape': 'roundrectangle'
            }
          },
          {
            selector: 'edge[proximity_score < 0.1]',
            style: {
              'line-color': '#c0392b',
              'target-arrow-color': '#c0392b',
              'width': 4
            }
          },
          {
            selector: 'edge[proximity_score >= 0.1][proximity_score < 0.5]',
            style: {
              'line-color': '#e74c3c',
              'target-arrow-color': '#e74c3c',
              'width': 3
            }
          },
          {
            selector: 'edge[proximity_score >= 0.5][proximity_score < 1.5]',
            style: {
              'line-color': '#f39c12',
              'target-arrow-color': '#f39c12',
              'width': 2.5
            }
          },
          {
            selector: 'edge[proximity_score >= 1.5]',
            style: {
              'line-color': '#95a5a6',
              'target-arrow-color': '#95a5a6',
              'width': 2
            }
          },
          {
            selector: 'edge[relationship_type="constellation_membership"]',
            style: {
              'line-color': '#3498db',
              'width': 3,
              'line-style': 'solid'
            }
          },
          {
            selector: 'edge[relationship_type="registration_link"]',
            style: {
              'line-color': '#9b59b6',
              'width': 2,
              'line-style': 'dashed'
            }
          },
          {
            selector: 'edge[relationship_type="orbital_proximity"]',
            style: {
              'line-color': '#e67e22',
              'width': 2,
              'line-style': 'dotted'
            }
          },
          {
            selector: 'edge[edge_type="orbital_proximity"]',
            style: {
              'line-color': 'data(edge_color)',
              'width': 'data(edge_width)',
              'line-style': 'solid'
            }
          },
          {
            selector: 'edge[edge_type="constellation_membership"]',
            style: {
              'line-color': 'data(edge_color)',
              'width': 'data(edge_width)',
              'line-style': 'solid'
            }
          },
          {
            selector: 'edge[edge_type="registration_links"]',
            style: {
              'line-color': 'data(edge_color)',
              'width': 'data(edge_width)',
              'line-style': 'dashed'
            }
          },
          {
            selector: 'node[type="country"]',
            style: {
              'background-color': '#9b59b6',
              'shape': 'hexagon',
              'font-size': '12px',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'node[centrality_score]',
            style: {
              'width': 'data(centrality_size)',
              'height': 'data(centrality_size)',
              'background-color': '#e74c3c',
              'border-width': 3,
              'border-color': '#c0392b'
            }
          },
          {
            selector: 'node[is_path_node]',
            style: {
              'background-color': '#9b59b6',
              'border-width': 4,
              'border-color': '#8e44ad'
            }
          },
          {
            selector: 'node[node_role="source"]',
            style: {
              'background-color': '#e67e22',
              'border-width': 4,
              'border-color': '#d35400',
              'font-weight': 'bold',
              'width': 40,
              'height': 40
            }
          },
          {
            selector: 'node[node_role="destination"]',
            style: {
              'background-color': '#e74c3c',
              'border-width': 4,
              'border-color': '#c0392b',
              'font-weight': 'bold',
              'width': 40,
              'height': 40
            }
          },
          {
            selector: 'node[node_role="hub"]',
            style: {
              'background-color': '#f39c12',
              'border-width': 3,
              'border-color': '#d68910',
              'shape': 'pentagon',
              'width': 50,
              'height': 50,
              'font-weight': 'bold'
            }
          },
          {
            selector: 'node[node_role="intermediate"]',
            style: {
              'background-color': '#9b59b6',
              'border-width': 3,
              'border-color': '#8e44ad',
              'width': 35,
              'height': 35
            }
          },
          {
            selector: 'edge[is_path_edge]',
            style: {
              'line-color': '#9b59b6',
              'width': 5,
              'line-style': 'solid',
              'target-arrow-shape': 'triangle',
              'target-arrow-color': '#9b59b6'
            }
          },
          {
            selector: 'edge[path_edge_type="constellation_membership"]',
            style: {
              'line-color': '#3498db',
              'target-arrow-color': '#3498db',
              'width': 3,
              'color': '#3498db',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'edge[path_edge_type="orbital_proximity"]',
            style: {
              'line-color': '#e67e22',
              'target-arrow-color': '#e67e22',
              'width': 3,
              'color': '#e67e22',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'edge[path_edge_type="registration_link"]',
            style: {
              'line-color': '#9b59b6',
              'target-arrow-color': '#9b59b6',
              'width': 2,
              'line-style': 'dashed',
              'color': '#9b59b6',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'edge[path_edge_type="satellite_lineage"]',
            style: {
              'line-color': '#27ae60',
              'target-arrow-color': '#27ae60',
              'width': 2,
              'color': '#27ae60',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'edge[path_edge_type="collision_risk"]',
            style: {
              'line-color': '#e74c3c',
              'target-arrow-color': '#e74c3c',
              'width': 3,
              'color': '#e74c3c',
              'font-weight': 'bold'
            }
          },
          {
            selector: 'edge[collision_risk]',
            style: {
              'line-color': 'data(risk_color)',
              'width': 'data(risk_width)',
              'line-style': 'solid'
            }
          },
          {
            selector: 'node[is_selected]',
            style: {
              'background-color': '#e74c3c',
              'border-width': 4,
              'border-color': '#c0392b'
            }
          },
          {
            selector: 'edge[relationship_type="collaboration"]',
            style: {
              'line-color': '#27ae60',
              'width': 4,
              'line-style': 'solid'
            }
          },
          {
            selector: 'edge[relationship_type="shared_orbital_band"]',
            style: {
              'line-color': '#3498db',
              'width': 2,
              'line-style': 'dashed'
            }
          },
          {
            selector: ':selected',
            style: {
              'background-color': '#f39c12',
              'line-color': '#f39c12',
              'target-arrow-color': '#f39c12',
              'border-width': 3,
              'border-color': '#f39c12'
            }
          },
          {
            selector: 'node.function-graph-node',
            style: {
              'label': ''
            }
          },
          {
            selector: 'node.function-graph-node:selected, node.function-graph-node.hovered',
            style: {
              'label': 'data(label)'
            }
          },
          {
            selector: 'edge.function-graph-edge',
            style: {
              'opacity': 0.4
            }
          }
        ],
        layout: { name: 'preset' }
      })

      cyRef.current.on('tap', 'node', (evt) => {
        const node = evt.target
        console.log('Node clicked:', node.data())
        // Close context menu on regular click
        setContextMenu({ visible: false, x: 0, y: 0, node: null })
      })

      // Right-click context menu
      cyRef.current.on('cxttap', 'node', (evt) => {
        evt.preventDefault()
        const node = evt.target
        const renderedPosition = evt.renderedPosition || evt.position
        
        setContextMenu({
          visible: true,
          x: renderedPosition.x,
          y: renderedPosition.y,
          node: node.data()
        })
      })

      // Close context menu on background click
      cyRef.current.on('tap', (evt) => {
        if (evt.target === cyRef.current) {
          setContextMenu({ visible: false, x: 0, y: 0, node: null })
        }
      })

      // Hover event handlers for showing labels
      cyRef.current.on('mouseover', 'node.function-graph-node', (evt) => {
        evt.target.addClass('hovered')
      })

      cyRef.current.on('mouseout', 'node.function-graph-node', (evt) => {
        evt.target.removeClass('hovered')
      })
    }

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [graphType])

  useEffect(() => {
    if (graphType === 'constellation' && selectedConstellation) {
      loadConstellationGraph(selectedConstellation)
    } else if (graphType === 'proximity' && selectedOrbitalBand) {
      loadProximityGraph(selectedOrbitalBand)
    } else if (graphType === 'function') {
      loadAllFunctionCategories()
    } else if (graphType === 'country' && !countryGraphData) {
      loadCountryGraph()
    } else if (graphType === 'country' && countryGraphData) {
      filterCountryGraph(selectedCountries)
    } else if (graphType === 'paths' && pathData) {
      renderPathGraph(pathData)
    } else if (graphType === 'centrality' && centralityData) {
      renderCentralityGraph(centralityData, centralityMetric)
    } else if (graphType === 'collision' && collisionRiskData) {
      renderCollisionRiskGraph(collisionRiskData, collisionViewType)
    } else if (graphType === 'communities') {
      loadCommunitiesGraph(communityAlgorithm, communityMinSize)
    } else if (graphType === 'lineage' && selectedSatellite) {
      loadLineageGraph(selectedSatellite)
    } else if (graphType === 'lineage') {
      setStats({ message: 'Select a satellite from the data table to view its lineage' })
      if (cyRef.current) {
        cyRef.current.elements().remove()
      }
    } else if (graphType === 'constellation-browser' && constellationBrowserData) {
      renderConstellationBrowserGraph(constellationBrowserData)
    } else if ((graphType === 'neighborhood' || graphType === 'satellite-observations') && neighborhoodData) {
      renderNeighborhoodGraph(neighborhoodData)
    }
  }, [graphType, selectedConstellation, selectedOrbitalBand, selectedFunctionCategories, selectedOrbitalBands, selectedCountries, pathData, centralityData, centralityMetric, collisionRiskData, collisionViewType, selectedSatellite, communityAlgorithm, communityMinSize, constellationBrowserData, neighborhoodData, functionViewMode, selectedClusterId])

  const loadConstellationGraph = async (constellation) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading constellation graph:', constellation)
    setLoading(true)
    setError(null)
    try {
      const url = `/v2/graphs/constellation/${encodeURIComponent(constellation)}?limit=100`
      console.log('[GraphViewer] Fetching:', url)
      const response = await apiFetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Constellation data received:', {
        hasData: !!data.data,
        nodeCount: data.data?.nodes?.length || 0,
        edgeCount: data.data?.edges?.length || 0
      })
      
      if (!data.data) {
        throw new Error('No data returned from API')
      }
      
      if (!data.data.nodes || data.data.nodes.length === 0) {
        setError('No nodes found for this constellation')
        setStats({ message: 'No data available' })
        return
      }
      
      const elements = {
        nodes: data.data.nodes.filter(node => node.id != null).map(node => ({
          data: {
            ...node,
            id: node.id,
            label: node.name || node.identifier,
            node_size: node.is_hub === true ? 45 : 30
          }
        })),
        edges: data.data.edges.filter(edge => edge.source != null && edge.target != null).map(edge => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            ...edge
          }
        }))
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      setStats(data.data.stats)
      console.log('[GraphViewer] Constellation graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error loading constellation graph:', error)
      setError(`Failed to load constellation: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const loadProximityGraph = async (orbitalBand) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading proximity graph:', orbitalBand)
    setLoading(true)
    setError(null)
    try {
      const url = `/v2/graphs/orbital-proximity/${encodeURIComponent(orbitalBand)}?limit=100`
      console.log('[GraphViewer] Fetching:', url)
      const response = await apiFetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Proximity data received:', {
        hasData: !!data.data,
        nodeCount: data.data?.nodes?.length || 0,
        edgeCount: data.data?.edges?.length || 0
      })
      
      if (!data.data) {
        throw new Error('No data returned from API')
      }
      
      if (!data.data.nodes || data.data.nodes.length === 0) {
        setError('No nodes found for this orbital band')
        setStats({ message: 'No data available' })
        return
      }
      
      if (data.data && data.data.nodes && data.data.nodes.length > 0) {
        const filteredEdges = data.data.edges.filter(edge => edge.source < edge.target).map(edge => ({
          ...edge,
          source: normalizeId(edge.source),
          target: normalizeId(edge.target)
        }))
        
        const edgeCounts = {}
        filteredEdges.forEach(edge => {
          edgeCounts[edge.source] = (edgeCounts[edge.source] || 0) + 1
          edgeCounts[edge.target] = (edgeCounts[edge.target] || 0) + 1
        })
        
        const maxEdgeCount = Math.max(...Object.values(edgeCounts), 1)
        
        const elements = {
          nodes: data.data.nodes.map(node => {
            const nid = normalizeId(node.id)
            const edgeCount = edgeCounts[nid] || 0
            const nodeSize = 25 + (edgeCount / maxEdgeCount) * 40
            
            return {
              data: {
                id: nid,
                label: node.name || node.identifier,
                congestion_risk: node.congestion_risk ? node.congestion_risk.toLowerCase() : 'unknown',
                edge_count: edgeCount,
                node_size: nodeSize,
                identifier: node.identifier,
                name: node.name,
                orbital_band: node.orbital_band,
                apogee_km: node.apogee_km,
                perigee_km: node.perigee_km,
                inclination_degrees: node.inclination_degrees
              }
            }
          }),
          edges: filteredEdges.map(edge => {
              const maxDiff = Math.max(
                edge.apogee_diff_km || 0,
                edge.perigee_diff_km || 0
              )
              const edgeLabel = `${maxDiff.toFixed(1)}km`
              
              return {
                data: {
                  id: edge.id,
                  source: edge.source,
                  target: edge.target,
                  proximity_score: edge.proximity_score,
                  edge_label: edgeLabel,
                  apogee_diff_km: edge.apogee_diff_km,
                  perigee_diff_km: edge.perigee_diff_km,
                  inclination_diff_degrees: edge.inclination_diff_degrees
                }
              }
            })
        }
        
        cyRef.current.elements().remove()
        cyRef.current.add(elements)
        applyLayout(layout)
        setStats(data.data.stats)
        console.log('[GraphViewer] Proximity graph rendered successfully')
      }
    } catch (error) {
      console.error('[GraphViewer] Error loading proximity graph:', error)
      setError(`Failed to load proximity graph: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const loadAllFunctionCategories = async () => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading function categories in', functionViewMode, 'mode')
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ 
        top_n: '15',
        view_mode: functionViewMode
      })
      
      if (functionViewMode === 'detailed' && selectedClusterId) {
        params.append('cluster_id', selectedClusterId)
      }
      
      if (selectedFunctionCategories && selectedFunctionCategories.length > 0) {
        params.append('functions', selectedFunctionCategories.join(','))
      }
      
      if (selectedOrbitalBands && selectedOrbitalBands.length > 0) {
        params.append('orbital_bands', selectedOrbitalBands.join(','))
      }
      
      const url = `/v2/graphs/function-similarity?${params.toString()}`
      console.log('[GraphViewer] Fetching:', url)
      const response = await apiFetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Function data received:', {
        hasData: !!data.data,
        clusterCount: data.data?.clusters?.length || 0,
        nodeCount: data.data?.nodes?.length || 0,
        edgeCount: data.data?.edges?.length || 0
      })
      
      if (!data.data) {
        throw new Error('No data returned from API')
      }
      
      if (!data.data.nodes || data.data.nodes.length === 0) {
        setError('No function similarity data found')
        setStats({ message: 'No data available' })
        return
      }
      
      if (data.data && data.data.nodes && data.data.nodes.length > 0) {
        setFunctionGraphData(data.data)
        
        let elements
        
        if (functionViewMode === 'aggregate') {
          // Aggregate view: nodes are clusters
          const functionColors = {
            'Communications': '#3498db',
            'Earth Observation': '#2ecc71',
            'Scientific Research': '#9b59b6',
            'Navigation': '#f39c12',
            'Military-Defense': '#e74c3c',
            'Space Station': '#1abc9c',
            'Technology-Testing': '#e67e22',
            'Other': '#95a5a6'
          }
          
          elements = {
            nodes: data.data.nodes.map(node => {
              const nodeSize = Math.max(40, Math.min(120, 40 + Math.log(node.satellite_count) * 10))
              return {
                data: {
                  id: node.id,
                  label: `${node.function}\n${node.orbital_band}\n(${node.satellite_count} sats)`,
                  function: node.function,
                  orbital_band: node.orbital_band,
                  satellite_count: node.satellite_count,
                  edge_count: node.edge_count,
                  density: node.density,
                  top_countries: node.top_countries,
                  top_constellations: node.top_constellations,
                  avg_congestion_risk: node.avg_congestion_risk,
                  node_size: nodeSize,
                  background_color: functionColors[node.function] || '#95a5a6',
                  type: 'cluster'
                }
              }
            }),
            edges: data.data.edges.map(edge => {
              const edgeWidth = Math.max(2, Math.min(10, 2 + Math.log(edge.connection_count) * 2))
              return {
                data: {
                  id: edge.id,
                  source: edge.source,
                  target: edge.target,
                  connection_count: edge.connection_count,
                  constellation_edges: edge.constellation_edges,
                  proximity_edges: edge.proximity_edges,
                  avg_proximity_score: edge.avg_proximity_score,
                  edge_width: edgeWidth,
                  edge_color: '#7f8c8d',
                  edge_label: `${edge.connection_count} connections`
                }
              }
            })
          }
        } else {
          // Detailed view: nodes are satellites
          const clusterColors = {}
          if (data.data.clusters) {
            const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e', '#16a085', '#27ae60', '#2980b9', '#8e44ad', '#2c3e50', '#f1c40f', '#d35400']
            data.data.clusters.forEach((cluster, idx) => {
              clusterColors[cluster.cluster_id] = colors[idx % colors.length]
            })
          }
          
          const edgeCounts = {}
          data.data.edges.forEach(edge => {
            edgeCounts[edge.source] = (edgeCounts[edge.source] || 0) + 1
            edgeCounts[edge.target] = (edgeCounts[edge.target] || 0) + 1
          })
          
          const proximityEdges = data.data.edges.filter(e => e.relationship_type === 'orbital_proximity' && e.proximity_score != null)
          const proximityScores = proximityEdges.map(e => e.proximity_score).sort((a, b) => a - b)
          const p25 = proximityScores[Math.floor(proximityScores.length * 0.25)] || 0
          const p50 = proximityScores[Math.floor(proximityScores.length * 0.50)] || 0
          const p75 = proximityScores[Math.floor(proximityScores.length * 0.75)] || 0
          
          const getProximityColor = (score) => {
            if (score == null) return '#e67e22'
            if (score <= p25) return '#e74c3c'
            if (score <= p50) return '#e67e22'
            if (score <= p75) return '#2ecc71'
            return '#27ae60'
          }
          
          const getEdgeColor = (edge) => {
            if (edge.relationship_type === 'orbital_proximity') {
              return getProximityColor(edge.proximity_score)
            } else if (edge.relationship_type === 'constellation_membership') {
              return '#3498db'
            }
            return '#95a5a6'
          }
          
          const getEdgeWidth = (edge) => {
            if (edge.relationship_type === 'orbital_proximity' && edge.proximity_score != null) {
              const normalized = 1 - Math.min(edge.proximity_score / 2, 1)
              return 2 + (normalized * 4)
            } else if (edge.relationship_type === 'constellation_membership') {
              return 3
            }
            return 2
          }
          
          const seenEdges = new Set()
          const uniqueEdges = data.data.edges.filter(edge => {
            const pair = [edge.source, edge.target].sort().join('_')
            if (seenEdges.has(pair)) return false
            seenEdges.add(pair)
            return true
          })
          
          elements = {
            nodes: data.data.nodes.map(node => {
              const edgeCount = edgeCounts[node._id] || 0
              const nodeSize = Math.min(40, 25 + (edgeCount * 0.5))
              return {
                data: {
                  id: node._id,
                  label: node.name || node.identifier || node._id,
                  function: node.function,
                  function_category: node.function_category,
                  country: node.country,
                  orbital_band: node.orbital_band,
                  congestion_risk: node.congestion_risk,
                  cluster_id: node.cluster_id,
                  edge_count: edgeCount,
                  node_size: nodeSize,
                  background_color: node.cluster_id ? clusterColors[node.cluster_id] : '#3498db'
                },
                classes: 'function-graph-node'
              }
            }),
            edges: uniqueEdges.map(edge => {
              return { 
                data: {
                  id: edge.id,
                  source: edge.source,
                  target: edge.target,
                  relationship_type: edge.relationship_type,
                  edge_width: getEdgeWidth(edge),
                  edge_color: getEdgeColor(edge)
                }, 
                classes: 'function-graph-edge' 
              }
            })
          }
        }
        
        cyRef.current.elements().remove()
        cyRef.current.add(elements)
        
        if (functionViewMode === 'aggregate') {
          cyRef.current.on('dblclick', 'node[type="cluster"]', (evt) => {
            const node = evt.target
            const clusterId = node.data('id')
            console.log('[GraphViewer] Drill down to cluster:', clusterId)
            setSelectedClusterId(clusterId)
            setFunctionViewMode('detailed')
          })
        }
        
        applyLayout(layout)
        setStats({
          ...data.data.stats,
          view_mode: functionViewMode,
          selected_cluster: selectedClusterId
        })
        console.log('[GraphViewer] Function graph rendered successfully in', functionViewMode, 'mode')
      }
    } catch (error) {
      console.error('[GraphViewer] Error loading function graph:', error)
      setError(`Failed to load function graph: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const filterFunctionGraph = (categories) => {
    if (!cyRef.current || !functionGraphData) return
    
    console.log('[GraphViewer] Filtering function graph:', { categories })
    setLoading(true)
    setError(null)
    try {
      let filteredNodes, filteredEdges
      
      if (!categories || categories.length === 0) {
        filteredNodes = functionGraphData.nodes
        filteredEdges = functionGraphData.edges
      } else {
        const selectedSet = new Set(categories)
        
        filteredNodes = functionGraphData.nodes.filter(node => 
          selectedSet.has(node.function_category)
        )
        
        const nodeIds = new Set(filteredNodes.map(n => n._id))
        filteredEdges = functionGraphData.edges.filter(edge =>
          nodeIds.has(edge.source) && nodeIds.has(edge.target)
        )
      }
      
      const elements = {
        nodes: filteredNodes.map(node => {
          const isSelected = categories && categories.includes(node.function_category)
          return {
            data: {
              id: node._id,
              label: node.name || node.identifier,
              function: node.function,
              function_category: node.function_category,
              country: node.country,
              orbital_band: node.orbital_band,
              congestion_risk: node.congestion_risk,
              node_size: isSelected ? 25 : 20,
              is_selected: isSelected ? true : undefined
            }
          }
        }),
        edges: filteredEdges.map(edge => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            relationship_type: edge.relationship_type,
            constellation_name: edge.constellation_name,
            registration_document: edge.registration_document,
            proximity_score: edge.proximity_score,
            orbital_band: edge.orbital_band
          }
        }))
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      const newStats = {
        satellites_shown: filteredNodes.length,
        edges_shown: filteredEdges.length,
        total_nodes: filteredNodes.length,
        total_edges: filteredEdges.length
      }
      
      if (categories && categories.length > 0) {
        newStats.selected_categories = categories.join(', ')
      }
      
      setStats(newStats)
    } catch (error) {
      console.error('Error filtering function graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCountryGraph = async () => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading country graph')
    setLoading(true)
    setError(null)
    try {
      const url = '/v2/graphs/country-relations?min_satellites=10&limit_countries=100'
      console.log('[GraphViewer] Fetching:', url)
      const response = await apiFetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Country data received:', {
        hasData: !!data.data,
        nodeCount: data.data?.nodes?.length || 0,
        edgeCount: data.data?.edges?.length || 0
      })
      
      if (!data.data) {
        throw new Error('No data returned from API')
      }
      
      if (!data.data.nodes || data.data.nodes.length === 0) {
        setError('No country relationship data found')
        setStats({ message: 'No data available' })
        return
      }
      
      if (data.data && data.data.nodes && data.data.nodes.length > 0) {
        setCountryGraphData(data.data)
        
        const elements = {
          nodes: data.data.nodes.map(node => {
            const nodeSize = Math.log(node.satellite_count + 1) * 15
            return {
              data: {
                id: node.country,
                label: node.country,
                satellite_count: node.satellite_count,
                node_size: nodeSize,
                type: 'country'
              }
            }
          }),
          edges: data.data.edges.map(edge => ({
            data: {
              id: edge.id,
              source: edge.source,
              target: edge.target,
              relationship_type: edge.relationship_type,
              strength: edge.strength,
              weight: edge.weight,
              orbital_band: edge.orbital_band,
              edge_label: edge.relationship_type === 'collaboration' ? 'Collab' : edge.orbital_band
            }
          }))
        }
        
        cyRef.current.elements().remove()
        cyRef.current.add(elements)
        applyLayout(layout)
        setStats(data.data.stats)
        console.log('[GraphViewer] Country graph rendered successfully')
      }
    } catch (error) {
      console.error('[GraphViewer] Error loading country graph:', error)
      setError(`Failed to load country graph: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const filterCountryGraph = (countries) => {
    if (!cyRef.current || !countryGraphData) return
    
    console.log('[GraphViewer] Filtering country graph:', { countries })
    setLoading(true)
    setError(null)
    try {
      let filteredNodes, filteredEdges
      
      if (!countries || countries.length === 0) {
        filteredNodes = countryGraphData.nodes
        filteredEdges = countryGraphData.edges
      } else {
        const selectedSet = new Set(countries)
        
        filteredNodes = countryGraphData.nodes.filter(node => 
          selectedSet.has(node.country)
        )
        
        filteredEdges = countryGraphData.edges.filter(edge =>
          selectedSet.has(edge.source) && selectedSet.has(edge.target)
        )
      }
      
      const elements = {
        nodes: filteredNodes.map(node => {
          const nodeSize = Math.log(node.satellite_count + 1) * 15
          const isSelected = countries && countries.includes(node.country)
          return {
            data: {
              id: node.country,
              label: node.country,
              satellite_count: node.satellite_count,
              node_size: isSelected ? nodeSize * 1.3 : nodeSize,
              type: 'country',
              is_selected: isSelected ? true : undefined
            }
          }
        }),
        edges: filteredEdges.map(edge => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            relationship_type: edge.relationship_type,
            strength: edge.strength,
            weight: edge.weight,
            orbital_band: edge.orbital_band,
            edge_label: edge.relationship_type === 'collaboration' ? 'Collab' : edge.orbital_band
          }
        }))
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      const newStats = {
        countries_shown: filteredNodes.length,
        relationships_found: filteredEdges.length,
        total_nodes: filteredNodes.length,
        total_edges: filteredEdges.length
      }
      
      if (countries && countries.length > 0) {
        newStats.selected_countries = countries.join(', ')
      }
      
      setStats(newStats)
    } catch (error) {
      console.error('Error filtering country graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const renderPathGraph = (data) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Rendering path graph:', { hasData: !!data, pathFound: data?.path_found })
    setLoading(true)
    setError(null)
    try {
      if (!data || (!data.paths && !data.path)) {
        setError('No path data provided')
        setStats({ message: 'No paths to display' })
        setLoading(false)
        return
      }

      if (!data.path_found) {
        setError(data.message || 'No path found between the two satellites')
        setStats({ message: 'No path found' })
        setLoading(false)
        return
      }

      const paths = data.paths || (data.path ? [data.path] : [])

      if (paths.length === 0) {
        setError('No paths to display')
        setStats({ message: 'No paths to display' })
        setLoading(false)
        return
      }

      const pathNodes = new Map()
      const pathEdgesMap = new Map()
      const edgeTypeCounts = {}

      const firstPath = paths[0]
      const firstVertices = firstPath.vertices || []
      const sourceId = firstVertices.length > 0 ? (firstVertices[0]._id || firstVertices[0]) : null
      const destId = firstVertices.length > 1 ? (firstVertices[firstVertices.length - 1]._id || firstVertices[firstVertices.length - 1]) : null

      const formatEdgeLabel = (edge) => {
        const type = edge.relationship_type || edge.edge_type ||
          (edge._id ? edge._id.split('/')[0] : '') || ''
        if (type === 'constellation_membership') {
          const name = edge.constellation_name ? ` (${edge.constellation_name})` : ''
          return `Constellation Member${name}`
        }
        if (type === 'orbital_proximity') {
          const score = edge.proximity_score !== undefined ? ` (score: ${parseFloat(edge.proximity_score).toFixed(2)})` : ''
          return `Orbital Proximity${score}`
        }
        if (type === 'registration_link') return 'Shared Registration'
        if (type === 'satellite_lineage') return 'Satellite Lineage'
        if (type === 'collision_risk') return 'Collision Risk'
        return edge.constellation_name || type || ''
      }

      paths.forEach(path => {
        const vertices = path.vertices || []
        const edges = path.edges || []

        vertices.forEach(vertex => {
          const nodeId = normalizeId(vertex._id || vertex)
          if (!pathNodes.has(nodeId)) {
            let nodeRole = 'intermediate'
            if (nodeId === sourceId) nodeRole = 'source'
            else if (nodeId === destId) nodeRole = 'destination'
            else if (vertex.is_hub === true || vertex.type === 'constellation_hub') nodeRole = 'hub'
            pathNodes.set(nodeId, {
              id: nodeId,
              identifier: vertex.identifier || nodeId.split('/')[1] || nodeId,
              label: (() => { const identifier = vertex.identifier || nodeId.split('/')[1] || nodeId; const satName = vertex.canonical?.name; return satName ? `${identifier}\n(${satName})` : identifier })(),
              is_path_node: true,
              node_role: nodeRole,
              node_size: nodeRole === 'hub' ? 50 : (nodeRole === 'source' || nodeRole === 'destination') ? 40 : 35
            })
          }
        })

        edges.forEach(edge => {
          const source = normalizeId(edge._from || edge.source)
          const target = normalizeId(edge._to || edge.target)
          if (source && target) {
            const edgeId = `${source}_to_${target}`
            if (!pathEdgesMap.has(edgeId)) {
              const edgeType = edge.relationship_type || edge.edge_type ||
                (edge._id ? edge._id.split('/')[0] : 'other') || 'other'
              const label = formatEdgeLabel(edge)
              edgeTypeCounts[label] = (edgeTypeCounts[label] || 0) + 1
              pathEdgesMap.set(edgeId, {
                id: edgeId,
                source,
                target,
                is_path_edge: true,
                path_edge_type: edgeType,
                edge_label: label
              })
            }
          }
        })
      })

      const supplementaryNodes = paths.flatMap(p => p.supplementary_nodes || [])
      const supplementaryEdges = paths.flatMap(p => p.supplementary_edges || [])

      supplementaryNodes.forEach(node => {
        const nodeId = normalizeId(node._id || node.id)
        if (nodeId && !pathNodes.has(nodeId)) {
          pathNodes.set(nodeId, {
            id: nodeId,
            label: node.document_title || node.name || nodeId.split('/')[1] || nodeId,
            type: 'registration_document',
            node_size: 50
          })
        }
      })

      supplementaryEdges.forEach(edge => {
        const source = normalizeId(edge._from || edge.source)
        const target = normalizeId(edge._to || edge.target)
        if (source && target) {
          const edgeId = `supp_${source}_to_${target}`
          if (!pathEdgesMap.has(edgeId)) {
            const label = 'Shared Registration'
            edgeTypeCounts[label] = (edgeTypeCounts[label] || 0) + 1
            pathEdgesMap.set(edgeId, {
              id: edgeId,
              source,
              target,
              path_edge_type: 'registration_link',
              edge_label: label
            })
          }
        }
      })

      const elements = {
        nodes: Array.from(pathNodes.values()).map(nodeData => ({ data: nodeData })),
        edges: Array.from(pathEdgesMap.values()).map(edgeData => ({ data: edgeData }))
      }

      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)

      setStats({
        paths_found: paths.length,
        total_nodes: elements.nodes.length,
        total_edges: elements.edges.length,
        edge_type_counts: edgeTypeCounts
      })
      console.log('[GraphViewer] Path graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error rendering path graph:', error)
      setError(`Failed to render paths: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const renderCentralityGraph = (data, metric) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Rendering centrality graph:', { hasData: !!data, metric, satelliteCount: data?.satellites?.length || 0 })
    setLoading(true)
    setError(null)
    try {
      if (!data || !data.satellites) {
        setError('No centrality data provided')
        setStats({ message: 'No centrality data to display' })
        setLoading(false)
        return
      }
      
      const satellites = data.satellites || []
      
      if (satellites.length === 0) {
        setError('No satellites found in centrality data')
        setStats({ message: 'No satellites to analyze' })
        setLoading(false)
        return
      }
      
      const getScore = (item) => {
        if (metric === 'degree') return item.degree
        if (metric === 'betweenness') return item.betweenness
        if (metric === 'closeness') return item.closeness
        return 0
      }
      
      const scores = satellites.map(getScore)
      const maxScore = Math.max(...scores, 1)
      
      const elements = {
        nodes: satellites.map(item => {
          const score = getScore(item)
          const normalizedScore = score / maxScore
          const nodeSize = 20 + (normalizedScore * 60)
          
          return {
            data: {
              id: item._id,
              label: item.name || item.identifier || item._id.split('/')[1],
              centrality_score: score,
              centrality_size: nodeSize,
              node_size: nodeSize
            }
          }
        }),
        edges: []
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      setStats({
        metric_type: metric,
        nodes_analyzed: satellites.length,
        max_score: maxScore.toFixed(4)
      })
      console.log('[GraphViewer] Centrality graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error rendering centrality graph:', error)
      setError(`Failed to render centrality: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const renderCollisionRiskGraph = (data, viewType) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Rendering collision risk graph:', { hasData: !!data, viewType, nodesCount: data?.nodes?.length || 0, edgesCount: data?.edges?.length || 0 })
    setLoading(true)
    setError(null)
    try {
      if (!data) {
        setError('No collision risk data provided')
        setStats({ message: 'No collision data to display' })
        setLoading(false)
        return
      }
      
      if (!data.nodes || data.nodes.length === 0) {
        setError('No satellites found in collision risk data')
        setStats({ message: 'No collision risks to analyze' })
        setLoading(false)
        return
      }
      
      // Calculate percentiles for relative coloring
      const riskScores = (data.edges || [])
        .map(e => e.risk_score || e.proximity_score || 0)
        .filter(s => s > 0)
        .sort((a, b) => a - b)
      
      const getPercentile = (arr, p) => {
        if (arr.length === 0) return 0
        const index = Math.ceil(arr.length * p) - 1
        return arr[Math.max(0, index)]
      }
      
      const p25 = getPercentile(riskScores, 0.25)
      const p50 = getPercentile(riskScores, 0.50)
      const p75 = getPercentile(riskScores, 0.75)
      const minScore = riskScores.length > 0 ? riskScores[0] : 0
      const maxScore = riskScores.length > 0 ? riskScores[riskScores.length - 1] : 1
      
      console.log('[GraphViewer] Risk score distribution:', { minScore, p25, p50, p75, maxScore })
      
      const getRiskColor = (riskScore) => {
        if (riskScore >= p75) return '#c0392b'  // Top 25%: Dark red
        if (riskScore >= p50) return '#e74c3c'  // 50-75%: Red
        if (riskScore >= p25) return '#f39c12'  // 25-50%: Orange
        return '#27ae60'                         // Bottom 25%: Green
      }
      
      const getRiskWidth = (riskScore) => {
        const normalized = (riskScore - minScore) / (maxScore - minScore)
        return 2 + (normalized * 6)
      }
      
      const elements = {
        nodes: (data.nodes || []).map(node => ({
          data: {
            id: normalizeId(node.id || node._id),
            label: node.name || node.identifier || (node.id?.split('/')[1]),
            congestion_risk: node.congestion_risk,
            node_size: 25,
            ...node
          }
        })),
        edges: (data.edges || []).map(edge => ({
          data: {
            id: edge.id || `${normalizeId(edge.source || edge._from)}_to_${normalizeId(edge.target || edge._to)}`,
            source: normalizeId(edge.source || edge._from),
            target: normalizeId(edge.target || edge._to),
            collision_risk: edge.risk_score || edge.proximity_score,
            risk_color: getRiskColor(edge.risk_score || edge.proximity_score || 0),
            risk_width: getRiskWidth(edge.risk_score || edge.proximity_score || 0),
            edge_label: edge.risk_score ? edge.risk_score.toFixed(4) : ''
          }
        }))
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      setStats({
        view_type: viewType,
        satellites: elements.nodes.length,
        collision_risks: elements.edges.length,
        risk_range: {
          min: minScore.toFixed(4),
          max: maxScore.toFixed(4),
          p25: p25.toFixed(4),
          median: p50.toFixed(4),
          p75: p75.toFixed(4)
        },
        ...(data.stats || {})
      })
      console.log('[GraphViewer] Collision risk graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error rendering collision risk graph:', error)
      setError(`Failed to render collision risks: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const renderConstellationBrowserGraph = (data) => {
    if (!cyRef.current) return
    
    setLoading(true)
    setError(null)
    try {
      if (!data) {
        setError('No constellation data provided')
        setStats({ message: 'Select a constellation to view its network' })
        setLoading(false)
        return
      }
      
      if (!data.nodes || data.nodes.length === 0) {
        setError('No satellites found in this constellation')
        setStats({ message: 'No data available for this constellation' })
        setLoading(false)
        return
      }
      
      const elements = {
        nodes: (data.nodes || []).map(node => ({
          data: {
            ...node,
            id: normalizeId(node.id || node._id),
            label: node.name || node.identifier || (node.id?.split('/')[1]),
            node_size: node.is_hub === true ? 45 : 30
          }
        })),
        edges: (data.edges || []).map(edge => ({
          data: {
            id: edge.id || `${normalizeId(edge.source || edge._from)}_to_${normalizeId(edge.target || edge._to)}`,
            source: normalizeId(edge.source || edge._from),
            target: normalizeId(edge.target || edge._to),
            ...edge
          }
        }))
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      setStats({
        constellation: data.constellation_name,
        satellites: elements.nodes.length,
        connections: elements.edges.length,
        ...(data.stats || {})
      })
      console.log('[GraphViewer] Constellation browser graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error rendering constellation browser graph:', error)
      setError(`Failed to render constellation: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const renderNeighborhoodGraph = (data) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Rendering neighborhood graph:', { hasData: !!data, nodesCount: data?.nodes?.length || 0, edgesCount: data?.edges?.length || 0 })
    setLoading(true)
    setError(null)
    try {
      if (!data) {
        setError('No neighborhood data provided')
        setStats({ message: 'Select a satellite to view its neighborhood' })
        setLoading(false)
        return
      }
      
      if (!data.nodes || data.nodes.length === 0) {
        setError('No neighbors found for this satellite')
        setStats({ message: 'No data available for this satellite' })
        setLoading(false)
        return
      }
      
      // Calculate percentiles for orbital proximity edges to enable relative coloring
      const proximityEdges = data.edges.filter(e => e.type === 'orbital_proximity' && e.proximity_score != null)
      const proximityScores = proximityEdges.map(e => e.proximity_score).sort((a, b) => a - b)
      const p25 = proximityScores[Math.floor(proximityScores.length * 0.25)] || 0
      const p50 = proximityScores[Math.floor(proximityScores.length * 0.50)] || 0
      const p75 = proximityScores[Math.floor(proximityScores.length * 0.75)] || 0
      
      const getProximityColor = (score) => {
        if (score == null) return '#e67e22' // Default orange
        // Lower score = closer satellites = MORE DANGEROUS
        // Closest 25% (lowest scores) = red (most dangerous)
        // 25-50% = orange
        // 50-75% = light green
        // Farthest 25% (highest scores) = dark green (safest)
        if (score <= p25) return '#e74c3c'      // Red (closest/most dangerous)
        if (score <= p50) return '#e67e22'      // Orange
        if (score <= p75) return '#2ecc71'      // Light green
        return '#27ae60'                        // Dark green (farthest/safest)
      }
      
      const getEdgeLabel = (edge) => {
        if (edge.type === 'orbital_proximity') {
          // Show average separation from apogee/perigee diffs
          if (edge.apogee_diff_km != null && edge.perigee_diff_km != null) {
            const avgDiff = (edge.apogee_diff_km + edge.perigee_diff_km) / 2
            return `~${avgDiff.toFixed(1)} km`
          } else if (edge.proximity_score != null) {
            return `${edge.proximity_score.toFixed(2)}`
          }
        } else if (edge.type === 'constellation_membership' && edge.constellation) {
          return edge.constellation
        } else if (edge.type === 'registration_links') {
          return 'Registration'
        }
        return ''
      }
      
      const getEdgeWidth = (edge) => {
        if (edge.type === 'orbital_proximity' && edge.proximity_score != null) {
          // Lower score = closer (better proximity), so thicker line
          // Assume score range 0-2, invert it
          const normalized = 1 - Math.min(edge.proximity_score / 2, 1)
          return 2 + (normalized * 4)
        }
        return 2.5
      }
      
      const elements = {
        nodes: (data.nodes || []).filter(node => (node.id || node._id) != null).map(node => ({
          data: {
            ...node,
            id: normalizeId(node.id || node._id),
            label: node.name || node.identifier || (node.id?.split('/')[1]),
            is_source: node.is_source,
            distance: node.distance,
            node_size: node.node_size || (node.is_source ? 50 : (40 - ((node.distance || 1) * 5)))
          }
        })),
        edges: (data.edges || []).filter(edge => (edge.source || edge._from) != null && (edge.target || edge._to) != null).map(edge => {
          const label = getEdgeLabel(edge)
          const edgeData = {
            id: edge.id || `${normalizeId(edge.source || edge._from)}_to_${normalizeId(edge.target || edge._to)}`,
            source: normalizeId(edge.source || edge._from),
            target: normalizeId(edge.target || edge._to),
            ...edge,
            edge_type: edge.type,
            edge_width: getEdgeWidth(edge)
          }
          // Only add edge_label if it has a value
          if (label) {
            edgeData.edge_label = label
          }
          // Add color for orbital proximity edges
          if (edge.type === 'orbital_proximity') {
            edgeData.edge_color = getProximityColor(edge.proximity_score)
          }
          return { data: edgeData }
        })
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      const edgeTypeCounts = {}
      elements.edges.forEach(e => {
        const type = e.data.edge_type || 'unknown'
        edgeTypeCounts[type] = (edgeTypeCounts[type] || 0) + 1
      })
      
      setStats({
        source_satellite: data.source_satellite?.name,
        neighbors: elements.nodes.length - 1,
        connections: elements.edges.length,
        edge_types: edgeTypeCounts,
        proximity_distribution: proximityScores.length > 0 ? {
          min: proximityScores[0]?.toFixed(4),
          p25: p25.toFixed(4),
          median: p50.toFixed(4),
          p75: p75.toFixed(4),
          max: proximityScores[proximityScores.length - 1]?.toFixed(4)
        } : null,
        ...(data.stats || {})
      })
      console.log('[GraphViewer] Neighborhood graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error rendering neighborhood graph:', error)
      setError(`Failed to render neighborhood: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const loadCommunitiesGraph = async (algorithm = 'label_propagation', minSize = 3) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading communities graph with params:', { algorithm, minSize })
    setLoading(true)
    setError(null)
    
    try {
      const url = `/v2/graphs/communities?algorithm=${encodeURIComponent(algorithm)}&min_size=${minSize}`
      console.log('[GraphViewer] Fetching:', url)
      
      const response = await apiFetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('[GraphViewer] API error response:', errorText)
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Communities data received:', {
        hasData: !!data.data,
        dataStructure: data.data ? Object.keys(data.data) : [],
        communitiesCount: data.data?.communities?.length || 0,
        communitiesIsArray: Array.isArray(data.data?.communities),
        firstCommunity: data.data?.communities?.[0]
      })
      
      if (!data.data) {
        console.warn('[GraphViewer] No data object in response')
        throw new Error('No data returned from API')
      }
      
      if (!data.data.communities) {
        console.warn('[GraphViewer] No communities property in data:', data.data)
        setError('Invalid response structure: missing communities')
        setStats({ message: 'No communities data in response' })
        if (cyRef.current) {
          cyRef.current.elements().remove()
        }
        return
      }
      
      if (!Array.isArray(data.data.communities)) {
        console.warn('[GraphViewer] Communities is not an array:', typeof data.data.communities)
        setError('Invalid response structure: communities is not an array')
        setStats({ message: 'Invalid communities data format' })
        if (cyRef.current) {
          cyRef.current.elements().remove()
        }
        return
      }
      
      if (data.data.communities.length === 0) {
        console.log('[GraphViewer] No communities found with current parameters')
        setError('No communities found with the current settings')
        setStats({ 
          message: 'No communities detected',
          algorithm: algorithm,
          min_size: minSize,
          suggestion: 'Try lowering the minimum size or using a different algorithm'
        })
        if (cyRef.current) {
          cyRef.current.elements().remove()
        }
        return
      }
      
      const communityColors = {}
      let colorIndex = 0
      const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e', '#16a085', '#d35400']
      
      const nodes = []
      let totalMembers = 0
      
      data.data.communities.forEach((community, idx) => {
        if (!community.community_id) {
          console.warn('[GraphViewer] Community missing community_id:', community)
          return
        }
        
        const communityId = community.community_id
        if (!communityColors[communityId]) {
          communityColors[communityId] = colors[colorIndex % colors.length]
          colorIndex++
        }
        
        const members = community.members || []
        console.log(`[GraphViewer] Community ${communityId}: ${members.length} members`)
        
        if (!Array.isArray(members)) {
          console.warn('[GraphViewer] Community members is not an array:', community)
          return
        }
        
        members.forEach(member => {
          if (!member.satellite_id) {
            console.warn('[GraphViewer] Member missing satellite_id:', member)
            return
          }
          
          totalMembers++
          nodes.push({
            data: {
              id: member.satellite_id,
              label: member.satellite_name || member.identifier || member.satellite_id.split('/')[1],
              community_id: communityId,
              orbital_band: member.orbital_band,
              country: member.country,
              node_size: 25
            },
            style: {
              'background-color': communityColors[communityId]
            }
          })
        })
      })
      
      if (nodes.length === 0) {
        console.warn('[GraphViewer] No valid nodes found in communities')
        setError('No satellites found in communities')
        setStats({ 
          message: 'Communities found but no satellites',
          communities_found: data.data.communities.length 
        })
        if (cyRef.current) {
          cyRef.current.elements().remove()
        }
        return
      }
      
      const elements = {
        nodes: nodes,
        edges: []
      }
      
      console.log('[GraphViewer] Rendering communities:', {
        communitiesCount: data.data.communities.length,
        nodesCount: nodes.length,
        colorsUsed: colorIndex
      })
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      setStats({
        communities_found: data.data.communities.length,
        total_nodes: nodes.length,
        algorithm: data.data.algorithm || algorithm,
        min_size_used: minSize
      })
      console.log('[GraphViewer] Communities graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error loading communities graph:', error)
      setError(`Failed to load communities: ${error.message}`)
      setStats({ error: error.message })
      if (cyRef.current) {
        cyRef.current.elements().remove()
      }
    } finally {
      setLoading(false)
    }
  }

  const loadLineageGraph = async (satelliteId) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading lineage graph for:', satelliteId)
    setLoading(true)
    setError(null)
    try {
      const cleanId = satelliteId.includes('/') ? satelliteId.split('/')[1] : satelliteId
      const url = `/v2/graphs/lineage/${encodeURIComponent(cleanId)}?direction=both&max_depth=5`
      console.log('[GraphViewer] Fetching:', url)
      const response = await apiFetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Lineage data received:', {
        hasData: !!data.data,
        hasRoot: !!data.data?.root,
        ancestorsCount: data.data?.ancestors?.length || 0,
        descendantsCount: data.data?.descendants?.length || 0,
        siblingsCount: data.data?.siblings?.length || 0,
        dataStructure: data.data ? Object.keys(data.data) : []
      })
      
      if (!data.data) {
        throw new Error('No data returned from API')
      }
      
      if (data.data.error) {
        setError(data.data.error)
        setStats({ error: data.data.error })
        return
      }
      
      if (!data.data.root) {
        setError('No lineage data found for this satellite')
        setStats({ message: 'No lineage data available' })
        return
      }
      
      if (data.data && data.data.root) {
        const nodes = []
        const edges = []
        const seenNodeIds = new Set()
        const seenEdgeIds = new Set()
        const nodeColors = {
          root: '#e74c3c',
          ancestor: '#3498db',
          descendant: '#2ecc71',
          sibling: '#9b59b6'
        }
        
        const rootId = normalizeId(data.data.root._id)
        seenNodeIds.add(rootId)
        nodes.push({
          data: {
            id: rootId,
            label: data.data.root.name || data.data.root.identifier,
            node_type: 'root',
            family: data.data.root.family,
            generation: data.data.root.generation,
            node_size: 40,
            background_color: nodeColors.root
          }
        })
        
        (data.data.ancestors || []).filter(item => item.satellite?._id != null).forEach(item => {
          const sat = item.satellite
          const satId = normalizeId(sat._id)
          if (!seenNodeIds.has(satId)) {
            seenNodeIds.add(satId)
            nodes.push({
              data: {
                id: satId,
                label: sat.name || sat.identifier,
                node_type: 'ancestor',
                generation: item.generation,
                node_size: 30,
                background_color: nodeColors.ancestor
              }
            })
          }
          
          if (item.edge) {
            const edgeId = `${satId}_to_${rootId}`
            if (!seenEdgeIds.has(edgeId)) {
              seenEdgeIds.add(edgeId)
              edges.push({
                data: {
                  id: edgeId,
                  source: satId,
                  target: rootId,
                  relationship: item.edge.relationship_type
                }
              })
            }
          }
        })
        
        (data.data.descendants || []).filter(item => item.satellite?._id != null).forEach(item => {
          const sat = item.satellite
          const satId = normalizeId(sat._id)
          if (!seenNodeIds.has(satId)) {
            seenNodeIds.add(satId)
            nodes.push({
              data: {
                id: satId,
                label: sat.name || sat.identifier,
                node_type: 'descendant',
                generation: item.generation,
                node_size: 30,
                background_color: nodeColors.descendant
              }
            })
          }
          
          if (item.edge) {
            const edgeId = `${rootId}_to_${satId}`
            if (!seenEdgeIds.has(edgeId)) {
              seenEdgeIds.add(edgeId)
              edges.push({
                data: {
                  id: edgeId,
                  source: rootId,
                  target: satId,
                  relationship: item.edge.relationship_type
                }
              })
            }
          }
        })
        
        ;(data.data.siblings || []).filter(item => item.satellite?._id != null).forEach(item => {
          const sat = item.satellite
          const satId = normalizeId(sat._id)
          if (!seenNodeIds.has(satId)) {
            seenNodeIds.add(satId)
            nodes.push({
              data: {
                id: satId,
                label: sat.name || sat.identifier,
                node_type: 'sibling',
                node_size: 25,
                background_color: nodeColors.sibling
              }
            })
          }
          const edgeId = `${rootId}_sibling_${satId}`
          if (!seenEdgeIds.has(edgeId)) {
            seenEdgeIds.add(edgeId)
            edges.push({
              data: {
                id: edgeId,
                source: rootId,
                target: satId,
                relationship: item.edge?.relationship_type || 'co_passenger'
              }
            })
          }
        })
        
        const elements = { nodes, edges }
        
        cyRef.current.elements().remove()
        cyRef.current.add(elements)
        if (edges.length > 0) {
          applyLayout('breadthfirst')
        } else {
          cyRef.current.fit(null, 80)
        }
        
        setStats({
          root_satellite: data.data.root.name || data.data.root.identifier,
          total_ancestors: data.data.stats?.total_ancestors || 0,
          total_descendants: data.data.stats?.total_descendants || 0,
          total_siblings: data.data.stats?.total_siblings || 0,
          family: data.data.root.family || 'Unknown',
          ...(edges.length === 0 && { message: 'No known lineage connections for this satellite' })
        })
        console.log('[GraphViewer] Lineage graph rendered successfully')
      }
    } catch (error) {
      console.error('[GraphViewer] Error loading lineage graph:', error)
      setError(`Failed to load lineage: ${error.message}`)
      setStats({ error: 'Failed to load lineage data' })
    } finally {
      setLoading(false)
    }
  }

  const applyLayout = (layoutName) => {
    if (!cyRef.current) return
    
    // Use optimized parameters for function similarity graph
    const isFunctionGraph = graphType === 'function'
    
    const layoutOptions = {
      cola: {
        name: 'cola',
        animate: true,
        randomize: false,
        maxSimulationTime: 2000,
        nodeSpacing: isFunctionGraph ? 100 : 50,
        edgeLength: isFunctionGraph ? 180 : 100
      },
      breadthfirst: {
        name: 'breadthfirst',
        directed: true,
        animate: true,
        spacingFactor: 1.75,
        padding: 30
      },
      circle: {
        name: 'circle',
        animate: true
      },
      grid: {
        name: 'grid',
        animate: true
      },
      concentric: {
        name: 'concentric',
        animate: true,
        concentric: (node) => node.data('is_hub') ? 10 : 1,
        levelWidth: () => 2
      }
    }
    
    try {
      const layout = cyRef.current.layout(layoutOptions[layoutName] || layoutOptions.cola)
      layout.run()
    } catch (err) {
      console.warn('[GraphViewer] Layout failed, falling back to breadthfirst:', err)
      cyRef.current.layout(layoutOptions.breadthfirst).run()
    }
  }

  const handleLayoutChange = (newLayout) => {
    setLayout(newLayout)
    applyLayout(newLayout)
  }

  const handleFitToView = () => {
    if (cyRef.current) {
      cyRef.current.fit(null, 50)
    }
  }

  const handleReset = () => {
    if (cyRef.current) {
      cyRef.current.elements().remove()
      setStats(null)
    }
  }

  const handleShowObservationDetails = (nodeData) => {
    setContextMenu({ visible: false, x: 0, y: 0, node: null })
    // observation_data is embedded in the node by the API
    const obsData = nodeData.observation_data || nodeData
    setDetailPanel({
      visible: true,
      type: 'observation',
      data: obsData
    })
  }

  const handleShowSatelliteDetails = async (nodeData) => {
    setContextMenu({ visible: false, x: 0, y: 0, node: null })
    
    try {
      // Extract satellite ID from node data
      const satelliteId = nodeData.identifier || nodeData.key || nodeData.id?.split('/')[1]
      
      if (!satelliteId) {
        console.error('No satellite identifier found')
        setDetailPanel({
          visible: true,
          type: 'error',
          data: { message: 'No satellite identifier found' }
        })
        return
      }
      
      const response = await apiFetch(`/v2/satellite/${satelliteId}`)
      if (!response.ok) throw new Error('Failed to fetch satellite details')
      
      const result = await response.json()
      setDetailPanel({
        visible: true,
        type: 'satellite',
        data: result.data
      })
    } catch (error) {
      console.error('Error fetching satellite details:', error)
      setDetailPanel({
        visible: true,
        type: 'error',
        data: { message: error.message }
      })
    }
  }

  const handleShowRegistrationDocument = async (nodeData) => {
    setContextMenu({ visible: false, x: 0, y: 0, node: null })
    
    try {
      // Extract document ID from node data
      const docId = nodeData.key || nodeData.id?.split('/')[1]
      
      if (!docId) {
        console.error('No document identifier found', nodeData)
        setDetailPanel({
          visible: true,
          type: 'error',
          data: { message: 'No document identifier found' }
        })
        return
      }
      
      const response = await apiFetch(`/v2/registration-documents/${docId}`)
      if (!response.ok) throw new Error('Failed to fetch registration document')
      
      const result = await response.json()
      setDetailPanel({
        visible: true,
        type: 'registration',
        data: result.data
      })
    } catch (error) {
      console.error('Error fetching registration document:', error)
      setDetailPanel({
        visible: true,
        type: 'error',
        data: { message: error.message }
      })
    }
  }

  return (
    <div className="graph-viewer">
      <div className="graph-controls">
        <div className="control-group">
          <label>Layout:</label>
          <select value={layout} onChange={(e) => handleLayoutChange(e.target.value)}>
            <option value="cola">Force-Directed (Cola)</option>
            <option value="circle">Circle</option>
            <option value="grid">Grid</option>
            <option value="concentric">Concentric</option>
          </select>
        </div>
        
        <button onClick={handleFitToView}>Fit to View</button>
        {graphType === 'function' && stats?.selected_categories && (
          <button onClick={() => filterFunctionGraph([])}>Show All Categories</button>
        )}
        {graphType === 'country' && stats?.selected_countries && (
          <button onClick={() => filterCountryGraph([])}>Show All Countries</button>
        )}
        <button onClick={handleReset}>Clear Graph</button>
        
        {stats && (
          <div className="graph-stats">
            {stats.total_satellites && <span>Satellites: {stats.total_satellites}</span>}
            {stats.satellites && <span>Satellites: {stats.satellites}</span>}
            {stats.members !== undefined && <span>Members: {stats.members}</span>}
            {stats.has_hub && <span>⭐ Has Hub</span>}
            {stats.total_proximity_edges !== undefined && <span>Total Proximity Edges: {stats.total_proximity_edges.toLocaleString()}</span>}
            {stats.edges_shown !== undefined && <span>Showing: {stats.edges_shown} edges</span>}
            {stats.countries_shown !== undefined && <span>Countries: {stats.countries_shown}</span>}
            {stats.relationships_found !== undefined && <span>Relationships: {stats.relationships_found}</span>}
            {stats.selected_categories && <span>🔍 Categories: {stats.selected_categories}</span>}
            {stats.selected_countries && <span>🔍 Selected: {stats.selected_countries}</span>}
            {stats.cluster_count !== undefined && <span>Clusters: {stats.cluster_count}</span>}
            {stats.satellites_shown !== undefined && <span>Satellites: {stats.satellites_shown}</span>}
            {stats.nodes_shown !== undefined && <span>Nodes: {stats.nodes_shown}</span>}
            {stats.paths_found !== undefined && <span>Paths: {stats.paths_found}</span>}
            {stats.total_nodes !== undefined && <span>Nodes: {stats.total_nodes}</span>}
            {stats.total_edges !== undefined && <span>Edges: {stats.total_edges}</span>}
            {stats.metric_type && <span>Metric: {stats.metric_type}</span>}
            {stats.nodes_analyzed !== undefined && <span>Analyzed: {stats.nodes_analyzed} nodes</span>}
            {stats.max_score && <span>Max Score: {stats.max_score}</span>}
            {stats.view_type && <span>View: {stats.view_type}</span>}
            {stats.collision_risks !== undefined && <span>Risks: {stats.collision_risks}</span>}
            {stats.communities_found !== undefined && <span>Communities: {stats.communities_found}</span>}
            {stats.algorithm && <span>Algorithm: {stats.algorithm}</span>}
            {stats.min_size_used !== undefined && <span>Min Size: {stats.min_size_used}</span>}
            {stats.suggestion && <span style={{ fontStyle: 'italic' }}>💡 {stats.suggestion}</span>}
            {stats.root_satellite && <span>Root: {stats.root_satellite}</span>}
            {stats.total_ancestors !== undefined && <span>Ancestors: {stats.total_ancestors}</span>}
            {stats.total_descendants !== undefined && <span>Descendants: {stats.total_descendants}</span>}
            {stats.family && <span>Family: {stats.family}</span>}
            {stats.message && <span>{stats.message}</span>}
            {stats.edge_type_counts && Object.entries(stats.edge_type_counts).map(([type, count]) => (
              <span key={type}>{type}: {count}</span>
            ))}
          </div>
        )}
      </div>
      
      <div className="graph-container">
        <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
        {loading && <div className="loading-overlay">Loading graph...</div>}
        {error && !loading && (
          <div className="error-overlay">
            <div className="error-message">
              <strong>Error:</strong> {error}
            </div>
          </div>
        )}
      </div>
      
      <div className="graph-legend">
        <h4>Legend</h4>
        {graphType === 'proximity' ? (
          <>
            <div className="legend-section">
              <h5>Satellites (size = # neighbors)</h5>
              <div className="legend-item">
                <span className="legend-node low-risk"></span>
                <span>Low Congestion</span>
              </div>
              <div className="legend-item">
                <span className="legend-node medium-risk"></span>
                <span>Medium Congestion</span>
              </div>
              <div className="legend-item">
                <span className="legend-node high-risk"></span>
                <span>High Congestion</span>
              </div>
              <div className="legend-item">
                <span className="legend-node critical-risk"></span>
                <span>Critical Congestion</span>
              </div>
              <div className="legend-note">
                Larger nodes = more proximity connections
              </div>
            </div>
            <div className="legend-section">
              <h5>Proximity (separation)</h5>
              <div className="legend-item">
                <span className="legend-edge-thick critical"></span>
                <span>Very Close (&lt;5km)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-thick high"></span>
                <span>Close (5-15km)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-medium"></span>
                <span>Moderate (15-30km)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge"></span>
                <span>Distant (30-50km)</span>
              </div>
            </div>
          </>
        ) : graphType === 'country' ? (
          <>
            <div className="legend-item">
              <span className="legend-node country"></span>
              <span>Country (size = satellites)</span>
            </div>
            <div className="legend-item">
              <span className="legend-edge-thick collaboration"></span>
              <span>Direct Collaboration</span>
            </div>
            <div className="legend-item">
              <span className="legend-edge-dashed"></span>
              <span>Shared Orbital Band</span>
            </div>
          </>
        ) : graphType === 'function' ? (
          <>
            <div className="legend-item">
              <span className="legend-node satellite"></span>
              <span>Satellite</span>
            </div>
            <div className="legend-item">
              <span className="legend-edge"></span>
              <span>Similar Function</span>
            </div>
          </>
        ) : graphType === 'paths' ? (
          <>
            <div className="legend-section">
              <h5>Nodes</h5>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#e67e22', border: '4px solid #d35400'}}></span>
                <span>Source satellite</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#e74c3c', border: '4px solid #c0392b'}}></span>
                <span>Destination satellite</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#9b59b6', border: '3px solid #8e44ad', width: '18px', height: '18px'}}></span>
                <span>Intermediate satellite</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#f39c12', border: '3px solid #d68910', clipPath: 'polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%)', borderRadius: '0'}}></span>
                <span>Constellation hub</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#2ecc71', borderRadius: '3px', width: '22px', height: '14px'}}></span>
                <span>Registration document</span>
              </div>
            </div>
            <div className="legend-section">
              <h5>Edges</h5>
              <div className="legend-item">
                <span className="legend-edge-thick" style={{backgroundColor: '#3498db'}}></span>
                <span>Constellation membership</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-thick" style={{backgroundColor: '#e67e22'}}></span>
                <span>Orbital proximity</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-medium" style={{backgroundColor: '#9b59b6'}}></span>
                <span>Shared registration</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-medium" style={{backgroundColor: '#e74c3c'}}></span>
                <span>Collision risk</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-medium" style={{backgroundColor: '#27ae60'}}></span>
                <span>Satellite lineage</span>
              </div>
            </div>
          </>
        ) : graphType === 'centrality' ? (
          <>
            <div className="legend-item">
              <span className="legend-node" style={{backgroundColor: '#e74c3c', border: '3px solid #c0392b'}}></span>
              <span>High Centrality (larger = higher score)</span>
            </div>
            <div className="legend-note">
              Node size indicates centrality importance
            </div>
          </>
        ) : graphType === 'collision' ? (
          <>
            <div className="legend-section">
              <h5>Risk Levels (Relative)</h5>
              <div className="legend-item">
                <span className="legend-edge-thick" style={{backgroundColor: '#c0392b'}}></span>
                <span>Highest (Top 25%)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-thick" style={{backgroundColor: '#e74c3c'}}></span>
                <span>High (50-75%)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-medium" style={{backgroundColor: '#f39c12'}}></span>
                <span>Medium (25-50%)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge" style={{backgroundColor: '#27ae60'}}></span>
                <span>Lower (Bottom 25%)</span>
              </div>
              <div className="legend-note">
                Colors are relative to the current view
              </div>
            </div>
          </>
        ) : graphType === 'lineage' ? (
          <>
            <div className="legend-item">
              <span className="legend-node" style={{backgroundColor: '#e74c3c'}}></span>
              <span>Root Satellite (selected)</span>
            </div>
            <div className="legend-item">
              <span className="legend-node" style={{backgroundColor: '#3498db'}}></span>
              <span>Ancestor</span>
            </div>
            <div className="legend-item">
              <span className="legend-node" style={{backgroundColor: '#2ecc71'}}></span>
              <span>Descendant / Fragment</span>
            </div>
            <div className="legend-item">
              <span className="legend-node" style={{backgroundColor: '#9b59b6'}}></span>
              <span>Co-passenger (same launch)</span>
            </div>
            <div className="legend-note">
              Lineage shows family relationships, fragments, and co-passengers
            </div>
          </>
        ) : graphType === 'communities' ? (
          <>
            <div className="legend-section">
              <h5>Community Colors (examples)</h5>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#3498db'}}></span>
                <span>Community 1</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#e74c3c'}}></span>
                <span>Community 2</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#2ecc71'}}></span>
                <span>Community 3</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#f39c12'}}></span>
                <span>Community 4</span>
              </div>
              <div className="legend-note">
                Each color represents a different detected community. Satellites with the same color share similar orbital and functional characteristics.
              </div>
            </div>
          </>
        ) : (graphType === 'neighborhood' || graphType === 'satellite-observations') ? (
          <>
            <div className="legend-section">
              <h5>Nodes</h5>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#2ecc71', border: '4px solid #27ae60'}}></span>
                <span>Source Satellite</span>
              </div>
              <div className="legend-item">
                <span className="legend-node" style={{backgroundColor: '#3498db'}}></span>
                <span>Neighbor (size = hops away)</span>
              </div>
            </div>
            <div className="legend-section">
              <h5>Edge Types</h5>
              <div className="legend-item">
                <div style={{display: 'flex', gap: '2px', alignItems: 'center'}}>
                  <span className="legend-edge-thick" style={{backgroundColor: '#e74c3c', width: '8px'}}></span>
                  <span className="legend-edge-thick" style={{backgroundColor: '#e67e22', width: '8px'}}></span>
                  <span className="legend-edge-thick" style={{backgroundColor: '#2ecc71', width: '8px'}}></span>
                  <span className="legend-edge-thick" style={{backgroundColor: '#27ae60', width: '8px'}}></span>
                </div>
                <span>Orbital Proximity (red=close/dangerous → green=far/safe)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-thick" style={{backgroundColor: '#3498db'}}></span>
                <span>Same Constellation</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-medium" style={{backgroundColor: '#9b59b6', borderStyle: 'dashed'}}></span>
                <span>Same Registration Doc</span>
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="legend-item">
              <span className="legend-node satellite"></span>
              <span>Satellite</span>
            </div>
            <div className="legend-item">
              <span className="legend-node hub"></span>
              <span>Hub Satellite</span>
            </div>
            <div className="legend-item">
              <span className="legend-node document"></span>
              <span>Registration Document</span>
            </div>
            <div className="legend-item">
              <span className="legend-edge"></span>
              <span>Relationship</span>
            </div>
          </>
        )}
      </div>

      {/* Context Menu */}
      {contextMenu.visible && contextMenu.node && (
        <div 
          className="graph-context-menu"
          style={{
            position: 'absolute',
            left: `${contextMenu.x}px`,
            top: `${contextMenu.y}px`,
            zIndex: 1000
          }}
        >
          {/* Registration document nodes */}
          {contextMenu.node.type === 'registration_document' && (
            <div 
              className="context-menu-item"
              onClick={() => handleShowRegistrationDocument(contextMenu.node)}
            >
              📄 Show Registration Document
            </div>
          )}

          {/* Satellite nodes (show if has identifier and is not a document) */}
          {contextMenu.node.identifier && contextMenu.node.type !== 'registration_document' && contextMenu.node.type !== 'observation' && (
            <div
              className="context-menu-item"
              onClick={() => handleShowSatelliteDetails(contextMenu.node)}
            >
              {contextMenu.node.is_hub === true ? '⭐ Show Hub Details' : '📊 Show Satellite Details'}
            </div>
          )}

          {/* Observation nodes */}
          {contextMenu.node.type === 'observation' && (
            <div
              className="context-menu-item"
              onClick={() => handleShowObservationDetails(contextMenu.node)}
            >
              Show Observation Data
            </div>
          )}
        </div>
      )}

      {/* Detail Panel */}
      {detailPanel.visible && (
        <div className="detail-panel-overlay" onClick={() => setDetailPanel({ visible: false, type: null, data: null })}>
          <div className="graph-detail-panel" onClick={(e) => e.stopPropagation()}>
            <div className="graph-detail-panel-header">
              <h3>
                {detailPanel.type === 'satellite' && 'Satellite Details'}
                {detailPanel.type === 'registration' && 'Registration Document'}
                {detailPanel.type === 'observation' && 'Observation Record'}
                {detailPanel.type === 'error' && 'Error'}
              </h3>
              <button 
                className="close-button"
                onClick={() => setDetailPanel({ visible: false, type: null, data: null })}
              >
                ✕
              </button>
            </div>
            
            <div className="graph-detail-panel-content">
              {detailPanel.type === 'satellite' && detailPanel.data && (
                <div className="satellite-details">
                  <pre className="json-display">
                    {JSON.stringify(detailPanel.data, null, 2)}
                  </pre>
                  <button 
                    className="copy-json-button"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(detailPanel.data, null, 2))
                        .then(() => alert('Copied to clipboard!'))
                        .catch(err => console.error('Failed to copy:', err))
                    }}
                  >
                    Copy to Clipboard
                  </button>
                </div>
              )}

              {detailPanel.type === 'registration' && detailPanel.data && (
                <div className="registration-details">
                  <pre className="json-display">
                    {JSON.stringify(detailPanel.data, null, 2)}
                  </pre>
                  <button 
                    className="copy-json-button"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(detailPanel.data, null, 2))
                        .then(() => alert('Copied to clipboard!'))
                        .catch(err => console.error('Failed to copy:', err))
                    }}
                  >
                    Copy to Clipboard
                  </button>
                </div>
              )}

              {detailPanel.type === 'observation' && detailPanel.data && (
                <div className="observation-details">
                  <pre className="json-display">
                    {JSON.stringify(detailPanel.data, null, 2)}
                  </pre>
                  <button
                    className="copy-json-button"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(detailPanel.data, null, 2))
                        .then(() => alert('Copied to clipboard!'))
                        .catch(err => console.error('Failed to copy:', err))
                    }}
                  >
                    Copy to Clipboard
                  </button>
                </div>
              )}

              {detailPanel.type === 'error' && (
                <div className="error-details">
                  <p>{detailPanel.data?.message || 'An unknown error occurred'}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default GraphViewer
