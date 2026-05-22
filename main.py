from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
    global connection_pool
    connection_pool = pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=20,
        dsn=os.environ.get("DATABASE_URL")
    )
    conn = connection_pool.getconn()
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
    """
    )
    cur.execute("""
        ALTER TABLE baches ADD COLUMN IF NOT EXISTS completado BOOLEAN DEFAULT FALSE
    """
    )
    cur.execute("""
        ALTER TABLE baches ADD COLUMN IF NOT EXISTS votantes INTEGER DEFAULT 0
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave VARCHAR(50) PRIMARY KEY,
            valor INTEGER NOT NULL
        )
    """)
    cur.execute("INSERT INTO config (clave, valor) VALUES ('restriccion_votos', 360) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO config (clave, valor) VALUES ('restriccion_creacion', 1440) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO config (clave, valor) VALUES ('distancia_limite', 50) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO config (clave, valor) VALUES ('votos_cerca', 5) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO config (clave, valor) VALUES ('votos_lejos', 2) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO config (clave, valor) VALUES ('votos_umbral', 100) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO config (clave, valor) VALUES ('votos_por_sesion', 1) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO config (clave, valor) VALUES ('baches_por_sesion', 1) ON CONFLICT DO NOTHING")
    conn.commit()
    cur.close()
    connection_pool.putconn(conn)

@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.post("/baches")
def crear_bache(bache: BacheCreate):
    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO baches (latitud, longitud, votos) VALUES (%s, %s, %s) RETURNING id, latitud, longitud, votos, fecha_creacion",
        (bache.latitud, bache.longitud, bache.votos_iniciales)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    connection_pool.putconn(conn)
    return {"id": row[0], "latitud": row[1], "longitud": row[2], "votos": row[3], "fecha_creacion": row[4]}

@app.get("/baches")
def obtener_baches():
    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute("SELECT id, latitud, longitud, votos, votantes, completado, fecha_creacion FROM baches ORDER BY fecha_creacion DESC")
    rows = cur.fetchall()
    cur.execute("SELECT valor FROM config WHERE clave = 'votos_umbral'")
    umbral_row = cur.fetchone()
    umbral = umbral_row[0] if umbral_row else 100
    cur.close()
    connection_pool.putconn(conn)
    def estado(r):
        if r[5]: return 'reparado'
        if r[3] >= umbral: return 'urgente'
        return 'reportado'
    return [{"id": r[0], "latitud": r[1], "longitud": r[2], "votos": r[3], "votantes": r[4], "completado": r[5], "estado": estado(r), "fecha_creacion": r[6]} for r in rows]

@app.post("/baches/{id}/votar")
def votar_bache(id: int, voto: VotoCreate):
    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE baches SET votos = votos + %s, votantes = votantes + 1 WHERE id = %s RETURNING votos, votantes",
        (voto.puntos, id)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    connection_pool.putconn(conn)
    if not row:
        return {"error": "Bache no encontrado"}
    return {"id": id, "votos": row[0], "votantes": row[1]}



class ConfigUpdate(BaseModel):
    restriccion_votos: int
    restriccion_creacion: int
    distancia_limite: int = 50
    votos_cerca: int = 5
    votos_lejos: int = 2
    votos_umbral: int = 100
    votos_por_sesion: int = 1
    baches_por_sesion: int = 1

@app.get("/config")
def get_config():
    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute("SELECT clave, valor FROM config")
    rows = cur.fetchall()
    cur.close()
    connection_pool.putconn(conn)
    return {r[0]: r[1] for r in rows}

@app.post("/config")
def set_config(cfg: ConfigUpdate):
    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'restriccion_votos'", (cfg.restriccion_votos,))
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'restriccion_creacion'", (cfg.restriccion_creacion,))
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'distancia_limite'", (cfg.distancia_limite,))
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'votos_cerca'", (cfg.votos_cerca,))
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'votos_lejos'", (cfg.votos_lejos,))
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'votos_umbral'", (cfg.votos_umbral,))
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'votos_por_sesion'", (cfg.votos_por_sesion,))
    cur.execute("UPDATE config SET valor = %s WHERE clave = 'baches_por_sesion'", (cfg.baches_por_sesion,))
    conn.commit()
    cur.close()
    connection_pool.putconn(conn)
    return {"ok": True}

@app.delete("/baches/{id}")
def eliminar_bache(id: int):
    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute("DELETE FROM baches WHERE id = %s RETURNING id", (id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    connection_pool.putconn(conn)
    if not row:
        return {"error": "Bache no encontrado"}
    return {"eliminado": True, "id": id}


@app.post("/baches/{id}/completar")
def completar_bache(id: int):
    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE baches ADD COLUMN IF NOT EXISTS completado BOOLEAN DEFAULT FALSE
    """
    )
    cur.execute("""
        ALTER TABLE baches ADD COLUMN IF NOT EXISTS votantes INTEGER DEFAULT 0
    """)
    cur.execute(
        "UPDATE baches SET completado = TRUE WHERE id = %s RETURNING id",
        (id,)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    connection_pool.putconn(conn)
    if not row:
        return {"error": "Bache no encontrado"}
    return {"completado": True, "id": id}
