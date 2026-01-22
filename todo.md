# WatchdogGov - Task Tracking

## Project Setup
- [x] Initialize Python project structure
- [x] Set up FastAPI application
- [x] Configure SQLite database with SQLAlchemy
- [x] Create .env.example with required variables

## Database Models
- [x] Create Legislator model
- [x] Create Bill model
- [x] Create Vote and VotePosition models
- [x] Create CampaignFinance and Expenditure models
- [x] Create Conversation and Message models for AI chat
- [x] Add Favorite model for user bookmarks (PWA offline support)
- [x] Add former member flag/status to Legislator model

## API Services
- [x] Implement Congress.gov API client
- [x] Implement OpenFEC API client
- [x] Implement NewsAPI client
- [x] Implement caching service with TTL
- [x] Update caching to variable TTLs (news: 1hr, votes: 24hr, finance: weekly)
- [x] Add "data may be outdated" warning when serving stale cache on API failure
- [ ] Implement request pooling for NewsAPI batch queries
- [ ] Add per-section cache invalidation (refresh buttons)

## Routes & Templates
- [x] Create base HTML template with Tailwind/HTMX
- [x] Build homepage with search form
- [x] Create search results page
- [x] Build legislator profile page
- [x] Implement bills tab (HTMX partial)
- [x] Implement votes tab (HTMX partial)
- [x] Implement news tab (HTMX partial)
- [x] Add campaign finance section with request button

## Search Enhancements
- [ ] Implement server-side fuzzy matching
- [ ] Add autocomplete suggestions endpoint
- [ ] Integrate autocomplete into search form

## UI/UX Improvements
- [ ] Apply blue/teal accent color scheme (modern civic tech style)
- [ ] Implement progressive reveal loading (show sections as they load)
- [ ] Add per-section refresh buttons to tabs
- [ ] Improve empty states with explanations + suggested actions
- [ ] Add loading indicators for each section

## AI Agent
- [x] Set up Claude client with tool-use
- [x] Define data retrieval tools
- [x] Build chat page interface
- [x] Implement conversation persistence
- [ ] Convert chat to floating button + modal (instead of dedicated page only)
- [ ] Add user option to save or clear conversation history
- [ ] Update AI to hybrid mode (data-first, acknowledge general civic questions)

## Rate Limiting
- [x] Implement rate limiting middleware
- [x] Add rate limit headers to all responses
- [x] Configure limits per endpoint

## PWA & Offline Support
- [ ] Create service worker
- [ ] Add web app manifest
- [ ] Implement favorites/bookmarks feature
- [ ] Cache favorited legislators for offline viewing
- [ ] Add install prompt for PWA

## Former Members Section
- [ ] Create separate route for historical/former legislators
- [ ] Add "former member" badge to profiles
- [ ] Exclude former members from main search (or flag clearly)

## Analytics
- [ ] Set up analytics tracking system
- [ ] Track page views and user flows
- [ ] Track feature usage (tabs, chat, search)
- [ ] Create analytics dashboard or export

## Testing
- [ ] Write unit tests for Congress.gov client
- [ ] Write unit tests for OpenFEC client
- [ ] Write unit tests for NewsAPI client
- [x] Write unit tests for caching service
- [~] Write unit tests for database models (Legislator, Favorite done)
- [ ] Write unit tests for AI agent tools
- [ ] Write integration tests for main routes

## Documentation & Deployment
- [ ] Write README documentation
- [ ] Create local deployment configuration
- [ ] Document PostgreSQL migration path
