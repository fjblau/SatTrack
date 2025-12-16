# Technical Specification: Show Data Record Button

## Task Complexity: Easy

## Overview
Add a "Show Data Record" button to the DetailPanel component that opens a modal window displaying the complete MongoDB document for the selected satellite.

## Technical Context

### Language & Framework
- **Frontend**: React 19.2.3 with Vite 7.2.7
- **Backend**: Python FastAPI with MongoDB (pymongo)
- **State Management**: React useState hooks
- **Styling**: CSS modules

### Current Architecture
- The application uses a MongoDB envelope structure for satellite data:
  - `identifier`: unique identifier
  - `canonical`: consolidated/merged data from sources
  - `sources`: source-specific data objects (unoosa, celestrak, spacetrack)
  - `metadata`: system metadata (timestamps, source priority)
- The API endpoint `/v2/satellite/{identifier}` already returns the full MongoDB document
- The `DetailPanel` component displays formatted data but doesn't show the raw document structure

## Implementation Approach

### 1. Create Modal Component
Create a new modal component `DataRecordModal.jsx` in `react-app/src/components/` that:
- Accepts a `data` prop with the MongoDB document
- Displays the JSON data in a readable, formatted way (syntax-highlighted if possible, or prettified JSON)
- Provides a close button
- Handles click-outside-to-close behavior
- Includes a copy-to-clipboard button for the JSON data

### 2. Modify DetailPanel Component
Update `DetailPanel.jsx` to:
- Add a "Show Data Record" button in the detail header area (below or next to the satellite name)
- Track modal visibility state with `useState`
- Store the full MongoDB document from the existing `/v2/satellite/{identifier}` API call
- Pass the document data to the modal when open

### 3. Backend Changes
**No backend changes required** - the existing `/v2/satellite/{identifier}` endpoint already returns the complete MongoDB document including:
- `identifier`
- `canonical` (all merged fields)
- `sources` (all source-specific data)
- `metadata` (timestamps and sources)

### 4. Styling
- Create `DataRecordModal.css` for modal styling
- Modal should:
  - Overlay the page with a semi-transparent background
  - Center the content box
  - Have a max-width and max-height with scrolling
  - Use a monospace font for the JSON display
  - Have clear visual hierarchy (header, content, actions)

## Source Code Changes

### Files to Create
1. `react-app/src/components/DataRecordModal.jsx` - New modal component
2. `react-app/src/components/DataRecordModal.css` - Modal styles

### Files to Modify
1. `react-app/src/components/DetailPanel.jsx` - Add button and integrate modal
2. `react-app/src/components/DetailPanel.css` - Styling for the new button

## Data Model / API / Interface Changes

**No changes required**. The existing data flow already provides all necessary information:
- The `DetailPanel` component already calls `/v2/satellite/{identifier}` to fetch orbital data
- The API response includes the full MongoDB document structure
- We'll reuse this data to display in the modal

## Verification Approach

### Manual Testing
1. Start the application with `./start.sh`
2. Navigate to the frontend at http://localhost:3000
3. Select a satellite row from the table
4. Verify the "Show Data Record" button appears in the detail panel
5. Click the button and verify:
   - Modal opens with formatted JSON
   - JSON contains all document fields (identifier, canonical, sources, metadata)
   - Close button works
   - Click outside modal closes it
   - Copy button copies JSON to clipboard
6. Test with multiple satellite records to ensure data updates correctly
7. Test responsive behavior at different screen sizes

### Code Quality
- Run `npm run lint` in the `react-app` directory (if lint script exists)
- Check browser console for React warnings or errors
- Verify no memory leaks (modal cleanup on unmount)

## Implementation Notes

### Component Structure
```jsx
// DataRecordModal.jsx
- Modal overlay (click to close)
- Modal content container
  - Header with title and close button
  - JSON display area (pre-formatted or syntax-highlighted)
  - Copy to clipboard button
```

### State Management in DetailPanel
```javascript
const [showDataRecord, setShowDataRecord] = useState(false)
const [fullDocument, setFullDocument] = useState(null)
```

### Button Placement
The button should be placed in the detail header section, either:
- Below the satellite name and registration number
- As a secondary action button in the header area
- Style it distinctly from external links (different color/style)

## Complexity Justification

**Easy complexity** because:
- No backend changes required - API already provides the data
- Simple React component with basic modal functionality
- Straightforward state management with useState
- No complex data transformations needed
- Clear UI pattern (button -> modal)
- Limited edge cases to handle
