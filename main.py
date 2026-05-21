from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import get_db_connection
from datetime import datetime

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

@app.on_event("startup")
def crear_tablas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS baches (
            id SERIAL PRIMARY KEY,
            latitud FLOAT NOT NULL,
            longitud FLOAT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.post("/baches")
def crear_bache(bache: BacheCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO baches (latitud, longitud) VALUES (%s, %s) RETURNING id, latitud, longitud, fecha_creacion",
        (bache.latitud, bache.longitud)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"id": row[0], "latitud": row[1], "longitud": row[2], "fecha_creacion": row[3]}

@app.get("/baches")
def obtener_baches():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, latitud, longitud, fecha_creacion FROM baches ORDER BY fecha_creacion DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "latitud": r[1], "longitud": r[2], "fecha_creacion": r[3]} for r in rows]

@app.get("/")
def health():
    return {"status": "ok", "mensaje": "Baches API funcionando"}
