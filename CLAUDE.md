# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WatchdogGov is a civic transparency tool that helps citizens track US Congressional representatives' activities, voting records, and campaign finances. It aggregates data from Congress.gov, OpenFEC, and NewsAPI, with an AI-powered chat interface for asking questions about legislators.

## Commands

```bash
# Install dependencies
uv sync

# Run the development server
uv run uvicorn app.main:app --reload

# Run tests (pytest)
uv run pytest

# Run a single test file
uv run pytest tests/test_specific.py -v
```

## Environment Setup

Copy `.env.example` to `.env` and configure API keys:
- `CONGRESS_API_KEY` - From api.data.gov
- `FEC_API_KEY` - From api.data.gov (or use DEMO_KEY)
- `NEWS_API_KEY` - From newsapi.org
- `ANTHROPIC_API_KEY` - For AI chat functionality

## Architecture

### Tech Stack
- **Backend**: FastAPI with async/await throughout
- **Database**: SQLite with SQLAlchemy async (aiosqlite) - designed for easy PostgreSQL migration
- **Frontend**: HTMX + Jinja2 templates with Tailwind CSS (CDN)
- **AI**: Anthropic Claude with tool-use for data retrieval
- **Offline**: PWA with service worker, caches user's favorited legislators

### Key Patterns

**API Client Pattern**: Each external API has a dedicated client in `app/services/` that:
- Wraps httpx for async HTTP calls
- Implements variable TTL caching backed by SQLite (news: 1hr, votes: 24hr, finance: weekly)
- Converts between API responses and ORM models
- Shows cached data with "may be outdated" warning on API failures

**Database Models**: All models inherit from `app.database.Base` and are re-exported from `app/models/__init__.py`. Key models:
- `Legislator` - Congress members (keyed by bioguide_id)
- `Bill`, `Vote`, `VotePosition` - Legislative activity
- `CampaignFinance`, `Expenditure` - FEC financial data
- `NewsArticle` - Cached news articles
- `Conversation`, `Message` - AI chat history

**AI Agent** (`app/services/ai_agent.py`): Uses Claude tool-use to let the assistant call data retrieval functions (search_legislators, get_legislator_bills, get_campaign_finance, etc.) and answer questions about congressional data.

### Data Flow
1. User interacts via HTMX-powered frontend
2. FastAPI routes in `app/routers/` handle requests
3. Service clients fetch from external APIs or return cached data
4. Results are rendered via Jinja2 templates (in `app/templates/`)

### External APIs
- **Congress.gov API** (`congress_client`): Members, bills, votes
- **OpenFEC API** (`fec_client`): Campaign finance, expenditures
- **NewsAPI** (`news_client`): News articles about legislators (500 req/day limit - use lazy loading + aggressive caching)

## Implementation Guidelines

### UI/UX Patterns
- **Visual Style**: Modern civic tech with blue/teal accent colors, sans-serif fonts, approachable feel
- **Loading**: Progressive reveal - show each section as it loads independently
- **Profile Layout**: Tabbed interface for bills, votes, news, finance
- **Chat**: Floating button in corner that opens modal (not dedicated page only)
- **Empty States**: Show message explaining why empty + suggest related actions
- **Refresh**: Per-section refresh buttons to invalidate cache for that data type
- **Search**: Server-side fuzzy matching with autocomplete suggestions
- **Desktop Only**: Mobile responsiveness is not a priority for MVP

### Rate Limiting
- Implement full rate limiting on all endpoints with proper headers
- NewsAPI: Combine lazy loading (fetch only when tab clicked) + request pooling

### Data Loading
- Smart prefetch: Load basic legislator info + prefetch likely next actions
- Expenditures: Keep button-to-request pattern (user clicks to load detailed FEC data)

### AI Agent Behavior
- Hybrid approach: Data-first using tools, but can acknowledge general civic questions
- Chat history: Let user choose to save or clear conversation history
- Political sensitivity: Trust Claude's default behavior

### Content Organization
- Former members: Display in separate historical section (not mixed with current)
- Priority: Core data accuracy above all other features

### Infrastructure
- Full analytics tracking for feature decisions
- Full unit test coverage for all services, models, and utilities
- Deployment: Local/self-hosted
