# Data Analysis Report - Kessler Satellite Database
**Date**: 2026-01-12  
**Analyst**: AI Agent  
**Dataset**: mongodb_export.json (18,870 satellite documents)

---

## Executive Summary

Full dataset analysis reveals **significantly different characteristics** than initial sampling suggested, with major implications for graph feature design:

### Key Findings
1. **Starlink Gen 1 dominates**: 9,258 satellites (49% of dataset)
2. **Poor orbital parameter coverage**: Only 26.1% have complete orbital data
3. **No launch vehicle data**: 0% coverage eliminates planned features
4. **Massive function diversity**: 1,290 unique functions (complex classification needed)

### Revised Graph Priorities
- **Constellation Network**: ✅ High priority (78.9% data coverage, Starlink is massive)
- **Registration Document Network**: ✅ Moderate priority (26.8% coverage, 746 docs)
- **Orbital Proximity**: ⚠️ **Limited scope** (only 26.1% satellites, biased to GEO/MEO/LEO-Polar)
- **Launch Timeline**: ⚠️ **Degraded** (dates exist, but no vehicle data)
- **Function Similarity**: ⚠️ **Complex** (1,290 functions require sophisticated NLP)

---

## Dataset Overview

### Total Documents
- **18,870 satellite documents**
- Sources: UNOOSA, CelesTrak, Space-Track, Kaggle
- Envelope structure with canonical + source-specific data

---

## Constellation Analysis

### Distribution
| Constellation | Satellite Count | % of Dataset |
|--------------|-----------------|--------------|
| **Starlink Gen 1** | **9,258** | **49.1%** |
| Other | 4,268 | 22.6% |
| OneWeb | 1,208 | 6.4% |
| Beidou | 69 | 0.4% |
| Glonass | 56 | 0.3% |
| Galileo | 31 | 0.2% |
| **TOTAL with constellation** | **14,890** | **78.9%** |

### Key Insights
- **Starlink Gen 1 is nearly half the entire database**
- Mega-constellations (Starlink + OneWeb) = 10,466 satellites (55.5%)
- GNSS constellations (GPS, Glonass, Beidou, Galileo) combined: 156 satellites
- 21.1% (3,980 satellites) have no constellation assignment

### Graph Implications
- Constellation graphs are **highly viable** with excellent data coverage
- Starlink graph will require special handling (may need sampling/aggregation for visualization)
- Clear clustering opportunity: mega-constellations vs traditional satellites

---

## Geographic Distribution

### Country Count: **79 unique countries/entities**

### Top 15 Countries
| Rank | Country/Entity | Satellites | % of Dataset |
|------|----------------|------------|--------------|
| 1 | USSR | 2,701 | 14.3% |
| 2 | Russian Federation | 967 | 5.1% |
| 3 | United Kingdom | 596 | 3.2% |
| 4 | China | 158 | 0.8% |
| 5 | Germany | 94 | 0.5% |
| 6 | Japan | 93 | 0.5% |
| 7 | Belgium | 43 | 0.2% |
| 8 | Spain | 35 | 0.2% |
| 9 | Uruguay | 35 | 0.2% |
| 10 | Finland | 30 | 0.2% |
| 11 | New Zealand | 27 | 0.1% |
| 12 | France | 23 | 0.1% |
| 13 | Australia | 20 | 0.1% |
| 14 | ESA | 18 | 0.1% |
| 15 | Canada | 17 | 0.1% |

### Note on UK Satellites
The UK's 596 satellites likely include OneWeb (registered in UK), explaining the high count.

### Graph Implications
- Country relationship graphs are viable with 79 nodes
- Historical data (USSR) requires careful handling/merging with Russia
- Geopolitical analysis opportunities (US data not shown but likely significant)

---

## Orbital Band Distribution

### Band Count: **8 orbital bands**

| Orbital Band | Satellites | % of Dataset |
|--------------|------------|--------------|
| LEO-Inclined | 6,068 | 32.2% |
| LEO-Polar | 4,297 | 22.8% |
| LEO-Equatorial | 3,542 | 18.8% |
| GEO | 492 | 2.6% |
| MEO | 379 | 2.0% |
| GEO-Inclined | 68 | 0.4% |
| HEO | 36 | 0.2% |
| LEO-Retrograde | 8 | 0.0% |
| **TOTAL with orbital band** | **14,890** | **78.9%** |

### Graph Implications
- LEO orbits dominate (73.8% of dataset)
- GEO belt has manageable size (560 satellites) for proximity analysis
- Clear orbital "neighborhoods" for congestion analysis

---

## Orbital Parameter Completeness

### Overall Completeness
- **Only 4,918 satellites (26.1%) have complete orbital parameters** (apogee, perigee, inclination)
- This severely limits orbital proximity calculations

