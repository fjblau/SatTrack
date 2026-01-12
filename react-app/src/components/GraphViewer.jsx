import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import cola from 'cytoscape-cola'
import './GraphViewer.css'

cytoscape.use(cola)

function GraphViewer({ graphType, selectedConstellation, selectedDocument, selectedOrbitalBand }) {
  const cyRef = useRef(null)
  const containerRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [layout, setLayout] = useState('cola')

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
              'background-color': '#27ae60'
            }
          },
          {
            selector: 'node[congestion_risk="medium"]',
            style: {
              'background-color': '#f39c12'
            }
          },
          {
            selector: 'node[congestion_risk="high"]',
            style: {
              'background-color': '#e74c3c'
            }
          },
          {
            selector: 'node[congestion_risk="critical"]',
            style: {
              'background-color': '#c0392b'
            }
          },
          {
            selector: 'edge',
            style: {
              'width': 2,
              'line-color': '#95a5a6',
              'target-arrow-color': '#95a5a6',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier'
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
  }, [])

  useEffect(() => {
    if (graphType === 'constellation' && selectedConstellation) {
      loadConstellationGraph(selectedConstellation)
    } else if (graphType === 'registration' && selectedDocument) {
      loadRegistrationGraph(selectedDocument)
    } else if (graphType === 'proximity' && selectedOrbitalBand) {
      loadProximityGraph(selectedOrbitalBand)
    }
  }, [graphType, selectedConstellation, selectedDocument, selectedOrbitalBand])

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
        const elements = {
          nodes: data.data.nodes.map(node => ({
            data: {
              ...node,
              id: node.id,
              label: node.name || node.identifier,
              congestion_risk: node.congestion_risk ? node.congestion_risk.toLowerCase() : null
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
      console.error('Error loading proximity graph:', error)
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
        <button onClick={handleReset}>Clear Graph</button>
        
        {stats && (
          <div className="graph-stats">
            {stats.total_satellites && <span>Satellites: {stats.total_satellites}</span>}
            {stats.satellites && <span>Satellites: {stats.satellites}</span>}
            {stats.members !== undefined && <span>Members: {stats.members}</span>}
            {stats.has_hub && <span>⭐ Has Hub</span>}
            {stats.total_proximity_edges !== undefined && <span>Total Proximity Edges: {stats.total_proximity_edges.toLocaleString()}</span>}
            {stats.edges_shown !== undefined && <span>Showing: {stats.edges_shown} edges</span>}
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
            <div className="legend-item">
              <span className="legend-edge"></span>
              <span>Proximity Link</span>
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
