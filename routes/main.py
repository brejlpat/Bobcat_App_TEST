from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import sqlite3
from pathlib import Path
from app_state import state
from opcua import Client
from routes.auth import get_current_user, User
import os
from pathlib import Path
from dotenv import load_dotenv

# Načtení .env souboru
# Load the .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Cesta k databázovému souboru
DB_PATH = Path(__file__).parent.parent / "test.db"

# Připojení k SQLite
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row  # Umožní přístup k sloupcům podle názvu
cur = conn.cursor()


@router.get("/home", response_class=HTMLResponse)
async def home(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí domovskou obrazovku.

    English:
    Displays the home screen.
    """
    state.title = "Home Page"
    line = request.query_params.get("line") or "❌"

    return templates.TemplateResponse("home.html", {
        "request": request,
        "title": state.title,
        "line": line,
        "username": user.username,
        "role": user.role
    })


@router.get("/plant_status", response_class=HTMLResponse)
async def plant_status(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí plán závodu a stav linek.

    English:
    Displays the plant layout and line status.
    """
    state.title = "Plant Status Overview"

    line_names = [
        "Blade_Mex", "Boom_Arm_Mex", "Cairo", "Frame_SSL", "Lift_Arm_SSL",
        "Mex", "SSL", "SSL_Transmission", "Under_Carriage_Sirius",
        "Undercarriage_Phoenix", "Upper_structure_Mex"
    ]

    tags_with_values = []
    try:
        opc_client = Client("opc.tcp://dbr-us-DFOPC.corp.doosan.com:49320")
        opc_client.set_security_string(
            "Basic256Sha256,SignAndEncrypt,"
            "certs_dbr/client_cert.der,"
            "certs_dbr/client_key.pem,"
            "certs_dbr/server_cert.der"
        )
        opc_client.application_uri = "urn:FreeOpcUa:python:client"
        opc_client.set_user(os.getenv("kepserver_user"))
        opc_client.set_password(os.getenv("kepserver_password"))
        opc_client.connect()
        status_message = "✅ Successfully connected to OPC UA server."

        for name in line_names:
            nodeid = f"ns=2;s=DBR_SITE_LINE_STATUS.Line_Status.line_status.{name}"
            try:
                node = opc_client.get_node(nodeid)
                value = node.get_value()
                tags_with_values.append({
                    "name": name,
                    "nodeid": nodeid,
                    "value": value
                })
            except Exception as e:
                tags_with_values.append({
                    "name": name,
                    "nodeid": nodeid,
                    "value": f"⚠️ Error: {e}"
                })

        opc_client.disconnect()

    except Exception as e:
        status_message = f"⚠️ Error connecting to OPC UA server: {e}"

    line = request.query_params.get("line") or "❌"

    return templates.TemplateResponse("plant_status.html", {
        "request": request,
        "title": state.title,
        "tags": tags_with_values,
        "line": line,
        "status_message": status_message,
        "username": user.username,
        "role": user.role
    })


@router.get("/line_detail", response_class=HTMLResponse)
async def line_detail(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí detailní pohled na linku.
    Uživatel má možnost procházet jednotlivé zařízení a jejich hodnoty.

    English:
    Displays a detailed view of the line.
    The user can browse through individual devices and their values.
    """
    state.title = "Line Detail"
    line = request.query_params.get("line") or "❌"

    return templates.TemplateResponse("plant_status_detail.html", {
        "request": request,
        "title": state.title,
        "line": line,
        "username": user.username,
        "role": user.role
    })
