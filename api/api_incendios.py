import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

database_url = os.getenv("DATABASE_URL")
if database_url:
    pool = ThreadedConnectionPool(1, 8, dsn=database_url)
else:
    DB = dict(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "incendios_peru"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )
    pool = ThreadedConnectionPool(1, 8, **DB)

app = FastAPI(
    title="Susceptibilidad a incendios forestales",
    description="Índice relativo por distrito (celdas de 500 m, calibración 2012-2021).",
    version="1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

COLUMNAS = """ubigeo, departamen AS departamento, provincia, distrito,
              celdas, susc_media, susc_p90, susc_max"""


@contextmanager
def cursor():
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.rollback()
    finally:
        pool.putconn(conn)


def nivel(x):
    if x is None:
        return None
    for corte, nombre in ((0.2, "Muy baja"), (0.4, "Baja"), (0.6, "Media"), (0.8, "Alta")):
        if x < corte:
            return nombre
    return "Muy alta"


def preparar(fila):
    fila["nivel"] = nivel(fila["susc_media"])
    return fila


@app.get("/salud")
def salud():
    with cursor() as cur:
        cur.execute("SELECT COUNT(*) AS distritos, COUNT(susc_media) AS con_dato FROM res.distritos_susceptibilidad")
        return {"estado": "ok", **cur.fetchone()}


@app.get("/departamentos")
def departamentos():
    with cursor() as cur:
        cur.execute("SELECT DISTINCT departamen FROM res.distritos_susceptibilidad ORDER BY 1")
        return [f["departamen"] for f in cur.fetchall()]


@app.get("/distrito/{ubigeo}")
def distrito(ubigeo: str):
    with cursor() as cur:
        cur.execute(f"SELECT {COLUMNAS} FROM res.distritos_susceptibilidad WHERE ubigeo = %s", (ubigeo,))
        fila = cur.fetchone()
    if not fila:
        raise HTTPException(404, "Ubigeo no encontrado")
    return preparar(fila)


@app.get("/punto")
def punto(lon: float = Query(..., ge=-82, le=-68), lat: float = Query(..., ge=-19, le=1)):
    with cursor() as cur:
        cur.execute(
            f"""SELECT {COLUMNAS} FROM res.distritos_susceptibilidad
                WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) LIMIT 1""",
            (lon, lat),
        )
        fila = cur.fetchone()
    if not fila:
        raise HTTPException(404, "El punto no cae dentro de un distrito")
    return preparar(fila)


@app.get("/ranking")
def ranking(departamento: str, n: int = Query(10, ge=1, le=50), min_celdas: int = Query(30, ge=1)):
    with cursor() as cur:
        cur.execute(
            f"""SELECT {COLUMNAS} FROM res.distritos_susceptibilidad
                WHERE departamen = %s AND susc_media IS NOT NULL AND celdas >= %s
                ORDER BY susc_media DESC LIMIT %s""",
            (departamento.upper(), min_celdas, n),
        )
        return [preparar(f) for f in cur.fetchall()]
