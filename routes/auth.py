from fastapi import APIRouter, Request, Form, status, Depends, HTTPException, Cookie
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from datetime import datetime, timedelta
from fastapi.templating import Jinja2Templates
from ldap3 import Server, Connection, ALL, NTLM, Tls
import ssl
from email.message import EmailMessage
import smtplib
import psycopg2
from psycopg2.extras import DictCursor
import sqlite3
from pathlib import Path
import os
from pathlib import Path
from dotenv import load_dotenv

# Načtení .env souboru
# Load the .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Inicializace FastAPI routeru a šablon
# Initialization of FastAPI router and templates
router = APIRouter()
templates = Jinja2Templates(directory="templates")

"""
Struktura databází / Database structure
- users_ad      -> tabulka s uživately/table of users
    - id (auto)
    - username
    - email
    - role
    - registry_date (auto)
- login         -> tabulka se záznamy přihlášení/table of login records
    - id (auto)
    - username
    - token_expiration
    - login_date (auto)
- device_edit   -> tabulka se záznamy úprav zařízení/table of device edit records
    - id (auto)
    - username
    - project_id
    - payload (json)
    - device_edit_date (auto)
- embeddings   -> tabulka s embeddings pro AI model na vyhledávání zařízení/table of embeddings for AI model for search bar
    - id (auto)
    - channel
    - device
    - embedding (vector(384))
"""

# Cesta k databázovému souboru
DB_PATH = Path(__file__).parent.parent / "test.db"

# Připojení k SQLite
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row  # Umožní přístup k sloupcům podle názvu
cur = conn.cursor()

# LDAP parametry
# LDAP parameters
LDAP_SERVER = 'ldaps://corp.doosan.com'
BASE_DN = 'DC=corp,DC=doosan,DC=com'

# JWT konfigurace
# JWT configuration
SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Definice modelů pro uživatele a tokeny
# Definition of models for users and tokens
class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str
    role: str


class TokenData(BaseModel):
    username: str
    role: str


def authenticate_ldap_user(username: str, password: str):
    """
    Autentizuje uživatele pomocí LDAP serveru.
    Pokud je autentizace úspěšná, vrací dict s email a username.
    Pokud selže, vrací None.

    English:
    Authenticates the user using the LDAP server.
    If authentication is successful, returns a dict with email and username.
    If it fails, returns None.
    """
    try:
        tls_config = Tls(validate=ssl.CERT_NONE)

        server = Server(
            LDAP_SERVER,
            use_ssl=True,
            tls=tls_config,
            get_info=None,
            connect_timeout=3
        )

        conn_ldap = Connection(
            server,
            user=f"DSG\\{username}",
            password=password,
            authentication=NTLM,
            receive_timeout=3
        )

        if not conn_ldap.bind():
            return None

        conn_ldap.search(BASE_DN, f"(sAMAccountName={username})", attributes=["cn", "mail"])

        if not conn_ldap.entries:
            return None

        user = conn_ldap.entries[0]
        return {"email": user.mail.value, "username": user.cn.value}

    except Exception:
        return None


def get_user_from_db(email: str):
    """
    Získá uživatelská data z DB podle emailu.

    English:
    Retrieves user data from the database by email.
    """

    cur.execute("SELECT * FROM users_ad WHERE email = ?", (email,))
    return cur.fetchone()


