import { useState, useEffect } from 'react'
import './EvolutionTimelineView.css'
import { API_ENDPOINTS } from '../config/constants'

function EvolutionTimelineView({ onTimelineLoad }) {
  const [loading, setLoading] = useState(false)
  const [timelineData, setTimelineData] = useState(null)
  const [startDate, setStartDate] = useState('2000')
  const [endDate, setEndDate] = useState(new Date().getFullYear().toString())
  const [granularity, setGranularity] = useState('year')
  const [selectedMetric, setSelectedMetric] = useState('node_count')
  const [hoveredPeriod, setHoveredPeriod] = useState(null)

  useEffect(() => {
    loadTimeline()
  }, [])

  const loadTimeline = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
        granularity: granularity
      })

      const response = await fetch(`${API_ENDPOINTS.GRAPHS.EVOLUTION_TIMELINE}?${params}`)
      const result = await response.json()

      if (result.data) {
        setTimelineData(result.data)
        if (onTimelineLoad) {
          onTimelineLoad(result.data)
        }
      }
    } catch (error) {
      console.error('Error loading evolution timeline:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleApplyFilters = () => {
    loadTimeline()
  }

  const renderMetricChart = () => {
    if (!timelineData || !timelineData.timeline || timelineData.timeline.length === 0) {
      return <div className="no-data">No timeline data available</div>
    }

    const timeline = timelineData.timeline
    const maxValue = Math.max(...timeline.map(t => t[selectedMetric] || 0))
    const chartHeight = 300
    const chartWidth = 900
    const padding = { top: 20, right: 40, bottom: 60, left: 80 }

    const xScale = (index) => {
      return padding.left + (index / (timeline.length - 1)) * (chartWidth - padding.left - padding.right)
    }

    const yScale = (value) => {
      return padding.top + chartHeight - padding.bottom - ((value / maxValue) * (chartHeight - padding.top - padding.bottom))
    }

    const pathData = timeline.map((t, i) => {
      const x = xScale(i)
      const y = yScale(t[selectedMetric] || 0)
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
    }).join(' ')

    const areaData = `M ${padding.left} ${chartHeight - padding.bottom} ${pathData} L ${chartWidth - padding.right} ${chartHeight - padding.bottom} Z`

    const yTicks = 5
    const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) => 
      Math.round((maxValue / yTicks) * i)
    )

    return (
      <div className="metric-chart">
        <svg width={chartWidth} height={chartHeight}>
          <defs>
            <linearGradient id="evolutionGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#2ecc71" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#2ecc71" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          <g className="grid-lines">
            {yTickValues.map(value => (
              <line
                key={value}
                x1={padding.left}
                y1={yScale(value)}
                x2={chartWidth - padding.right}
                y2={yScale(value)}
                stroke="#e0e0e0"
                strokeWidth="1"
              />
            ))}
          </g>

          <g className="y-axis">
            <line
              x1={padding.left}
              y1={padding.top}
              x2={padding.left}
              y2={chartHeight - padding.bottom}
              stroke="#333"
              strokeWidth="2"
            />
            {yTickValues.map(value => (
              <g key={value}>
                <line
                  x1={padding.left - 5}
                  y1={yScale(value)}
                  x2={padding.left}
                  y2={yScale(value)}
                  stroke="#333"
                  strokeWidth="2"
                />
                <text
                  x={padding.left - 10}
                  y={yScale(value)}
                  textAnchor="end"
                  alignmentBaseline="middle"
                  fontSize="12"
                  fill="#666"
                >
                  {value.toLocaleString()}
                </text>
              </g>
            ))}
          </g>

          <g className="x-axis">
            <line
              x1={padding.left}
              y1={chartHeight - padding.bottom}
              x2={chartWidth - padding.right}
              y2={chartHeight - padding.bottom}
              stroke="#333"
              strokeWidth="2"
            />
            {timeline.map((t, i) => {
              if (timeline.length > 20 && i % Math.ceil(timeline.length / 10) !== 0) return null
              return (
                <g key={t.period}>
                  <line
                    x1={xScale(i)}
                    y1={chartHeight - padding.bottom}
                    x2={xScale(i)}
                    y2={chartHeight - padding.bottom + 5}
                    stroke="#333"
                    strokeWidth="2"
                  />
                  <text
                    x={xScale(i)}
                    y={chartHeight - padding.bottom + 20}
                    textAnchor="middle"
                    fontSize="12"
                    fill="#666"
                  >
                    {t.period}
                  </text>
                </g>
              )
            })}
          </g>

          <path
            d={areaData}
            fill="url(#evolutionGradient)"
          />

          <path
            d={pathData}
            fill="none"
            stroke="#2ecc71"
            strokeWidth="3"
          />

          {timeline.map((t, i) => (
            <circle
              key={t.period}
              cx={xScale(i)}
              cy={yScale(t[selectedMetric] || 0)}
              r={hoveredPeriod === t.period ? 6 : 4}
              fill={hoveredPeriod === t.period ? "#27ae60" : "#2ecc71"}
              stroke="#fff"
              strokeWidth="2"
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHoveredPeriod(t.period)}
              onMouseLeave={() => setHoveredPeriod(null)}
            />
          ))}
        </svg>

        {hoveredPeriod && (
          <div className="period-tooltip">
            {(() => {
              const period = timeline.find(t => t.period === hoveredPeriod)
              return (
                <div>
                  <strong>{period.period}</strong>
                  <div>Nodes: {period.node_count.toLocaleString()}</div>
                  <div>Edges: {period.edge_count.toLocaleString()}</div>
                  <div>Density: {period.density.toFixed(6)}</div>
                  <div>Avg Degree: {period.avg_degree.toFixed(2)}</div>
                  <div className="growth-metric">Node Growth: +{period.node_growth.toLocaleString()}</div>
                  <div className="growth-metric">Edge Growth: +{period.edge_growth.toLocaleString()}</div>
                </div>
              )
            })()}
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return <div className="evolution-timeline-loading">Loading graph evolution data...</div>
  }

  return (
    <div className="evolution-timeline-view">
      <div className="timeline-controls">
        <div className="control-group">
          <label htmlFor="start-date">Start Date:</label>
          <input
            id="start-date"
            type="text"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            placeholder="YYYY or YYYY-MM"
          />
        </div>

        <div className="control-group">
          <label htmlFor="end-date">End Date:</label>
          <input
            id="end-date"
            type="text"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            placeholder="YYYY or YYYY-MM"
          />
        </div>

        <div className="control-group">
          <label htmlFor="granularity">Granularity:</label>
          <select
            id="granularity"
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
          >
            <option value="year">Year</option>
            <option value="quarter">Quarter</option>
            <option value="month">Month</option>
          </select>
        </div>

        <button className="apply-button" onClick={handleApplyFilters}>
          Apply
        </button>
      </div>

      <div className="metric-selector">
        <button
          className={selectedMetric === 'node_count' ? 'active' : ''}
          onClick={() => setSelectedMetric('node_count')}
        >
          Node Count
        </button>
        <button
          className={selectedMetric === 'edge_count' ? 'active' : ''}
          onClick={() => setSelectedMetric('edge_count')}
        >
          Edge Count
        </button>
        <button
          className={selectedMetric === 'density' ? 'active' : ''}
          onClick={() => setSelectedMetric('density')}
        >
          Graph Density
        </button>
        <button
          className={selectedMetric === 'avg_degree' ? 'active' : ''}
          onClick={() => setSelectedMetric('avg_degree')}
        >
          Average Degree
        </button>
      </div>

      {renderMetricChart()}

      {timelineData && timelineData.stats && (
        <div className="timeline-stats">
          <div className="stat-card">
            <div className="stat-label">Total Periods</div>
            <div className="stat-value">{timelineData.stats.total_periods}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Node Growth</div>
            <div className="stat-value">{timelineData.stats.total_growth.nodes.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Edge Growth</div>
            <div className="stat-value">{timelineData.stats.total_growth.edges.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Final Node Count</div>
            <div className="stat-value">{timelineData.stats.final_state.node_count.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Final Edge Count</div>
            <div className="stat-value">{timelineData.stats.final_state.edge_count.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Average Density</div>
            <div className="stat-value">{timelineData.stats.avg_density.toFixed(6)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Peak Growth Period</div>
            <div className="stat-value">{timelineData.stats.peak_growth_period}</div>
          </div>
        </div>
      )}
    </div>
  )
}

export default EvolutionTimelineView
