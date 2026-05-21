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

@app.post("/baches")
def crear_bache(bache: BacheCreate, request: Request):
    ip = get_ip(request)
    conn = get_db_connection()
    cur = conn.cursor()

    # Verificar si creó un bache en las últimas 24h
    hace_24h = datetime.now() - timedelta(hours=24)
    cur.execute(
        "SELECT timestamp FROM acciones WHERE ip=%s AND tipo='bache' AND timestamp > %s ORDER BY timestamp DESC LIMIT 1",
        (ip, hace_24h)
    )
    row = cur.fetchone()
    if row:
        segundos = int((row[0] + timedelta(hours=24) - datetime.now()).total_seconds())
        cur.close()
        conn.close()
        return JSONResponse(status_code=429, content={"error": "limite_bache", "segundos_restantes": segundos})

    cur.execute(
        "INSERT INTO baches (latitud, longitud, votos) VALUES (%s, %s, %s) RETURNING id, latitud, longitud, votos, fecha_creacion",
        (bache.latitud, bache.longitud, bache.votos_iniciales)
    )
    nuevo = cur.fetchone()
    cur.execute("INSERT INTO acciones (ip, tipo, bache_id) VALUES (%s, 'bache', %s)", (ip, nuevo[0]))
    conn.commit()
    cur.close()
    conn.close()
    return {"id": nuevo[0], "latitud": nuevo[1], "longitud": nuevo[2], "votos": nuevo[3], "fecha_creacion": nuevo[4]}

@app.get("/baches")
def obtener_baches():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, latitud, longitud, votos, fecha_creacion FROM baches ORDER BY fecha_creacion DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "latitud": r[1], "longitud": r[2], "votos": r[3], "fecha_creacion": r[4]} for r in rows]

@app.post("/baches/{id}/votar")
def votar_bache(id: int, voto: VotoCreate, request: Request):
    ip = get_ip(request)
    conn = get_db_connection()
    cur = conn.cursor()

    # Verificar bloqueo de 6h por haber creado un bache
    hace_6h = datetime.now() - timedelta(hours=6)
    cur.execute(
        "SELECT timestamp FROM acciones WHERE ip=%s AND tipo='bache' AND timestamp > %s ORDER BY timestamp DESC LIMIT 1",
        (ip, hace_6h)
    )
    row = cur.fetchone()
    if row:
        segundos = int((row[0] + timedelta(hours=6) - datetime.now()).total_seconds())
        cur.close()
        conn.close()
        return JSONResponse(status_code=429, content={"error": "bloqueo_creacion", "segundos_restantes": segundos})

    # Verificar que no haya votado 2 veces este bache
    cur.execute(
        "SELECT COUNT(*) FROM acciones WHERE ip=%s AND tipo='voto' AND bache_id=%s",
        (ip, id)
    )
    conteo = cur.fetchone()[0]
    if conteo >= 2:
        cur.close()
        conn.close()
        return JSONResponse(status_code=429, content={"error": "max_votos_bache"})

    cur.execute(
        "UPDATE baches SET votos = votos + %s WHERE id = %s RETURNING votos",
        (voto.puntos, id)
    )
    row = cur.fetchone()
    cur.execute("INSERT INTO acciones (ip, tipo, bache_id) VALUES (%s, 'voto', %s)", (ip, id))
    conn.commit()
    cur.close()
    conn.close()
    if not row:
        return {"error": "Bache no encontrado"}
    return {"id": id, "votos": row[0], "votos_usados": conteo + 1}

@app.get("/estado")
def estado_usuario(request: Request):
    """Devuelve el estado actual del usuario: bloqueos y tiempos restantes"""
    ip = get_ip(request)
    conn = get_db_connection()
    cur = conn.cursor()

    ahora = datetime.now()
    hace_24h = ahora - timedelta(hours=24)
    hace_6h = ahora - timedelta(hours=6)

    cur.execute(
        "SELECT timestamp FROM acciones WHERE ip=%s AND tipo='bache' AND timestamp > %s ORDER BY timestamp DESC LIMIT 1",
        (ip, hace_24h)
    )
    ultimo_bache = cur.fetchone()

    cur.execute(
        "SELECT timestamp FROM acciones WHERE ip=%s AND tipo='bache' AND timestamp > %s ORDER BY timestamp DESC LIMIT 1",
        (ip, hace_6h)
    )
    bache_reciente = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "puede_crear_bache": ultimo_bache is None,
        "segundos_para_crear": int((ultimo_bache[0] + timedelta(hours=24) - ahora).total_seconds()) if ultimo_bache else 0,
        "bloqueado_por_creacion": bache_reciente is not None,
        "segundos_bloqueo_votar": int((bache_reciente[0] + timedelta(hours=6) - ahora).total_seconds()) if bache_reciente else 0,
    }
