from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from routes import routers
from dotenv import load_dotenv
import os
import sqlite3
from pathlib import Path
import pprint

# Načtení proměnných z .env
# Load environment variables from .env file
load_dotenv()

# Vytvoření aplikace
# Create the FastAPI application
app = FastAPI()

# Cesta k databázovému souboru
DB_PATH = Path(__file__).parent / "test.db"

# Připojení k SQLite
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row  # Umožní přístup k sloupcům podle názvu
cur = conn.cursor()

with open("init.sql", "r", encoding="utf-8") as f:
    sql_script = f.read()
cur.executescript(sql_script)
conn.commit()

# Načtení stylů a templates
# Load styles and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Přidání routerů
# Add routers
for prefix, router in routers:
    app.include_router(router, prefix=f"/{prefix}", tags=[prefix])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Zobrazí domovskou obrazovku.

    English:
    Displays the home screen.
    """

    return templates.TemplateResponse("login.html", {"request": request})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Zpracovává HTTP výjimky.
    Jakmile dojde k HTTP výjimce (exception), zavolá se tato funkce.

    English:
    Handles HTTP exceptions.
    Once an HTTP exception occurs, this function is called.
    """

    if exc.status_code == 401:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "status_message": exc.detail
        }, status_code=401)
    return HTMLResponse(str(exc.detail), status_code=exc.status_code)
