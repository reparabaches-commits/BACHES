from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from database import get_db_connection
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class BacheCreate(BaseModel):
    latitud: float
    longitud: float

class VotoCreate(BaseModel):
    bache_id: int
    latitud_usuario: Optional[float] = None
    longitud_usuario: Optional[float] = None

def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def estado_bache(puntos):
    if puntos >= 50:
        return "reparacion"
    return "candidato"

@app.on_event("startup")
def crear_tablas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS baches (
            id SERIAL PRIMARY KEY,
            latitud FLOAT NOT NULL,
            longitud FLOAT NOT NULL,
            puntos INTEGER DEFAULT 0,
            estado VARCHAR(20) DEFAULT 'candidato',
            fecha_creacion TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votos (
            id SERIAL PRIMARY KEY,
            bache_id INTEGER REFERENCES baches(id),
            puntos INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.post("/baches")
def crear_bache(bache: BacheCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO baches (latitud, longitud) VALUES (%s, %s) RETURNING id, latitud, longitud, puntos, estado, fecha_creacion",
        (bache.latitud, bache.longitud)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"id": row[0], "latitud": row[1], "longitud": row[2], "puntos": row[3], "estado": row[4], "fecha_creacion": row[5]}

@app.get("/baches")
def obtener_baches():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, latitud, longitud, puntos, estado, fecha_creacion FROM baches ORDER BY puntos DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "latitud": r[1], "longitud": r[2], "puntos": r[3], "estado": r[4], "fecha_creacion": r[5]} for r in rows]

@app.post("/votos")
def votar(voto: VotoCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT latitud, longitud, puntos FROM baches WHERE id = %s", (voto.bache_id,))
    bache = cur.fetchone()
    if not bache:
        cur.close()
        conn.close()
        return {"error": "Bache no encontrado"}

    puntos = 2
    distancia = None
    if voto.latitud_usuario and voto.longitud_usuario:
        distancia = distancia_metros(voto.latitud_usuario, voto.longitud_usuario, bache[0], bache[1])
        if distancia <= 50:
            puntos = 5

    nuevos_puntos = bache[2] + puntos
    nuevo_estado = estado_bache(nuevos_puntos)

    cur.execute("UPDATE baches SET puntos = %s, estado = %s WHERE id = %s", (nuevos_puntos, nuevo_estado, voto.bache_id))
    cur.execute("INSERT INTO votos (bache_id, puntos) VALUES (%s, %s)", (voto.bache_id, puntos))
    conn.commit()
    cur.close()
    conn.close()
    return {"puntos_sumados": puntos, "total_puntos": nuevos_puntos, "estado": nuevo_estado, "distancia_metros": distancia}
