from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.templating import Jinja2Templates
from routes.auth import get_current_user, User
import requests
import json
import shutil
import os
from pathlib import Path
from dotenv import load_dotenv
from app_state import state
from app_state import channel_properties
from app_state import device_properties
from routes.admin import ai_model_func
import psycopg2
from psycopg2.extras import DictCursor
from sentence_transformers import SentenceTransformer
import sqlite3
from pathlib import Path

# Načtení .env souboru
# Load the .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Cesta k databázovému souboru
DB_PATH = Path(__file__).parent.parent / "test.db"

# Připojení k SQLite
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row  # Umožní přístup k sloupcům podle názvu
cur = conn.cursor()

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/channel")
async def channel(
        request: Request,
        driver: str = Form(...),
        user: User = Depends(get_current_user)
):
    """
    Zobrazí nastavení kanálu.

    English:
    Displays channel settings.
    """

    status_message = f"You´ve selected driver: {driver}"
    return templates.TemplateResponse("channel_setting.html",
                                      {"request": request,
                                       "driver": driver,
                                       "status_message": status_message,
                                       "username": user.username,
                                       "role": user.role
                                       })


@router.post("/create_channel")
async def create_channel(
        request: Request,
        channel_name: str = Form(...),
        driver: str = Form(...),
        endpoint_url: str = Form(""),
        opc_pass: str = Form(""),
        opc_username: str = Form(""),
        channel_prog_id: str = Form(""),
        source_name: str = Form(""),
        source_username: str = Form(""),
        source_pass: str = Form(""),
        description: str = Form(""),
        user: User = Depends(get_current_user)
):
    """
    Vytvoří kanál OPC UA Client.

    English:
    Creates an OPC UA Client channel.
    """

    if not description:
        description = f"{driver} {channel_name}"
    if not opc_username:
        opc_username = ""
    if not opc_pass:
        opc_pass = ""

    # URL pro API KEPServerEX
    url = "http://dbr-us-DFOPC.corp.doosan.com:57412/config/v1/project/channels"

    username = os.getenv("kepserver_user")
    password = os.getenv("kepserver_password")
    headers = {"Content-Type": "application/json"}

    if driver == "OPC UA Client":
        payload = channel_properties.OPC_UA_Client.copy()
        payload["common.ALLTYPES_NAME"] = channel_name
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload["servermain.MULTIPLE_TYPES_DEVICE_DRIVER"] = driver
        payload["opcuaclient.CHANNEL_UA_SERVER_ENDPOINT_URL"] = endpoint_url
        payload["opcuaclient.CHANNEL_AUTHENTICATION_USERNAME"] = opc_username
        payload["opcuaclient.CHANNEL_AUTHENTICATION_PASSWORD"] = opc_pass
        payload.pop("PROJECT_ID", None)
    elif driver == "Allen-Bradley ControlLogix Ethernet":
        payload = channel_properties.Allen_Bradley_ControlLogix_Ethernet.copy()
        payload["common.ALLTYPES_NAME"] = channel_name
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload["servermain.MULTIPLE_TYPES_DEVICE_DRIVER"] = driver
        payload.pop("PROJECT_ID", None)
    elif driver == "Torque Tool Ethernet":
        payload = channel_properties.Torque_Tool_Ethernet.copy()
        payload["common.ALLTYPES_NAME"] = channel_name
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload["servermain.MULTIPLE_TYPES_DEVICE_DRIVER"] = driver
        payload.pop("PROJECT_ID", None)
    elif driver == "OPC DA Client":
        payload = channel_properties.OPC_DA_Client.copy()
        payload["common.ALLTYPES_NAME"] = channel_name
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload["servermain.MULTIPLE_TYPES_DEVICE_DRIVER"] = driver
        payload["opcdaclient.CHANNEL_PROG_ID"] = channel_prog_id
        payload.pop("PROJECT_ID", None)

    response = requests.post(url, headers=headers, data=json.dumps(payload), auth=(username, password))

    if response.status_code == 201:
        status_message = f"Channel '{channel_name}' was successfully created!"
    else:
        status_message = f"Failed to create channel: {response.status_code}"
        return templates.TemplateResponse("channel_setting.html",
                                          {"request": request,
                                           "driver": driver,
                                           "status_message": status_message,
                                           "username": user.username,
                                           "role": user.role
                                           })

    return templates.TemplateResponse("device_setting.html", {
        "request": request,
        "status_message": status_message,
        "channel_name": channel_name,
        "driver": driver,
        "username": user.username,
        "role": user.role
    })


