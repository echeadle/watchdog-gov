# Product Requirements Document - WatchdogGov

## Vision

A transparent tool for citizens to track their elected representatives' activities, voting records, and campaign finances.

## Target Users

- Engaged citizens
- Journalists
- Researchers
- Activists

## Core Problem

Congressional data is scattered across multiple government websites, making it difficult to get a complete picture of a representative's activities.

## MVP Scope

- Search and browse legislators
- View bills, votes, and news
- Access campaign finance data
- Ask questions via AI agent

## Success Metrics

- Users can find any legislator within 2 searches
- Profile page loads in < 3 seconds
- AI agent answers questions accurately

## Out of Scope for MVP

- User accounts and saved legislators
- Email notifications
- Historical data beyond current Congress
- Mobile native app

## Data Sources

| API | Purpose | Auth |
|-----|---------|------|
| Congress.gov API | Members, bills, votes | Free API key from api.data.gov |
| OpenFEC API | Campaign finance, expenditures | Free API key (or DEMO_KEY) |
| NewsAPI.org | News articles about legislators | Free tier (500 req/day) |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python FastAPI |
| Frontend | HTMX + Jinja2 |
| Database | SQLite + SQLAlchemy |
| Styling | Tailwind CSS (CDN) |
| AI Agent | Anthropic Claude API |
| Package Manager | uv |

## API Endpoints

```
GET  /                              # Homepage with search
GET  /search?q={name}&state={state} # Search results
GET  /legislators/{bioguide_id}     # Profile page

# HTMX partials
GET  /legislators/{id}/bills        # Bills tab content
GET  /legislators/{id}/votes        # Votes tab content
GET  /legislators/{id}/news         # News tab content
GET  /legislators/{id}/finance      # Finance summary

# Campaign finance
POST /legislators/{id}/expenditures/request  # Request details
GET  /legislators/{id}/expenditures          # View details

# AI Chat
GET  /chat                          # Chat page
POST /chat/message                  # Send message
```

---

## Technical Requirements

### Caching & Data
| Decision | Choice |
|----------|--------|
| Cache TTL | Variable by data type + per-section refresh buttons |
| API Failures | Show cached data with "may be outdated" warning |
| NewsAPI Rate Limits | Lazy loading + aggressive caching + request pooling |
| Data Loading | Smart prefetch (basic info + likely next actions) |
| Expenditures | Button to request (current pattern) |

### UI/UX
| Decision | Choice |
|----------|--------|
| Loading States | Progressive reveal |
| Profile Layout | Tabbed interface |
| Visual Style | Modern civic tech (blue/teal accent) |
| Chat Placement | Floating button with modal |
| Empty States | Message + suggest alternatives |
| Search | Fuzzy matching + autocomplete (server-side) |
| Mobile | Desktop only for MVP |
| Accessibility | Minimal (obvious issues) |

### AI Agent
| Decision | Choice |
|----------|--------|
| Boundaries | Hybrid (data-first, acknowledge general civic Qs) |
| Chat History | User choice to save or clear |
| Political Sensitivity | Trust Claude's default behavior |

### Infrastructure
| Decision | Choice |
|----------|--------|
| Deployment | Local/self-hosted |
| Rate Limiting | Full rate limiting on all endpoints |
| Database | SQLite now, design for PostgreSQL migration |
| Offline/PWA | Full PWA, cache user's favorites/bookmarks |
| Analytics | Full analytics for feature decisions |
| Testing | Full unit tests |

### Content
| Decision | Choice |
|----------|--------|
| Former Members | Separate historical section |
| Top Priority | Core data accuracy |
