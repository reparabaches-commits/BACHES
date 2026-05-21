from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from database import get_db_connection

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
    # Agregar columna votos si ya existe la tabla sin ella
    cur.execute("""
        ALTER TABLE baches ADD COLUMN IF NOT EXISTS votos INTEGER DEFAULT 0
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
        "INSERT INTO baches (latitud, longitud, votos) VALUES (%s, %s, %s) RETURNING id, latitud, longitud, votos, fecha_creacion",
        (bache.latitud, bache.longitud, bache.votos_iniciales)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"id": row[0], "latitud": row[1], "longitud": row[2], "votos": row[3], "fecha_creacion": row[4]}

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
def votar_bache(id: int, voto: VotoCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE baches SET votos = votos + %s WHERE id = %s RETURNING votos",
        (voto.puntos, id)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not row:
        return {"error": "Bache no encontrado"}
    return {"id": id, "votos": row[0]}
