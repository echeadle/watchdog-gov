"""Routes for legislator search and profiles."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import congress_client

router = APIRouter(prefix="/legislators", tags=["legislators"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/autocomplete")
async def autocomplete_legislators(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=8, le=20, description="Max results"),
    db: AsyncSession = Depends(get_db),
):
    """Get autocomplete suggestions for legislator search.

    Returns HTML partial for HTMX requests, JSON for API calls.
    Uses cached data when available for speed, with fuzzy matching.
    """
    # First try cached legislators (faster, works offline)
    results = await congress_client.search_cached_members(db, q, limit=limit)

    # If no cached results, try API search
    if not results:
        results = await congress_client.search_members(db, q, limit=limit)

    # Format for autocomplete dropdown
    suggestions = []
    for member in results:
        # Handle both API format and cached format
        name = member.get("name") or member.get("directOrderName", "")
        bioguide_id = member.get("bioguideId", "")
        state = member.get("state", "")
        party = member.get("partyName") or member.get("party", "")
        chamber = member.get("chamber", "")

        # Format display name
        if "," in name:
            # Convert "Pelosi, Nancy" to "Nancy Pelosi"
            parts = name.split(", ")
            display_name = f"{parts[1]} {parts[0]}" if len(parts) > 1 else name
        else:
            display_name = name

        suggestions.append({
            "id": bioguide_id,
            "name": display_name,
            "state": state,
            "party": party,
            "chamber": chamber,
            "label": f"{display_name} ({party}-{state})" if party and state else display_name,
        })

    # Return HTML for HTMX requests, JSON for API calls
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/autocomplete_results.html",
            {"request": request, "suggestions": suggestions},
        )

    return JSONResponse(content={"suggestions": suggestions})


@router.get("/search")
async def search_legislators(
    q: str = Query(default=None, description="Search query"),
    state: str = Query(default=None, description="State filter (2-letter code)"),
    limit: int = Query(default=20, le=50, description="Max results"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Search for legislators by name or state.

    Uses fuzzy matching for typo tolerance and relevance ranking.
    """
    if not q and not state:
        return JSONResponse(
            content={"error": "Please provide a search query or state filter"},
            status_code=400,
        )

    results = await congress_client.search_members(
        db, query=q, state=state, limit=limit
    )

    # Format results
    legislators = []
    for member in results:
        name = member.get("name") or member.get("directOrderName", "")
        bioguide_id = member.get("bioguideId", "")

        # Convert "Last, First" to "First Last"
        if "," in name:
            parts = name.split(", ")
            display_name = f"{parts[1]} {parts[0]}" if len(parts) > 1 else name
        else:
            display_name = name

        legislators.append({
            "bioguide_id": bioguide_id,
            "name": display_name,
            "state": member.get("state", ""),
            "party": member.get("partyName", ""),
            "chamber": member.get("chamber", ""),
            "image_url": member.get("depiction", {}).get("imageUrl") if member.get("depiction") else None,
            "url": f"/legislators/{bioguide_id}",
        })

    return JSONResponse(content={
        "query": q,
        "state": state,
        "count": len(legislators),
        "legislators": legislators,
    })