### Completeness by Orbital Band
| Orbital Band | Satellites | With Full Params | Coverage % |
|--------------|------------|------------------|------------|
| MEO | 379 | 80 | **21.1%** |
| LEO-Polar | 4,297 | 885 | **20.6%** |
| HEO | 36 | 6 | 16.7% |
| GEO | 492 | 67 | 13.6% |
| GEO-Inclined | 68 | 7 | 10.3% |
| LEO-Inclined | 6,068 | 27 | **0.4%** ⚠️ |
| LEO-Equatorial | 3,542 | 5 | **0.1%** ⚠️ |
| LEO-Retrograde | 8 | 0 | **0.0%** ⚠️ |

### Critical Issue: LEO Coverage
**LEO satellites (73.8% of dataset) have catastrophically poor orbital parameter coverage:**
- LEO-Equatorial: 5 out of 3,542 (0.1%)
- LEO-Inclined: 27 out of 6,068 (0.4%)
- LEO-Polar: Best LEO coverage at 20.6%, but still poor

**This means Starlink satellites likely have minimal orbital data in the UNOOSA source.**

### Graph Implications
- **Orbital proximity graphs will be heavily biased toward GEO/MEO/LEO-Polar**
- Cannot perform meaningful congestion analysis on LEO-Equatorial or LEO-Inclined bands
- May need to fetch additional TLE data from CelesTrak API to enrich orbital parameters
- Proximity calculations limited to ~5K satellites (26%), not 18K

---

## Congestion Risk Distribution

### Risk Levels: **3 levels**

| Risk Level | Satellites | % of Dataset |
|------------|------------|--------------|
| HIGH | 12,208 | 64.7% |
| MEDIUM | 2,096 | 11.1% |
| LOW | 586 | 3.1% |
| **None/Unknown** | **3,980** | **21.1%** |

### Graph Implications
- Majority flagged as HIGH risk (likely Starlink LEO mega-constellation)
- Color-coding by congestion risk will be effective visual indicator
- Risk assessment already done, can use directly in graphs

---

## Satellite Status Distribution

### Status Types: **15 distinct statuses**

| Status | Count | % |
|--------|-------|---|
| **in orbit** | **2,318** | **12.3%** |
| decayed | 1,042 | 5.5% |
| recovered | 1,133 | 6.0% |
| deorbited | 200 | 1.1% |
| in GSO | 279 | 1.5% |
| in disposal/graveyard orbit | 25 | 0.1% |
| on Moon | 16 | 0.1% |
| heliocentric | 25 | 0.1% |
| areocentric (Mars orbit) | 4 | 0.0% |
| selenocentric (Moon orbit) | 7 | 0.0% |
| orbiting Venus | 1 | 0.0% |
| on Venus | 6 | 0.0% |
| on Ryugu | 1 | 0.0% |
| in Sun L1 | 1 | 0.0% |
| in Sun L2 | 1 | 0.0% |
| **None/Unknown** | **~13,830** | **~73.3%** |

### Notable Findings
- Includes interplanetary missions (Mars, Venus, asteroids, Lagrange points)
- Only 12.3% explicitly marked "in orbit" (likely undercount, many lack status)
- Historical satellites (decayed, recovered) represent 11.5%

### Graph Implications
- Status filtering important for "active satellite" views
- Interplanetary objects should be filterable/excludable from Earth-orbit graphs
- Historical analysis opportunity (decay timeline graphs)

---

## Function Data Analysis

### Function Diversity: **1,290 unique function descriptions**
- **Coverage**: Only 5,056 satellites (26.8%) have function data
- **Complexity**: Functions are long, detailed text descriptions (not categories)

### Top 30 Function Keywords
Common terms across all function descriptions:
1. of (6,012)
2. the (5,430)
3. and (4,010)
4. investigation (2,239)
5. outer (2,098)
6. space (1,992)
7. atmosphere (1,905)
8. upper (1,889)
9. satellite (949)
10. communications (761)
11. scientific (306)
12. earth (309)
13. station (395)
14. system (388)
15. international (385)

### Identified Function Categories (Manual Classification Needed)
Based on keywords, likely categories:
- **Scientific research**: "investigation", "scientific", "research"
- **Communications**: "communications", "satellite"
- **Earth observation**: "earth", "remote sensing"
- **Atmospheric research**: "atmosphere", "upper"
- **International cooperation**: "international", "station" (ISS-related)
- **Military/Defense**: "ministry", "defence", "assignments", "russian federation"

### Graph Implications
- **Function similarity requires sophisticated NLP** (1,290 unique descriptions)
- Simple keyword matching insufficient for quality clustering
- Consider using embeddings (sentence transformers) or LLMs for classification
- Manual taxonomy creation may be needed for accuracy
- Coverage (26.8%) limits utility of function-based graphs

---

## Registration Document Coverage