def create_access_token(data: dict):
    global expire
    """
    Vytvoří JWT token, který expiruje po `timedelta`).
    Používá Unix timestamp v klíči `exp`.
    Kvůli časovému pásmu se přičítá 120 minut.
    Vrací token jako string.

    English:
    Creates a JWT token that expires after `timedelta`.
    Uses Unix timestamp in the `exp` key.
    Due to the timezone, 120 minutes are added.
    Returns the token as a string.
    """

    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=120) + timedelta(minutes=500)
    exp_timestamp = int(expire.timestamp())

    #print(f"Token expire datetime: {expire}")

    to_encode.update({"exp": exp_timestamp})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(access_token: str = Cookie(None)) -> User:
    """
    Získá aktuálního uživatele z JWT tokenu.
    Pokud token neexistuje nebo je neplatný, vyhodí HTTPException.
    Pokud je vše OK, vrátí username, role.

    English:
    Retrieves the current user from the JWT token.
    If the token does not exist or is invalid, raises HTTPException.
    If everything is OK, returns username and role.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated (no cookie)")

    try:
        token = access_token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        role: str = payload.get("role")

        if username is None or role is None:
            raise HTTPException(status_code=401, detail="Invalid token content")

        return User(username=username, role=role)

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Zobrazí přihlašovací stránku.

    English:
    Displays the login page.
    """
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """
    Zpracovává přihlašovací formulář.
    Ověřuje uživatelské jméno a heslo pomocí LDAP serveru.
    Pokud je uživatel úspěšně autentizován, zkontroluje se, zda je v DB.
    Pokud je uživatel v DB, vytvoří se JWT token a nastaví se cookie.
    Pokud uživatel není v DB, zobrazí se chybová hláška.
    Pokud uživatel není autentizován pomocí LDAP, zobrazí se chybová hláška.

    English:
    Processes the login form.
    Verifies the username and password using the LDAP server.
    If the user is successfully authenticated, checks if they are in the database.
    If the user is in the database, creates a JWT token and sets a cookie.
    If the user is not in the database, displays an error message.
    If the user is not authenticated using LDAP, displays an error message.
    """

    ldap_user = authenticate_ldap_user(username, password)
    if not ldap_user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "status_message": "Invalid LDAP credentials"
        })

    db_user = get_user_from_db(ldap_user["email"])
    if not db_user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "status_message": "User not authorized in application"
        })

    # Vložení username do DB pokud chybí
    # Insert username into DB if missing
    if not db_user["username"]:
        cur.execute("UPDATE users_ad SET username = ? WHERE email = ?",
                    (ldap_user["username"], ldap_user["email"]))
        conn.commit()

    # Vytvoření JWT tokenu
    # Creating JWT token
    access_token = create_access_token(
        data={"username": ldap_user["username"], "role": db_user["role"]}
    )

    # Zalogování přihlášení uživatele do databáze
    # Logging user login into the database
    cur.execute("INSERT INTO login (username, token_expiration) VALUES (?, ?)",
                (ldap_user["username"], expire))
    conn.commit()

    # Přesměrování na domovskou stránku, pokud je autentizace úspěšná
    # Redirecting to the home page if authentication is successful
    response = templates.TemplateResponse("home.html", {
        "request": request,
        "username": ldap_user["username"],
        "role": db_user["role"],
        "status_message": "Login successful ✅"
    })
    # Nastavení cookie s tokenem
    # Setting cookie with token
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # True pokud nasadíš na HTTPS / True if you deploy on HTTPS
        samesite="lax"
    )

    return response


@router.get("/me")
async def get_my_profile(user: TokenData = Depends(get_current_user)):
    """
    Získá aktuálního uživatele z JWT tokenu.

    English:
    Retrieves the current user from the JWT token.
    """
    return {
        "username": user.username,
        "role": user.role,
    }


@router.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    """
    Zobrazí registrační stránku.

    English:
    Displays the registration page.
    """
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register_post(request: Request, email: str = Form(...)):
    """
    Zpracovává registrační formulář.
    Odesílá email administrátorovi s žádostí o přístup.
    Pokud je vše v pořádku, zobrazí se potvrzovací hláška.
    Pokud dojde k chybě, zobrazí se chybová hláška.

    English:
    Processes the registration form.
    Sends an email to the administrator with a request for access.
    If everything is OK, displays a confirmation message.
    If an error occurs, displays an error message.
    """

    try:
        msg = EmailMessage()
        msg['Subject'] = 'New Access Request – Doosan Bobcat Web Application'
        msg['From'] = 'webtest.mail@seznam.cz'
        msg['To'] = 'patrik.brejla@doosan.com' # admin email
        msg.set_content(
            f"""Hello,
        
        A user with the email address {email} has submitted a request to access the internal Doosan Bobcat web application.
        
        Please review and approve the request in the account management section.
        
        Best regards,
        Bobcat Automation Team"""
        )

        with smtplib.SMTP_SSL("smtp.seznam.cz", 465) as smtp:
            smtp.login("webtest.mail@seznam.cz", os.getenv("mail_password"))
            smtp.send_message(msg)

        status_message = "Request sent to administrator."

    except Exception as e:
        status_message = "Failed to send email: " + str(e)

    return templates.TemplateResponse("login.html", {"request": request,
                                                     "status_message": status_message})


@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    """
    Zpracovává odhlášení uživatele.
    Odstraní cookie s JWT tokenem a přesměruje na přihlašovací stránku.

    English:
    Processes user logout.
    Removes the cookie with the JWT token and redirects to the login page.
    """

    status_message = "Logout successful ✅"
    response = templates.TemplateResponse("login.html", {"request": request, "status_message": status_message})
    response.delete_cookie("access_token")
    return response

