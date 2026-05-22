from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import psycopg2
from psycopg2 import pool
import os

app = FastAPI()
connection_pool = None

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

class ConfigUpdate(BaseModel):
    restriccion_votos: int
    restriccion_creacion: int
    distancia_limite: int = 50
    votos_cerca: int = 5
    votos_lejos: int = 2
    votos_umbral: int = 100
    votos_por_sesion: int = 1
    baches_por_sesion: int = 1

def get_conn():
    return connection_pool.getconn()

def put_conn(conn):
    connection_pool.putconn(conn)

@app.on_event("startup")
def startup():
    global connection_pool
    connection_pool = pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=20,
        dsn=os.environ.get("DATABASE_URL")
    )
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS baches (
            id SERIAL PRIMARY KEY,
            latitud FLOAT NOT NULL,
            longitud FLOAT NOT NULL,
            votos INTEGER DEFAULT 0,
            votantes INTEGER DEFAULT 0,
            completado BOOLEAN DEFAULT FALSE,
            fecha_creacion TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("ALTER TABLE baches ADD COLUMN IF NOT EXISTS votos INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE baches ADD COLUMN IF NOT EXISTS votantes INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE baches ADD COLUMN IF NOT EXISTS completado BOOLEAN DEFAULT FALSE")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave VARCHAR(50) PRIMARY KEY,
            valor INTEGER NOT NULL
        )
    """)
    defaults = [
        ('restriccion_votos', 360),
        ('restriccion_creacion', 1440),
        ('distancia_limite', 50),
        ('votos_cerca', 5),
        ('votos_lejos', 2),
        ('votos_umbral', 100),
        ('votos_por_sesion', 1),
        ('baches_por_sesion', 1),
    ]
    for clave, valor in defaults:
        cur.execute("INSERT INTO config (clave, valor) VALUES (%s, %s) ON CONFLICT DO NOTHING", (clave, valor))
    conn.commit()
    cur.close()
    put_conn(conn)

@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.get("/config")
def get_config():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT clave, valor FROM config")
    rows = cur.fetchall()
    cur.close()
    put_conn(conn)
    return {r[0]: r[1] for r in rows}

@app.post("/config")
def set_config(cfg: ConfigUpdate):
    conn = get_conn()
    cur = conn.cursor()
    fields = {
        'restriccion_votos': cfg.restriccion_votos,
        'restriccion_creacion': cfg.restriccion_creacion,
        'distancia_limite': cfg.distancia_limite,
        'votos_cerca': cfg.votos_cerca,
        'votos_lejos': cfg.votos_lejos,
        'votos_umbral': cfg.votos_umbral,
        'votos_por_sesion': cfg.votos_por_sesion,
        'baches_por_sesion': cfg.baches_por_sesion,
    }
    for clave, valor in fields.items():
        cur.execute("UPDATE config SET valor = %s WHERE clave = %s", (valor, clave))
    conn.commit()
    cur.close()
    put_conn(conn)
    return {"ok": True}

@app.post("/baches")
def crear_bache(bache: BacheCreate):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO baches (latitud, longitud, votos) VALUES (%s, %s, %s) RETURNING id, latitud, longitud, votos, votantes, completado, fecha_creacion",
        (bache.latitud, bache.longitud, bache.votos_iniciales)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    put_conn(conn)
    estado = 'reparado' if row[5] else 'reportado'
    return {"id": row[0], "latitud": row[1], "longitud": row[2], "votos": row[3], "votantes": row[4], "completado": row[5], "estado": estado, "fecha_creacion": row[6]}

@app.get("/baches")
def obtener_baches():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, latitud, longitud, votos, votantes, completado, fecha_creacion FROM baches ORDER BY fecha_creacion DESC")
    rows = cur.fetchall()
    cur.execute("SELECT valor FROM config WHERE clave = 'votos_umbral'")
    umbral_row = cur.fetchone()
    umbral = umbral_row[0] if umbral_row else 100
    cur.close()
    put_conn(conn)
    def estado(r):
        if r[5]: return 'reparado'
        if r[3] >= umbral: return 'urgente'
        return 'reportado'
    return [{"id": r[0], "latitud": r[1], "longitud": r[2], "votos": r[3], "votantes": r[4], "completado": r[5], "estado": estado(r), "fecha_creacion": r[6]} for r in rows]

@app.post("/baches/{id}/votar")
def votar_bache(id: int, voto: VotoCreate):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE baches SET votos = votos + %s, votantes = votantes + 1 WHERE id = %s RETURNING votos, votantes",
        (voto.puntos, id)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    put_conn(conn)
    if not row:
        return {"error": "Bache no encontrado"}
    return {"id": id, "votos": row[0], "votantes": row[1]}

@app.delete("/baches/{id}")
def eliminar_bache(id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM baches WHERE id = %s RETURNING id", (id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    put_conn(conn)
    if not row:
        return {"error": "Bache no encontrado"}
    return {"eliminado": True, "id": id}

@app.post("/baches/{id}/completar")
def completar_bache(id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE baches SET completado = TRUE WHERE id = %s RETURNING id", (id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    put_conn(conn)
    if not row:
        return {"error": "Bache no encontrado"}
    return {"completado": True, "id": id}
