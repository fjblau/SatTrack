import { useState, useEffect, useRef } from 'react'
import './TimelineChart.css'

function TimelineChart({ selectedTimePeriod }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [hoveredYear, setHoveredYear] = useState(null)
  const [breakdown, setBreakdown] = useState(null)
  const [loadingBreakdown, setLoadingBreakdown] = useState(false)
  const [viewMode, setViewMode] = useState('years')
  const [selectedYear, setSelectedYear] = useState(null)
  const [monthlyData, setMonthlyData] = useState([])
  const [monthlyBreakdown, setMonthlyBreakdown] = useState(null)
  const svgRef = useRef(null)
  
  const [filterCountry, setFilterCountry] = useState('')
  const [filterOrbitalBand, setFilterOrbitalBand] = useState('')
  const [availableCountries, setAvailableCountries] = useState([])
  const [availableOrbitalBands, setAvailableOrbitalBands] = useState([])

  useEffect(() => {
    loadTimelineData()
    loadFilterOptions()
  }, [])

  useEffect(() => {
    if (viewMode === 'months' && selectedYear) {
      loadMonthlyData(selectedYear)
    } else {
      loadTimelineData()
    }
    if (selectedTimePeriod) {
      loadBreakdown(selectedTimePeriod)
    }
  }, [filterCountry, filterOrbitalBand])

  useEffect(() => {
    if (selectedTimePeriod) {
      loadBreakdown(selectedTimePeriod)
    }
  }, [selectedTimePeriod])

  const loadFilterOptions = async () => {
    try {
      const response = await fetch('/v2/graphs/timeline/filter-options')
      const result = await response.json()
      
      if (result.data) {
        setAvailableCountries(result.data.countries || [])
        setAvailableOrbitalBands(result.data.orbital_bands || [])
      }
    } catch (error) {
      console.error('Error loading filter options:', error)
    }
  }

  const loadTimelineData = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterCountry) params.append('country', filterCountry)
      if (filterOrbitalBand) params.append('orbital_band', filterOrbitalBand)
      
      const url = params.toString() 
        ? `/v2/graphs/timeline/yearly?${params.toString()}`
        : '/v2/graphs/stats'
      
      console.log('Loading timeline data from:', url)
      
      const response = await fetch(url)
      const result = await response.json()
      
      if (result.data && result.data.recent_launch_years) {
        const allYears = result.data.recent_launch_years
        console.log(`Loaded ${allYears.length} years of data`)
        setData(allYears.sort((a, b) => a.year - b.year))
      } else {
        console.log('No data received')
        setData([])
      }
    } catch (error) {
      console.error('Error loading timeline data:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadBreakdown = async (year) => {
    setLoadingBreakdown(true)
    try {
      const params = new URLSearchParams()
      if (filterCountry) params.append('country', filterCountry)
      if (filterOrbitalBand) params.append('orbital_band', filterOrbitalBand)
      
      const url = params.toString()
        ? `/v2/graphs/launch-timeline/breakdown/${year}?${params.toString()}`
        : `/v2/graphs/launch-timeline/breakdown/${year}`
      
      const response = await fetch(url)
      const result = await response.json()
      
      if (result.data) {
        setBreakdown(result.data)
      }
    } catch (error) {
      console.error('Error loading breakdown data:', error)
    } finally {
      setLoadingBreakdown(false)
    }
  }

  const loadMonthlyData = async (year) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterCountry) params.append('country', filterCountry)
      if (filterOrbitalBand) params.append('orbital_band', filterOrbitalBand)
      
      const url = params.toString()
        ? `/v2/graphs/launch-timeline/monthly/${year}?${params.toString()}`
        : `/v2/graphs/launch-timeline/monthly/${year}`
      
      const response = await fetch(url)
      const result = await response.json()
      
      if (result.data && result.data.monthly_data) {
        setMonthlyData(result.data.monthly_data)
        setSelectedYear(year)
        setViewMode('months')
      }
    } catch (error) {
      console.error('Error loading monthly data:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const loadMonthlyBreakdown = async (year, month) => {
    setLoadingBreakdown(true)
    try {
      const params = new URLSearchParams()
      if (filterCountry) params.append('country', filterCountry)
      if (filterOrbitalBand) params.append('orbital_band', filterOrbitalBand)
      
      const url = params.toString()
        ? `/v2/graphs/launch-timeline/breakdown/monthly/${year}/${month}?${params.toString()}`
        : `/v2/graphs/launch-timeline/breakdown/monthly/${year}/${month}`
      
      const response = await fetch(url)
      const result = await response.json()
      
      if (result.data) {
        setMonthlyBreakdown(result.data)
      }
    } catch (error) {
      console.error('Error loading monthly breakdown data:', error)
    } finally {
      setLoadingBreakdown(false)
    }
  }

  const handleYearClick = (year) => {
    loadMonthlyData(year)
  }
  
  const handleMonthClick = (month) => {
    if (selectedYear) {
      loadMonthlyBreakdown(selectedYear, month)
    }
  }

  const handleBackToYears = () => {
    setViewMode('years')
    setSelectedYear(null)
    setMonthlyData([])
    setMonthlyBreakdown(null)
  }

  if (loading) {
    return <div className="timeline-loading">Loading timeline data...</div>
  }

  if (data.length === 0 && viewMode === 'years') {
    return <div className="timeline-empty">No timeline data available</div>
  }

  const width = 1400
  const height = 500
  const padding = { top: 40, right: 40, bottom: 60, left: 80 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const displayData = viewMode === 'months' ? monthlyData : data
  const maxCount = Math.max(...displayData.map(d => d.satellite_count))
  const minValue = viewMode === 'months' ? 1 : Math.min(...data.map(d => d.year))
  const maxValue = viewMode === 'months' ? 12 : Math.max(...data.map(d => d.year))

  const xScale = (value) => {
    return padding.left + ((value - minValue) / (maxValue - minValue)) * chartWidth
  }

  const yScale = (count) => {
    return padding.top + chartHeight - (count / maxCount) * chartHeight
  }

  const pathData = displayData.map((d, i) => {
    const xValue = viewMode === 'months' ? d.month : d.year
    const x = xScale(xValue)
    const y = yScale(d.satellite_count)
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
  }).join(' ')

  const areaData = `M ${xScale(minValue)} ${padding.top + chartHeight} ${pathData} L ${xScale(maxValue)} ${padding.top + chartHeight} Z`

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  const yTicks = 5
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) => 
    Math.round((maxCount / yTicks) * i)
  )

  return (
    <div className="timeline-chart-container">
      <div className="timeline-header">
        <h3>
          {viewMode === 'months' ? `Satellite Launches in ${selectedYear}` : 'Satellite Launches Over Time'}
          {viewMode === 'months' && (
            <button className="back-button" onClick={handleBackToYears}>
              ← Back to Years
            </button>
          )}
        </h3>
        <p className="timeline-subtitle">
          {viewMode === 'months' 
            ? `${monthlyData.reduce((sum, d) => sum + d.satellite_count, 0).toLocaleString()} satellites launched in ${selectedYear}`
            : `Total satellites tracked: ${data.reduce((sum, d) => sum + d.satellite_count, 0).toLocaleString()}`
          }
          {(filterCountry || filterOrbitalBand) && (
            <span className="active-filters">
              {' • Filtered by: '}
              {filterCountry && <span className="filter-tag">{filterCountry}</span>}
              {filterCountry && filterOrbitalBand && ' + '}
              {filterOrbitalBand && <span className="filter-tag">{filterOrbitalBand}</span>}
            </span>
          )}
        </p>
      </div>
      
      <div className="timeline-filters">
        <div className="filter-group">
          <label htmlFor="country-filter">Country:</label>
          <select 
            id="country-filter"
            value={filterCountry} 
            onChange={(e) => setFilterCountry(e.target.value)}
            className="filter-select"
          >
            <option value="">All Countries</option>
            {availableCountries.map(country => (
              <option key={country} value={country}>{country}</option>
            ))}
          </select>
        </div>
        
        <div className="filter-group">
          <label htmlFor="orbital-band-filter">Orbital Band:</label>
          <select 
            id="orbital-band-filter"
            value={filterOrbitalBand} 
            onChange={(e) => setFilterOrbitalBand(e.target.value)}
            className="filter-select"
          >
            <option value="">All Orbital Bands</option>
            {availableOrbitalBands.map(band => (
              <option key={band} value={band}>{band}</option>
            ))}
          </select>
        </div>
        
        {(filterCountry || filterOrbitalBand) && (
          <button 
            className="clear-filters-button" 
            onClick={() => {
              setFilterCountry('')
              setFilterOrbitalBand('')
            }}
          >
            Clear Filters
          </button>
        )}
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
          {displayData.map(d => {
            const xValue = viewMode === 'months' ? d.month : d.year
            const label = viewMode === 'months' ? monthNames[d.month - 1] : d.year
            return (
              <g key={xValue}>
                <line
                  x1={xScale(xValue)}
                  y1={padding.top + chartHeight}
                  x2={xScale(xValue)}
                  y2={padding.top + chartHeight + 5}
                  stroke="#333"
                  strokeWidth="2"
                />
                <text
                  x={xScale(xValue)}
                  y={padding.top + chartHeight + 20}
                  textAnchor="middle"
                  fontSize="12"
                  fill="#666"
                >
                  {label}
                </text>
              </g>
            )
          })}
          <text
            x={padding.left + chartWidth / 2}
            y={height - 10}
            textAnchor="middle"
            fontSize="13"
            fill="#333"
            fontWeight="600"
          >
            {viewMode === 'months' ? 'Launch Month' : 'Launch Year'}
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
          {displayData.map(d => {
            const xValue = viewMode === 'months' ? d.month : d.year
            const label = viewMode === 'months' ? monthNames[d.month - 1] : d.year
            const isSelected = viewMode === 'years' && selectedTimePeriod === d.year?.toString()
            const isHovered = hoveredYear === xValue
            return (
              <g key={xValue}>
                <circle
                  cx={xScale(xValue)}
                  cy={yScale(d.satellite_count)}
                  r={isSelected || isHovered ? 6 : 4}
                  fill={isSelected ? "#e74c3c" : "#3498db"}
                  stroke="white"
                  strokeWidth="2"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredYear(xValue)}
                  onMouseLeave={() => setHoveredYear(null)}
                  onClick={() => viewMode === 'years' ? handleYearClick(d.year) : handleMonthClick(d.month)}
                />
                {(isHovered || isSelected) && (
                  <g>
                    <rect
                      x={xScale(xValue) - 50}
                      y={yScale(d.satellite_count) - 40}
                      width="100"
                      height="30"
                      fill="rgba(0, 0, 0, 0.8)"
                      rx="4"
                    />
                    <text
                      x={xScale(xValue)}
                      y={yScale(d.satellite_count) - 30}
                      textAnchor="middle"
                      fontSize="11"
                      fill="white"
                      fontWeight="600"
                    >
                      {label}
                    </text>
                    <text
                      x={xScale(xValue)}
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
        {viewMode === 'years' ? (
          <>
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
          </>
        ) : (
          <>
            <div className="stat-card">
              <div className="stat-label">Peak Month</div>
              <div className="stat-value">
                {monthNames[monthlyData.reduce((max, d) => d.satellite_count > max.satellite_count ? d : max, monthlyData[0])?.month - 1]}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Peak Launches</div>
              <div className="stat-value">
                {Math.max(...monthlyData.map(d => d.satellite_count)).toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Year</div>
              <div className="stat-value">
                {monthlyData.reduce((sum, d) => sum + d.satellite_count, 0).toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Avg per Month</div>
              <div className="stat-value">
                {Math.round(monthlyData.reduce((sum, d) => sum + d.satellite_count, 0) / monthlyData.length).toLocaleString()}
              </div>
            </div>
          </>
        )}
      </div>

      {breakdown && viewMode === 'years' && (
        <div className="timeline-breakdown">
          <h4>Launch Breakdown for {breakdown.year}</h4>
          <div className="breakdown-sections">
            <div className="breakdown-section">
              <h5>Orbital Bands</h5>
              {loadingBreakdown ? (
                <p className="breakdown-loading">Loading...</p>
              ) : (
                <div className="breakdown-items">
                  {breakdown.by_orbital_band.filter(b => b.orbital_band).map((band, idx) => (
                    <div key={idx} className="breakdown-item">
                      <span className="breakdown-name">{band.orbital_band}</span>
                      <div className="breakdown-bar-container">
                        <div 
                          className="breakdown-bar" 
                          style={{ width: `${(band.count / breakdown.total_satellites) * 100}%` }}
                        />
                      </div>
                      <span className="breakdown-count">{band.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="breakdown-section">
              <h5>Top Countries</h5>
              {loadingBreakdown ? (
                <p className="breakdown-loading">Loading...</p>
              ) : (
                <div className="breakdown-items">
                  {breakdown.by_country.slice(0, 5).map((country, idx) => (
                    <div key={idx} className="breakdown-item">
                      <span className="breakdown-name">{country.country}</span>
                      <div className="breakdown-bar-container">
                        <div 
                          className="breakdown-bar breakdown-bar-country" 
                          style={{ width: `${(country.count / breakdown.total_satellites) * 100}%` }}
                        />
                      </div>
                      <span className="breakdown-count">{country.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {breakdown.by_constellation.length > 0 && (
              <div className="breakdown-section">
                <h5>Top Constellations</h5>
                {loadingBreakdown ? (
                  <p className="breakdown-loading">Loading...</p>
                ) : (
                  <div className="breakdown-items">
                    {breakdown.by_constellation.slice(0, 5).map((constellation, idx) => (
                      <div key={idx} className="breakdown-item">
                        <span className="breakdown-name">{constellation.constellation}</span>
                        <div className="breakdown-bar-container">
                          <div 
                            className="breakdown-bar breakdown-bar-constellation" 
                            style={{ width: `${(constellation.count / breakdown.total_satellites) * 100}%` }}
                          />
                        </div>
                        <span className="breakdown-count">{constellation.count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      
      {monthlyBreakdown && viewMode === 'months' && (
        <div className="timeline-breakdown">
          <h4>Launch Breakdown for {monthNames[monthlyBreakdown.month - 1]} {monthlyBreakdown.year}</h4>
          <div className="breakdown-sections">
            <div className="breakdown-section">
              <h5>Orbital Bands</h5>
              {loadingBreakdown ? (
                <p className="breakdown-loading">Loading...</p>
              ) : (
                <div className="breakdown-items">
                  {monthlyBreakdown.by_orbital_band.filter(b => b.orbital_band).map((band, idx) => (
                    <div key={idx} className="breakdown-item">
                      <span className="breakdown-name">{band.orbital_band}</span>
                      <div className="breakdown-bar-container">
                        <div 
                          className="breakdown-bar" 
                          style={{ width: `${(band.count / monthlyBreakdown.total_satellites) * 100}%` }}
                        />
                      </div>
                      <span className="breakdown-count">{band.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="breakdown-section">
              <h5>Top Countries</h5>
              {loadingBreakdown ? (
                <p className="breakdown-loading">Loading...</p>
              ) : (
                <div className="breakdown-items">
                  {monthlyBreakdown.by_country.slice(0, 5).map((country, idx) => (
                    <div key={idx} className="breakdown-item">
                      <span className="breakdown-name">{country.country}</span>
                      <div className="breakdown-bar-container">
                        <div 
                          className="breakdown-bar breakdown-bar-country" 
                          style={{ width: `${(country.count / monthlyBreakdown.total_satellites) * 100}%` }}
                        />
                      </div>
                      <span className="breakdown-count">{country.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {monthlyBreakdown.by_constellation && monthlyBreakdown.by_constellation.length > 0 && (
              <div className="breakdown-section">
                <h5>Top Constellations</h5>
                {loadingBreakdown ? (
                  <p className="breakdown-loading">Loading...</p>
                ) : (
                  <div className="breakdown-items">
                    {monthlyBreakdown.by_constellation.slice(0, 5).map((constellation, idx) => (
                      <div key={idx} className="breakdown-item">
                        <span className="breakdown-name">{constellation.constellation}</span>
                        <div className="breakdown-bar-container">
                          <div 
                            className="breakdown-bar breakdown-bar-constellation" 
                            style={{ width: `${(constellation.count / monthlyBreakdown.total_satellites) * 100}%` }}
                          />
                        </div>
                        <span className="breakdown-count">{constellation.count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default TimelineChart
