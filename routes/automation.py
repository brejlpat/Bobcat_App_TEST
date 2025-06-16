from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app_state import state
from routes.auth import get_current_user, User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí dashboard pro oddělení Automatizace & Digitalizace.
    English:
    Displays the dashboard for the Automation & Digitalisation department.
    """

    line = request.query_params.get("line") or "❌"

    team_members = [
        {"name": "Cyrille Piteau", "position": "Automation & Digitalisation senior manager EMEA", "image": "user_icon.png"},
        {"name": "Bořek Miklas", "position": "ME Engineer - Smart Factory", "image": "user_icon.png"},
        #{"name": "Sivakumar Siva", "position": "Automation Control Engineer", "image": "user_icon.png"},
        {"name": "Zdeněk Křížek", "position": "Technologist", "image": "user_icon.png"},
        {"name": "Patrik Brejla", "position": "Trainee Automation", "image": "user_icon.png"},
    ]

    state.line = line
    return templates.TemplateResponse("automation.html", {
        "request": request,
        "team_members": team_members,
        "line": state.line,
        "username": user.username,
        "role": user.role
    })
