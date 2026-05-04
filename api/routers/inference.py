"""
ML inference endpoints for provenance attribution.

NOTE: These endpoints are stubs. Full implementation deferred to a follow-on PR.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/v2/inference", tags=["inference"])


class AttributeFragmentationRequest(BaseModel):
    object_key: str
    candidate_event_key: Optional[str] = None
    force: bool = False


@router.post("/attribute-fragmentation")
def attribute_fragmentation(body: AttributeFragmentationRequest):
    """
    Trigger ML inference to attribute a fragment to a fragmentation event.

    NOT YET IMPLEMENTED — returns 501.
    Pending attributions (no explicit DISCOS event) omit the fragmented_from edge;
    this endpoint will create that edge when a candidate event is identified by ML inference.
    """
    raise HTTPException(
        status_code=501,
        detail="ML-based fragmentation attribution is not yet implemented. "
               "Pending attributions are tracked via metadata.attribution_status on the object document.",
    )
