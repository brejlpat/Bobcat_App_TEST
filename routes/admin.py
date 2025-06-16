from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from routes.auth import get_current_user, User
import psycopg2
from psycopg2.extras import DictCursor
from opcua import Client, ua
from opcua.ua.uaerrors import UaError
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from email.message import EmailMessage
import smtplib
import os
from pathlib import Path
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import numpy as np
import json
from app_state import state
import sqlite3
from pathlib import Path

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

"""
Všechny následující funkce může vykonávat pouze uživatel s rolí admin.

English:
All the following functions can only be performed by a user with the admin role.
"""


@router.get("/users", response_class=HTMLResponse)
async def accounts(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí seznam uživatelů a jejich rolí.

    English:
    Displays a list of users and their roles.
    """

    if user.role != "admin":
        return templates.TemplateResponse("home.html", {
            "request": request,
            "status_message": "You are not an admin, you cannot access this page."
        })

    cur.execute("SELECT id, username, role, email FROM users_ad ORDER BY id")
    users = cur.fetchall()
    df_users = pd.DataFrame(users, columns=["ID", "Username", "Role", "Email"]).to_dict(orient="records")

    return templates.TemplateResponse("users.html", {
        "request": request,
        "df_users": df_users,
        "status_message": request.query_params.get("status_message"),
        "username": user.username,
        "role": user.role
    })


def update_user_role(user_id: int, role: str):
    """
    Aktualizuje roli uživatele v databázi.

    English:
    Updates the user's role in the database.
    """

    cur.execute("UPDATE users_ad SET role = %s WHERE id = %s", (role, user_id))
    conn.commit()


@router.get("/set_admin/{user_ID}")
async def set_admin(user_ID: int, user: User = Depends(get_current_user)):
    """
    Nastaví uživateli roli admin.

    English:
    Sets the user's role to admin.
    """

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can perform this action")
    update_user_role(user_ID, "admin")
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/set_production/{user_ID}")
async def set_production(user_ID: int, user: User = Depends(get_current_user)):
    """
    Nastaví uživateli roli production.

    English:
    Sets the user's role to production.
    """

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can perform this action")
    update_user_role(user_ID, "production")
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/set_user/{user_ID}")
async def set_user(user_ID: int, user: User = Depends(get_current_user)):
    """
    Nastaví uživateli roli user.

    English:
    Sets the user's role to user.
    """

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can perform this action")
    update_user_role(user_ID, "user")
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/delete_account/{user_ID}")
async def delete_account(user_ID: int, user: User = Depends(get_current_user)):
    """
    Smaže uživatelský účet.

    English:
    Deletes the user account.
    """

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can perform this action")
    try:
        cur.execute("DELETE FROM users_ad WHERE id = %s", (user_ID,))
        conn.commit()
        msg = "User deleted successfully ✅"
    except Exception as e:
        conn.rollback()
        msg = f"Error deleting user: {e}"
    return RedirectResponse(url=f"/admin/users", status_code=302)


@router.post("/add_user", response_class=HTMLResponse)
async def add_user(request: Request, email: str = Form(...), user: User = Depends(get_current_user)):
    """
    Přidá uživatele do databáze a odešle mu email s potvrzením.

    English:
    Adds a user to the database and sends them a confirmation email.
    """

    if user.role != "admin":
        return templates.TemplateResponse("home.html", {
            "request": request,
            "status_message": "You are not an admin, you cannot add users."
        })

    try:
        cur.execute("INSERT INTO users_ad (email) VALUES (%s)", (email,))
        conn.commit()

        msg = EmailMessage()
        msg["Subject"] = "Your Access Has Been Approved – Doosan Bobcat Web Application"
        msg["From"] = "webtest.mail@seznam.cz"
        msg["To"] = email
        msg.set_content(f"""Hello,
        
        Your access to the Doosan Bobcat internal web application has been successfully approved by the system administrator.
        
        You can now log in using your company credentials.
        
        Welcome aboard and thank you for supporting digital transformation at Bobcat!
        
        If you experience any issues, feel free to contact the administrator at patrik.brejla@doosan.com.
        
        Best regards,  
        Bobcat Automation Team""")

        with smtplib.SMTP_SSL("smtp.seznam.cz", 465) as smtp:
            smtp.login("webtest.mail@seznam.cz", os.getenv("mail_password"))
            smtp.send_message(msg)

        msg = "User added successfully ✅"
    except Exception as e:
        conn.rollback()
        msg = f"Error adding user: {e}"

    return RedirectResponse(url=f"/admin/users", status_code=302)


@router.get("/device_log", response_class=HTMLResponse)
async def device_log(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí logy na všech zařízení.
    -> vytvoření, úpravu, smazání zařízení

    English:
    Displays logs on all devices.
    -> creation, modification, deletion of devices
    """

    if user.role != "admin":
        return templates.TemplateResponse("home.html", {
            "request": request,
            "status_message": "You are not an admin, you cannot access this page."
        })

    cur.execute("SELECT * FROM device_edit ORDER BY id DESC LIMIT 10")
    logs = cur.fetchall()
    df_logs = pd.DataFrame(logs, columns=["ID", "Username", "Channel", "Payload", "Date", "Action", "Driver"]).to_dict(orient="records")

    return templates.TemplateResponse("device_log.html", {
        "request": request,
        "df_logs": df_logs,
        "status_message": request.query_params.get("status_message"),
        "username": user.username,
        "role": user.role
    })


@router.get("/users_log", response_class=HTMLResponse)
async def users_log(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí přihlášení všech uživatelů

    English:
    Displays the login of all users
    """

    if user.role != "admin":
        return templates.TemplateResponse("home.html", {
            "request": request,
            "status_message": "You are not an admin, you cannot access this page."
        })

    cur.execute("SELECT * FROM login ORDER BY id DESC LIMIT 10")
    logs = cur.fetchall()
    users_log = pd.DataFrame(logs, columns=["ID", "Username", "Token_expiration", "Date"]).to_dict(orient="records")

    return templates.TemplateResponse("users_log.html", {
        "request": request,
        "user_logs": users_log,
        "status_message": request.query_params.get("status_message"),
        "username": user.username,
        "role": user.role
    })


def ai_model_func():
    """
    Funkce pro zpracování AI modelu.

    English:
    Function for processing the AI model.
    """

    cur.execute("SELECT to_regclass('public.embeddings');")
    result = cur.fetchone()

    if result and result[0] is not None:
        cur.execute("DELETE FROM embeddings;")
        conn.commit()

    try:
        # OPC UA připojení
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

        objects = opc_client.get_objects_node()
        channels = objects.get_children()

        # Výstupní list channelů
        channel_names = []
        device_names = []
        ip_addresses = []
        drivers = []

        for ch in channels:
            ch_name = ch.get_browse_name().Name
            if ch_name[0] != "_" and ch_name != "Server":
                for dev in ch.get_children():
                    dev_name = dev.get_browse_name().Name
                    if dev_name[0] != "_":
                        channel_names.append(ch_name)
                        device_names.append(dev_name)

                        try:
                            url_id = f"http://dbr-us-DFOPC.corp.doosan.com:57412/config/v1/project/channels/{ch_name}/devices/{dev_name}"
                            response = requests.get(
                                url_id,
                                auth=HTTPBasicAuth(os.getenv("kepserver_user"), os.getenv("kepserver_password")),
                                headers={"Content-Type": "application/json"}
                            )
                            response.raise_for_status()  # vyhodí chybu, pokud response není OK

                            device_data = response.json()
                            ip_address = device_data.get("servermain.DEVICE_ID_STRING", "Nan")
                            driver = device_data.get("servermain.MULTIPLE_TYPES_DEVICE_DRIVER", "Nan")
                            drivers.append(driver)
                            if ">" in ip_address:
                                ip_address1 = ip_address.split(">")
                                ip_address2 = ip_address1[0]
                                ip_address = ip_address2[1:]
                        except Exception as e:
                            ip_address = f"Error ({str(e)})"

                        ip_addresses.append(ip_address)

        opc_client.disconnect()
    except Exception as e:
        status_message = f"Error connecting to OPC UA: {e}"
        return status_message
    if channel_names:
        embeddings = model.encode(channel_names)

        for channel, device, embedding, ip_addr, driver in zip(channel_names, device_names, embeddings, ip_addresses,
                                                               drivers):
            embedding_json = json.dumps(embedding.tolist())
            cur.execute(
                "INSERT INTO embeddings (channel, device, embedding, ip_address, driver) VALUES (?, ?, ?, ?, ?)",
                (channel, device, embedding_json, ip_addr, driver))

        # Místo ivfflat indexu prostě jen počet řádků
        cur.execute("SELECT COUNT(channel) FROM embeddings")
        existing_count = cur.fetchone()[0]

        # Pokud fakt chceš analyzovat (většinou není potřeba)
        # cur.execute("ANALYZE embeddings")

        conn.commit()

        status_message = f"✅ Successfully connected to OPC UA. Found {existing_count} channels."
        conn.commit()
        return status_message
    else:
        status_message = "No channels found in OPC UA."
        return status_message


@router.get("/ai_model", response_class=HTMLResponse)
async def ai_model(request: Request, user: User = Depends(get_current_user)):
    """
    Zobrazí seznam AI modelů a jejich stav.

    English:
    Displays a list of AI models and their status.
    """

    if user.role != "admin":
        return templates.TemplateResponse("home.html", {
            "request": request,
            "status_message": "You are not an admin, you cannot access this page."
        })

    status_message = ai_model_func()

    return templates.TemplateResponse("home.html", {
        "request": request,
        "status_message": status_message,
        "username": user.username,
        "role": user.role
    })
