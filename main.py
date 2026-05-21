Skip to content
reparabaches-commits
BACHES
Repository navigation
Code
Issues
Pull requests
Actions
Projects
Wiki
Security and quality
Insights
Settings
Files
Go to file
t
T
static
ESCALLE.HTML
Procfile
database.py
main.py
requirements.txt
BACHES
/
main.py
in
main

Edit

Preview
Indent mode

Spaces
Indent size

4
Line wrap mode

No wrap
Editing main.py file contents
  1
  2
  3
  4
  5
  6
  7
  8
  9
 10
 11
 12
 13
 14
 15
 16
 17
 18
 19
 20
 21
 22
 23
 24
 25
 26
 27
 28
 29
 30
 31
 32
 33
 34
 35
 36
 37
 38
 39
 40
 41
 42
 43
 44
 45
 46
 47
 48
 49
 50
 51
 52
 53
 54
 55
 56
 57
 58
 59
 60
 61
 62
 63
 64
 65
 66
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from database import get_db_connection
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

class BacheCreate(BaseModel):
    latitud: float
    longitud: float
    votos_iniciales: int = 2

class VotoCreate(BaseModel):
    puntos: int

def get_ip(request: Request):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

@app.on_event("startup")
def crear_tablas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS baches (
            id SERIAL PRIMARY KEY,
            latitud FLOAT NOT NULL,
            longitud FLOAT NOT NULL,
            votos INTEGER DEFAULT 0,
            fecha_creacion TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        ALTER TABLE baches ADD COLUMN IF NOT EXISTS votos INTEGER DEFAULT 0
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS acciones (
            id SERIAL PRIMARY KEY,
            ip VARCHAR(100) NOT NULL,
            tipo VARCHAR(10) NOT NULL,
            bache_id INTEGER,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.get("/")
def index():
    return FileResponse("static/index.html")

Use Control + Shift + m to toggle the tab key moving focus. Alternatively, use esc then tab to move to the next interactive element on the page.
