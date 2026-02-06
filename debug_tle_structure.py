import sys
sys.path.insert(0, '.')

from db import find_satellite
import json

# Check the actual structure
satellite = find_satellite(international_designator="2023-155H")
if satellite:
    print("Satellite structure:")
    print(json.dumps({
        "sources": satellite.get("sources"),
        "canonical": satellite.get("canonical"),
        "metadata": satellite.get("metadata")
    }, indent=2, default=str))
else:
    print("Satellite not found")
