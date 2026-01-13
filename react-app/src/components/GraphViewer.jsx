import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import cola from 'cytoscape-cola'
import './GraphViewer.css'

cytoscape.use(cola)

function GraphViewer({ graphType, selectedConstellation, selectedDocument, selectedOrbitalBand, selectedFunctionCategory, selectedCountries }) {
  const cyRef = useRef(null)
  const containerRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [layout, setLayout] = useState('cola')
  const [countryGraphData, setCountryGraphData] = useState(null)

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
              'width': 'data(node_size)',
              'height': 'data(node_size)',
              'font-size': '10px',
              'text-valign': 'center',
              'text-halign': 'center',
              'color': '#2c3e50',
              'text-outline-width': 2,
              'text-outline-color': '#fff'
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
            selector: 'node[type="country"]',
            style: {
              'background-color': '#9b59b6',
              'shape': 'hexagon',
              'font-size': '12px',
              'font-weight': 'bold'
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
    } else if (graphType === 'function' && selectedFunctionCategory) {
      loadFunctionGraph(selectedFunctionCategory)
    } else if (graphType === 'country' && !countryGraphData) {
      loadCountryGraph()
    } else if (graphType === 'country' && countryGraphData) {
      filterCountryGraph(selectedCountries)
    }
  }, [graphType, selectedConstellation, selectedDocument, selectedOrbitalBand, selectedFunctionCategory, selectedCountries, countryGraphData])

  const loadConstellationGraph = async (constellation) => {
    if (!cyRef.current) return
    
    setLoading(true)
    try {
      const response = await fetch(`/v2/graphs/constellation/${encodeURIComponent(constellation)}?limit=100`)
      const data = await response.json()
      
      if (data.data && data.data.nodes && data.data.nodes.length > 0) {
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
      }
    } catch (error) {
      console.error('Error loading constellation graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadRegistrationGraph = async (docKey) => {
    if (!cyRef.current) return
    
    setLoading(true)
    try {
      const response = await fetch(`/v2/graphs/registration-document/${encodeURIComponent(docKey)}?limit=50`)
      const data = await response.json()
      
      if (data.data && data.data.nodes && data.data.nodes.length > 0) {
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
      }
    } catch (error) {
      console.error('Error loading registration graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadProximityGraph = async (orbitalBand) => {
    if (!cyRef.current) return
    
    setLoading(true)
    try {
      const response = await fetch(`/v2/graphs/orbital-proximity/${encodeURIComponent(orbitalBand)}?limit=100`)
      const data = await response.json()
      
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
      }
    } catch (error) {
      console.error('Error loading proximity graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadFunctionGraph = async (category) => {
    if (!cyRef.current) return
    
    setLoading(true)
    try {
      const response = await fetch(`/v2/graphs/function-similarity/category/${encodeURIComponent(category)}?limit=50`)
      const data = await response.json()
      
      if (data.data && data.data.nodes && data.data.nodes.length > 0) {
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
              relationship: edge.relationship
            }
          }))
        }
        
        cyRef.current.elements().remove()
        cyRef.current.add(elements)
        applyLayout(layout)
        setStats(data.data.stats)
      }
    } catch (error) {
      console.error('Error loading function graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCountryGraph = async () => {
    if (!cyRef.current) return
    
    setLoading(true)
    try {
      const response = await fetch('/v2/graphs/country-relations?min_satellites=100&limit_countries=10')
      const data = await response.json()
      
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
      }
    } catch (error) {
      console.error('Error loading country graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const filterCountryGraph = (countries) => {
    if (!cyRef.current || !countryGraphData) return
    
    setLoading(true)
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
            {stats.selected_countries && <span>🔍 Selected: {stats.selected_countries}</span>}
            {stats.satellites_shown !== undefined && <span>Satellites: {stats.satellites_shown}</span>}
          </div>
        )}
      </div>
      
      <div className="graph-container" ref={containerRef}>
        {loading && <div className="loading-overlay">Loading graph...</div>}
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
