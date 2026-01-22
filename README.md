# WatchdogGov

A civic transparency tool that helps citizens track US Congressional representatives' activities, voting records, and campaign finances.

## Features

- **Legislator Search** - Find representatives by name or state with fuzzy matching
- **Voting Records** - View how legislators voted on bills
- **Bill Tracking** - See legislation sponsored and co-sponsored
- **Campaign Finance** - Access FEC data on contributions and expenditures
- **News Integration** - Related news articles about legislators
- **AI Chat Assistant** - Ask questions about congressional data using natural language

## Tech Stack

- **Backend**: Python 3.12+ with FastAPI
- **Database**: SQLite with SQLAlchemy async
- **Frontend**: HTMX + Jinja2 templates with Tailwind CSS
- **AI**: Anthropic Claude with tool-use

## Data Sources

| API | Purpose |
|-----|---------|
| [Congress.gov API](https://api.congress.gov/) | Members, bills, votes |
| [OpenFEC API](https://api.open.fec.gov/) | Campaign finance, expenditures |
| [NewsAPI](https://newsapi.org/) | News articles |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/watchdog-gov.git
   cd watchdog-gov
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and add your API keys:
   - `CONGRESS_API_KEY` - Get from [api.data.gov](https://api.data.gov/signup/)
   - `FEC_API_KEY` - Get from [api.data.gov](https://api.data.gov/signup/) (or use `DEMO_KEY`)
   - `NEWS_API_KEY` - Get from [newsapi.org](https://newsapi.org/register)
   - `ANTHROPIC_API_KEY` - Get from [Anthropic Console](https://console.anthropic.com/)

5. Run the development server:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

6. Open http://localhost:8000 in your browser.

## Project Structure

```
watchdog-gov/
├── app/
│   ├── main.py           # FastAPI application entry
│   ├── config.py         # Configuration settings
│   ├── database.py       # SQLAlchemy setup
│   ├── models/           # Database models
│   ├── routers/          # API route handlers
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # External API clients
│   └── templates/        # Jinja2 HTML templates
├── tests/                # Test files
├── .env.example          # Environment template
├── pyproject.toml        # Project dependencies
└── uv.lock               # Locked dependencies
```

## Development

### Running Tests

```bash
uv run pytest
```

### Running a Single Test File

```bash
uv run pytest tests/test_specific.py -v
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Homepage with search |
| `GET /search` | Search results |
| `GET /legislators/{id}` | Legislator profile |
| `GET /legislators/{id}/bills` | Bills tab (HTMX) |
| `GET /legislators/{id}/votes` | Votes tab (HTMX) |
| `GET /legislators/{id}/news` | News tab (HTMX) |
| `GET /legislators/{id}/finance` | Finance summary |
| `GET /chat` | AI chat interface |
| `POST /chat/message` | Send chat message |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
