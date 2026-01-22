"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.routers import chat, legislators
from app.middleware import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    await init_db()
    yield


app = FastAPI(
    title="WatchdogGov",
    description="Track US Congressional representatives, their bills, votes, and campaign finance",
    version="0.1.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="app/templates")

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

app.include_router(legislators.router)
app.include_router(chat.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Homepage with search form."""
    return templates.TemplateResponse("index.html", {"request": request})
