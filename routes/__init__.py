from .auth import router as auth_router
from .admin import router as admin_router
from .automation import router as automation_router
from .main import router as main_router
from .device_mapping import router as device_mapping_router
from .create_device import router as create_device_router

# Přímo exportujeme routery – prefix přidáme v app.py
# Directly export the routers – prefix will be added in app.py
routers = [
    ("auth", auth_router),
    ("admin", admin_router),
    ("automation", automation_router),
    ("main", main_router),
    ("device_mapping", device_mapping_router),
    ("create_device", create_device_router)
]
