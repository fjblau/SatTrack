import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import cola from 'cytoscape-cola'
import './GraphViewer.css'

cytoscape.use(cola)

function GraphViewer({ graphType, selectedConstellation, selectedDocument, selectedOrbitalBand, selectedFunctionCategories, selectedCountries, pathData, centralityData, centralityMetric, collisionRiskData, collisionViewType, selectedSatellite, communityAlgorithm, communityMinSize }) {
  const cyRef = useRef(null)
  const containerRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)
  const [layout, setLayout] = useState('cola')
  const [countryGraphData, setCountryGraphData] = useState(null)
  const [functionGraphData, setFunctionGraphData] = useState(null)

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
              'font-size': '10px',
              'text-valign': 'center',
              'text-halign': 'center',
              'color': '#2c3e50',
              'text-outline-width': 2,
              'text-outline-color': '#fff'
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
              'label': 'data(edge_label)',
              'font-size': '8px',
              'text-background-color': '#fff',
              'text-background-opacity': 0.8,
              'text-background-padding': '2px'
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
          }
        ],
        layout: { name: 'preset' }
      })

      cyRef.current.on('tap', 'node', (evt) => {
        const node = evt.target
        console.log('Node clicked:', node.data())
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
    } else if (graphType === 'registration' && selectedDocument) {
      loadRegistrationGraph(selectedDocument)
    } else if (graphType === 'proximity' && selectedOrbitalBand) {
      loadProximityGraph(selectedOrbitalBand)
    } else if (graphType === 'function' && !functionGraphData) {
      loadAllFunctionCategories()
    } else if (graphType === 'function' && functionGraphData) {
      filterFunctionGraph(selectedFunctionCategories)
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
    }
  }, [graphType, selectedConstellation, selectedDocument, selectedOrbitalBand, selectedFunctionCategories, selectedCountries, countryGraphData, functionGraphData, pathData, centralityData, collisionRiskData, selectedSatellite, communityAlgorithm, communityMinSize])

  const loadConstellationGraph = async (constellation) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading constellation graph:', constellation)
    setLoading(true)
    setError(null)
    try {
      const url = `/v2/graphs/constellation/${encodeURIComponent(constellation)}?limit=100`
      console.log('[GraphViewer] Fetching:', url)
      const response = await fetch(url)
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
        nodes: data.data.nodes.map(node => ({
          data: {
            id: node.id,
            label: node.name || node.identifier,
            is_hub: node.is_hub,
            ...node
          }
        })),
        edges: data.data.edges.map(edge => ({
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

  const loadRegistrationGraph = async (docKey) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading registration graph:', docKey)
    setLoading(true)
    setError(null)
    try {
      const url = `/v2/graphs/registration-document/${encodeURIComponent(docKey)}?limit=50`
      console.log('[GraphViewer] Fetching:', url)
      const response = await fetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Registration data received:', {
        hasData: !!data.data,
        nodeCount: data.data?.nodes?.length || 0,
        edgeCount: data.data?.edges?.length || 0
      })
      
      if (!data.data) {
        throw new Error('No data returned from API')
      }
      
      if (!data.data.nodes || data.data.nodes.length === 0) {
        setError('No nodes found for this registration document')
        setStats({ message: 'No data available' })
        return
      }
      
      const elements = {
        nodes: data.data.nodes.map(node => ({
          data: {
            id: node.id,
            label: node.name || node.url || node.identifier,
            type: node.type,
            ...node
          }
        })),
        edges: data.data.edges.map(edge => ({
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
      console.log('[GraphViewer] Registration graph rendered successfully')
    } catch (error) {
      console.error('[GraphViewer] Error loading registration graph:', error)
      setError(`Failed to load registration document: ${error.message}`)
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
      const response = await fetch(url)
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
        const filteredEdges = data.data.edges.filter(edge => edge.source < edge.target)
        
        const edgeCounts = {}
        filteredEdges.forEach(edge => {
          edgeCounts[edge.source] = (edgeCounts[edge.source] || 0) + 1
          edgeCounts[edge.target] = (edgeCounts[edge.target] || 0) + 1
        })
        
        const maxEdgeCount = Math.max(...Object.values(edgeCounts), 1)
        
        const elements = {
          nodes: data.data.nodes.map(node => {
            const edgeCount = edgeCounts[node.id] || 0
            const nodeSize = 25 + (edgeCount / maxEdgeCount) * 40
            
            return {
              data: {
                id: node.id,
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
    
    console.log('[GraphViewer] Loading function categories')
    setLoading(true)
    setError(null)
    try {
      const url = '/v2/graphs/function-similarity?limit=50'
      console.log('[GraphViewer] Fetching:', url)
      const response = await fetch(url)
      console.log('[GraphViewer] Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('[GraphViewer] Function data received:', {
        hasData: !!data.data,
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
        
        const elements = {
          nodes: data.data.nodes.map(node => ({
            data: {
              id: node._id,
              label: node.name || node.identifier,
              function: node.function,
              function_category: node.function_category,
              country: node.country,
              orbital_band: node.orbital_band,
              congestion_risk: node.congestion_risk,
              node_size: 20
            }
          })),
          edges: data.data.edges.map(edge => ({
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
        setStats(data.data.stats)
        console.log('[GraphViewer] Function graph rendered successfully')
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
        edges_shown: filteredEdges.length
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
      const response = await fetch(url)
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
        relationships_found: filteredEdges.length
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
    
    console.log('[GraphViewer] Rendering path graph:', { hasData: !!data, pathsCount: data?.paths?.length || 0 })
    setLoading(true)
    setError(null)
    try {
      if (!data || !data.paths) {
        setError('No path data provided')
        setStats({ message: 'No paths to display' })
        setLoading(false)
        return
      }
      
      const pathNodes = new Set()
      const pathEdges = new Set()
      
      if (data.paths && data.paths.length > 0) {
        data.paths.forEach(path => {
          path.nodes?.forEach(node => pathNodes.add(node))
          path.edges?.forEach(edge => pathEdges.add(JSON.stringify(edge)))
        })
      }
      
      const elements = {
        nodes: Array.from(pathNodes).map(nodeId => ({
          data: {
            id: nodeId,
            label: nodeId.split('/')[1] || nodeId,
            is_path_node: true,
            node_size: 30
          }
        })),
        edges: Array.from(pathEdges).map(edgeStr => {
          const edge = JSON.parse(edgeStr)
          return {
            data: {
              id: `${edge.source}_to_${edge.target}`,
              source: edge.source,
              target: edge.target,
              is_path_edge: true,
              edge_label: edge.relationship_type || ''
            }
          }
        })
      }
      
      cyRef.current.elements().remove()
      cyRef.current.add(elements)
      applyLayout(layout)
      
      setStats({
        paths_found: data.paths?.length || 0,
        total_nodes: elements.nodes.length,
        total_edges: elements.edges.length
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
      
      const getRiskColor = (riskScore) => {
        if (riskScore > 0.8) return '#c0392b'
        if (riskScore > 0.6) return '#e74c3c'
        if (riskScore > 0.4) return '#f39c12'
        return '#27ae60'
      }
      
      const getRiskWidth = (riskScore) => {
        return 2 + (riskScore * 6)
      }
      
      const elements = {
        nodes: (data.nodes || []).map(node => ({
          data: {
            id: node.id || node._id,
            label: node.name || node.identifier || (node.id?.split('/')[1]),
            congestion_risk: node.congestion_risk,
            node_size: 25,
            ...node
          }
        })),
        edges: (data.edges || []).map(edge => ({
          data: {
            id: edge.id || `${edge.source}_to_${edge.target}`,
            source: edge.source || edge._from,
            target: edge.target || edge._to,
            collision_risk: edge.risk_score || edge.proximity_score,
            risk_color: getRiskColor(edge.risk_score || edge.proximity_score || 0),
            risk_width: getRiskWidth(edge.risk_score || edge.proximity_score || 0),
            edge_label: edge.risk_score ? edge.risk_score.toFixed(2) : ''
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

  const loadCommunitiesGraph = async (algorithm = 'label_propagation', minSize = 3) => {
    if (!cyRef.current) return
    
    console.log('[GraphViewer] Loading communities graph with params:', { algorithm, minSize })
    setLoading(true)
    setError(null)
    
    try {
      const url = `/v2/graphs/communities?algorithm=${encodeURIComponent(algorithm)}&min_size=${minSize}`
      console.log('[GraphViewer] Fetching:', url)
      
      const response = await fetch(url)
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
      const response = await fetch(url)
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
        const nodeColors = {
          root: '#e74c3c',
          ancestor: '#3498db',
          descendant: '#2ecc71'
        }
        
        nodes.push({
          data: {
            id: data.data.root._id,
            label: data.data.root.name || data.data.root.identifier,
            node_type: 'root',
            family: data.data.root.family,
            generation: data.data.root.generation,
            node_size: 40
          },
          style: {
            'background-color': nodeColors.root
          }
        })
        
        (data.data.ancestors || []).forEach(item => {
          const sat = item.satellite
          nodes.push({
            data: {
              id: sat._id,
              label: sat.name || sat.identifier,
              node_type: 'ancestor',
              generation: item.generation,
              node_size: 30
            },
            style: {
              'background-color': nodeColors.ancestor
            }
          })
          
          if (item.edge) {
            edges.push({
              data: {
                id: `${sat._id}_to_${data.data.root._id}`,
                source: sat._id,
                target: data.data.root._id,
                relationship: item.edge.relationship_type
              }
            })
          }
        })
        
        (data.data.descendants || []).forEach(item => {
          const sat = item.satellite
          nodes.push({
            data: {
              id: sat._id,
              label: sat.name || sat.identifier,
              node_type: 'descendant',
              generation: item.generation,
              node_size: 30
            },
            style: {
              'background-color': nodeColors.descendant
            }
          })
          
          if (item.edge) {
            edges.push({
              data: {
                id: `${data.data.root._id}_to_${sat._id}`,
                source: data.data.root._id,
                target: sat._id,
                relationship: item.edge.relationship_type
              }
            })
          }
        })
        
        const elements = { nodes, edges }
        
        cyRef.current.elements().remove()
        cyRef.current.add(elements)
        applyLayout('cola')
        
        setStats({
          root_satellite: data.data.root.name || data.data.root.identifier,
          total_ancestors: data.data.stats?.total_ancestors || 0,
          total_descendants: data.data.stats?.total_descendants || 0,
          family: data.data.root.family || 'Unknown'
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
    
    const layoutOptions = {
      cola: {
        name: 'cola',
        animate: true,
        randomize: false,
        maxSimulationTime: 2000,
        nodeSpacing: 50,
        edgeLength: 100
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
    
    const layout = cyRef.current.layout(layoutOptions[layoutName] || layoutOptions.cola)
    layout.run()
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
            {stats.satellites_shown !== undefined && <span>Satellites: {stats.satellites_shown}</span>}
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
          </div>
        )}
      </div>
      
      <div className="graph-container" ref={containerRef}>
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
            <div className="legend-item">
              <span className="legend-node" style={{backgroundColor: '#9b59b6', border: '4px solid #8e44ad'}}></span>
              <span>Path Node</span>
            </div>
            <div className="legend-item">
              <span className="legend-edge-thick" style={{backgroundColor: '#9b59b6'}}></span>
              <span>Path Edge</span>
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
              <h5>Risk Levels</h5>
              <div className="legend-item">
                <span className="legend-edge-thick" style={{backgroundColor: '#c0392b'}}></span>
                <span>Critical (&gt;0.8)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-thick" style={{backgroundColor: '#e74c3c'}}></span>
                <span>High (0.6-0.8)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge-medium" style={{backgroundColor: '#f39c12'}}></span>
                <span>Medium (0.4-0.6)</span>
              </div>
              <div className="legend-item">
                <span className="legend-edge" style={{backgroundColor: '#27ae60'}}></span>
                <span>Low (&lt;0.4)</span>
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
              <span>Descendant</span>
            </div>
            <div className="legend-note">
              Lineage shows family relationships and generations
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
    </div>
  )
}

export default GraphViewer