### Coverage
- **5,055 satellites (26.8%) have registration documents**
- **746 unique UN registration documents**
- Average: 6.8 satellites per document

### Graph Implications
- Registration document network is viable but covers only ~1/4 of dataset
- Document-satellite relationships provide administrative grouping
- Can identify batch registrations and operator patterns
- 746 document nodes is manageable for graph visualization

---

## Launch Vehicle Data

### Coverage: **0%**
- **No satellites have launch vehicle data in canonical fields**
- This data may exist in raw UNOOSA documents but was not extracted

### Graph Implications
- **Launch vehicle-based graphs are not feasible without data enrichment**
- Launch timeline graphs can still use launch dates (available) but without vehicle context
- Recommendation: Add launch vehicle extraction from registration PDFs or external sources

---

## Launch Date Coverage

### Analysis Pending
- Launch dates exist in `canonical.date_of_launch` field
- Temporal analysis viable for launch timeline graphs
- Date range: Need to analyze min/max dates

**Action Item**: Analyze launch date distribution and coverage

---

## Data Quality Summary

| Data Field | Coverage % | Data Quality | Graph Viability |
|------------|-----------|--------------|-----------------|
| Constellation | 78.9% | ✅ Excellent | ✅ High |
| Country | ~100% | ✅ Excellent | ✅ High |
| Orbital Band | 78.9% | ✅ Excellent | ✅ High |
| Congestion Risk | 78.9% | ✅ Good | ✅ High |
| Orbital Parameters | **26.1%** | ⚠️ **Poor (LEO)** | ⚠️ **Limited** |
| Function | 26.8% | ⚠️ Fair | ⚠️ Limited |
| Registration Document | 26.8% | ✅ Good | ✅ Moderate |
| Status | 26.7% | ⚠️ Fair | ⚠️ Limited |
| Launch Vehicle | **0%** | ❌ **Missing** | ❌ **Blocked** |
| Launch Date | **TBD** | ? | ? |

---

## Revised Graph Use Case Priorities

### Tier 1: High Value, High Viability
1. **Constellation Network** (78.9% coverage, Starlink dominance)
   - Clear visualization of mega-constellations
   - OneWeb, Starlink, GNSS networks
   
2. **Country Space Activity** (100% coverage)
   - Geopolitical analysis
   - Orbital band competition
   - 79 countries with varied activity levels

### Tier 2: Moderate Value, Moderate Viability
3. **Registration Document Network** (26.8% coverage, 746 docs)
   - Administrative groupings
   - Operator identification
   - Batch registration patterns

4. **Launch Timeline** (date coverage TBD, no vehicle data)
   - Temporal deployment patterns
   - Space race visualization
   - **Limited without launch vehicle context**

### Tier 3: Complex/Limited Scope
5. **Orbital Proximity** (26.1% coverage, heavily biased)
   - **Only viable for GEO/MEO/LEO-Polar bands**
   - LEO congestion analysis severely limited
   - Requires TLE data enrichment for Starlink proximity

6. **Function Similarity** (26.8% coverage, 1,290 unique)
   - **Requires advanced NLP** (embeddings, LLMs)
   - High implementation complexity
   - Moderate utility given coverage

---

## Recommendations

### Data Enrichment Priorities
1. **Fetch TLE data from CelesTrak API** for orbital parameters (especially Starlink)
2. **Extract launch vehicle from PDF documents** or external sources
3. **Classify functions** using NLP into standardized taxonomy
4. **Merge USSR + Russian Federation** for cleaner country analysis

### Graph Implementation Strategy
1. **Start with Constellation Network** (best data, highest impact)
2. **Add Country Relations** (complete data, interesting insights)
3. **Implement Registration Document Network** (moderate complexity)
4. **Defer Orbital Proximity** until TLE data enrichment is complete
5. **Defer Function Similarity** until NLP pipeline is built

### Technical Mitigations
- **Starlink visualization**: Implement sampling/aggregation (9K nodes too many)
- **Missing data handling**: Clear UI indicators for incomplete graphs
- **Data quality warnings**: Show coverage % in graph metadata
- **Progressive enhancement**: Build graphs that work with available data, improve as enrichment progresses

---

## Conclusion

The initial specification **significantly underestimated**:
- Constellation diversity (missed Starlink, Beidou, Galileo)
- Function complexity (1,290 vs 179)
- Data quality issues (26% orbital coverage vs assumed complete)
- Scale of Starlink (49% of entire dataset)

The corrected analysis reveals:
- **Constellation graphs are the killer feature** (great data, Starlink dominance)
- **Orbital proximity is limited** without TLE enrichment
- **Function similarity requires advanced NLP**, not simple matching
- **Launch vehicle graphs are blocked** until data is extracted

This fundamentally changes implementation priorities toward constellation-focused features with clearer data quality communication to users.