@router.post("/create_device")
async def create_device(
        request: Request,
        device_name: str = Form(...),
        channel_name: str = Form(...),
        driver: str = Form(...),
        description: str = Form(...),
        ip_address_AB: str = Form(""),
        device_port: str = Form(""),
        enet_port: str = Form(""),
        ip_address_TT: str = Form(""),
        model_kep: str = Form(""),
        line: str = Form(...),
        image: UploadFile = File(...),
        user: User = Depends(get_current_user)
):
    """
    Vytvoří zařízení OPC UA Client.

    English:
    Creates an OPC UA Client device.
    """

    # URL pro API KEPServerEX
    url = f"http://dbr-us-DFOPC.corp.doosan.com:57412/config/v1/project/channels/{channel_name}/devices"

    username = os.getenv("kepserver_user")
    password = os.getenv("kepserver_password")
    headers = {"Content-Type": "application/json"}

    image_dir = "static/images/DEVICES_MAP"
    os.makedirs(image_dir, exist_ok=True)
    image_path = os.path.join(image_dir, f"{channel_name}.png")

    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    if driver == "OPC UA Client":
        payload = device_properties.OPC_UA_Client_device.copy()
        payload["common.ALLTYPES_NAME"] = device_name
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload.pop("PROJECT_ID", None)
    elif driver == "Allen-Bradley ControlLogix Ethernet":
        payload = device_properties.Allen_Bradley_ControlLogix_Ethernet_device.copy()
        payload["common.ALLTYPES_NAME"] = device_name
        payload["servermain.DEVICE_ID_STRING"] = ip_address_AB
        payload["controllogix_ethernet.DEVICE_PORT_NUMBER"] = int(device_port)
        payload["controllogix_ethernet.DEVICE_CL_ENET_PORT_NUMBER"] = int(enet_port)
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload["servermain.DEVICE_MODEL"] = int(model_kep)
        payload.pop("PROJECT_ID", None)
    elif driver == "Torque Tool Ethernet":
        payload = device_properties.Torque_Tool_Ethernet_device.copy()
        payload["common.ALLTYPES_NAME"] = device_name
        payload["servermain.DEVICE_ID_STRING"] = ip_address_TT
        payload["torque_tool_ethernet.DEVICE_PORT_NUMBER"] = int(device_port)
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload.pop("PROJECT_ID", None)
    elif driver == "OPC DA Client":
        payload = device_properties.OPC_DA_Client_device.copy()
        payload["common.ALLTYPES_NAME"] = device_name
        payload["common.ALLTYPES_DESCRIPTION"] = description
        payload.pop("PROJECT_ID", None)

    response = requests.post(url, headers=headers, data=json.dumps(payload), auth=(username, password))

    sql_payload = {"device": device_name,
                   "channel": channel_name}

    if response.status_code == 201:
        status_message = f"✅ Device '{device_name}' was successfully created in channel '{channel_name}'!"
        cur.execute("INSERT INTO device_edit (username, channel_name, payload, action, driver) VALUES (?, ?, ?, ?, ?)",
                    (user.username, channel_name, json.dumps(sql_payload), "CREATE", driver))
        conn.commit()
    else:
        status_message = f"❌ Error when creating the device: {response.status_code}"

    state.line = line

    if ip_address_TT:
        ip_address = ip_address_TT
    elif ip_address_AB:
        ip1 = ip_address_AB.split(">")[0]
        ip_address = ip1[1:]

    # Funkce pro aktualizaci AI modelu
    # Function for AI model update
    channel_name_list = [channel_name]
    embedding = model.encode(channel_name_list)[0]
    vector_str = json.dumps(embedding.tolist())
    cur.execute("INSERT INTO embeddings (channel, device, embedding, ip_address) VALUES (?, ?, ?, ?)",
                (channel_name, device_name, vector_str, ip_address))
    conn.commit()

    return templates.TemplateResponse("device_mapping.html", {
        "request": request,
        "status_message": status_message,
        "device_name": device_name,
        "channel_name": channel_name,
        "line": state.line,
        "username": user.username,
        "role": user.role
    })
