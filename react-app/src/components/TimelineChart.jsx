import { useState, useEffect, useRef } from 'react'
import './TimelineChart.css'

function TimelineChart({ selectedTimePeriod }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [hoveredYear, setHoveredYear] = useState(null)
  const svgRef = useRef(null)

  useEffect(() => {
    loadTimelineData()
  }, [])

  const loadTimelineData = async () => {
    setLoading(true)
    try {
      const response = await fetch('/v2/graphs/stats')
      const result = await response.json()
      
      if (result.data && result.data.recent_launch_years) {
        const allYears = result.data.recent_launch_years
        setData(allYears.sort((a, b) => a.year - b.year))
      }
    } catch (error) {
      console.error('Error loading timeline data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="timeline-loading">Loading timeline data...</div>
  }

  if (data.length === 0) {
    return <div className="timeline-empty">No timeline data available</div>
  }

  const width = 900
  const height = 400
  const padding = { top: 40, right: 40, bottom: 60, left: 80 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const maxCount = Math.max(...data.map(d => d.satellite_count))
  const minYear = Math.min(...data.map(d => d.year))
  const maxYear = Math.max(...data.map(d => d.year))

  const xScale = (year) => {
    return padding.left + ((year - minYear) / (maxYear - minYear)) * chartWidth
  }

  const yScale = (count) => {
    return padding.top + chartHeight - (count / maxCount) * chartHeight
  }

  const pathData = data.map((d, i) => {
    const x = xScale(d.year)
    const y = yScale(d.satellite_count)
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
  }).join(' ')

  const areaData = `M ${xScale(minYear)} ${padding.top + chartHeight} ${pathData} L ${xScale(maxYear)} ${padding.top + chartHeight} Z`

  const yTicks = 5
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) => 
    Math.round((maxCount / yTicks) * i)
  )

  return (
    <div className="timeline-chart-container">
      <div className="timeline-header">
        <h3>Satellite Launches Over Time</h3>
        <p className="timeline-subtitle">
          Total satellites tracked: {data.reduce((sum, d) => sum + d.satellite_count, 0).toLocaleString()}
        </p>
      </div>

      <svg 
        ref={svgRef}
        width={width} 
        height={height}
        className="timeline-chart"
      >
        <defs>
          <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#3498db" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#3498db" stopOpacity="0.05" />
          </linearGradient>
        </defs>

        <g className="grid-lines">
          {yTickValues.map(value => (
            <line
              key={value}
              x1={padding.left}
              y1={yScale(value)}
              x2={padding.left + chartWidth}
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
            y2={padding.top + chartHeight}
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
          <text
            x={padding.left - 60}
            y={padding.top + chartHeight / 2}
            textAnchor="middle"
            fontSize="13"
            fill="#333"
            fontWeight="600"
            transform={`rotate(-90, ${padding.left - 60}, ${padding.top + chartHeight / 2})`}
          >
            Satellites Launched
          </text>
        </g>

        <g className="x-axis">
          <line
            x1={padding.left}
            y1={padding.top + chartHeight}
            x2={padding.left + chartWidth}
            y2={padding.top + chartHeight}
            stroke="#333"
            strokeWidth="2"
          />
          {data.map(d => (
            <g key={d.year}>
              <line
                x1={xScale(d.year)}
                y1={padding.top + chartHeight}
                x2={xScale(d.year)}
                y2={padding.top + chartHeight + 5}
                stroke="#333"
                strokeWidth="2"
              />
              <text
                x={xScale(d.year)}
                y={padding.top + chartHeight + 20}
                textAnchor="middle"
                fontSize="12"
                fill="#666"
              >
                {d.year}
              </text>
            </g>
          ))}
          <text
            x={padding.left + chartWidth / 2}
            y={height - 10}
            textAnchor="middle"
            fontSize="13"
            fill="#333"
            fontWeight="600"
          >
            Launch Year
          </text>
        </g>

        <path
          d={areaData}
          fill="url(#areaGradient)"
        />

        <path
          d={pathData}
          fill="none"
          stroke="#3498db"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        <g className="data-points">
          {data.map(d => {
            const isSelected = selectedTimePeriod === d.year.toString()
            const isHovered = hoveredYear === d.year
            return (
              <g key={d.year}>
                <circle
                  cx={xScale(d.year)}
                  cy={yScale(d.satellite_count)}
                  r={isSelected || isHovered ? 6 : 4}
                  fill={isSelected ? "#e74c3c" : "#3498db"}
                  stroke="white"
                  strokeWidth="2"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredYear(d.year)}
                  onMouseLeave={() => setHoveredYear(null)}
                />
                {(isHovered || isSelected) && (
                  <g>
                    <rect
                      x={xScale(d.year) - 50}
                      y={yScale(d.satellite_count) - 40}
                      width="100"
                      height="30"
                      fill="rgba(0, 0, 0, 0.8)"
                      rx="4"
                    />
                    <text
                      x={xScale(d.year)}
                      y={yScale(d.satellite_count) - 30}
                      textAnchor="middle"
                      fontSize="11"
                      fill="white"
                      fontWeight="600"
                    >
                      {d.year}
                    </text>
                    <text
                      x={xScale(d.year)}
                      y={yScale(d.satellite_count) - 17}
                      textAnchor="middle"
                      fontSize="11"
                      fill="white"
                    >
                      {d.satellite_count.toLocaleString()} sats
                    </text>
                  </g>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      <div className="timeline-stats">
        <div className="stat-card">
          <div className="stat-label">Peak Year</div>
          <div className="stat-value">
            {data.reduce((max, d) => d.satellite_count > max.satellite_count ? d : max, data[0])?.year}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Peak Launches</div>
          <div className="stat-value">
            {Math.max(...data.map(d => d.satellite_count)).toLocaleString()}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Years Tracked</div>
          <div className="stat-value">{data.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg per Year</div>
          <div className="stat-value">
            {Math.round(data.reduce((sum, d) => sum + d.satellite_count, 0) / data.length).toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  )
}

export default TimelineChart
