# app.py
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from simulacion import simular_proyeccion  # lógica principal
from generator import generar_dataset      # nuevo módulo de generación sintética

app = FastAPI(title="Simulador de Proyección de Facturación y RRHH")

# ==========================
# CORS
# ==========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción puedes restringir dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Static & Templates
# ==========================
templates = Jinja2Templates(directory="templates")

# Montar carpeta 'static' (dentro está 'images', 'styles', etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ==========================
# RUTAS HTML (templates)
# ==========================

# HOME: página principal (usa templates/home.html)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# GENERADOR DE DATOS: muestra el formulario (templates/generador.html)
@app.get("/generador", response_class=HTMLResponse)
async def generador_page(request: Request):
    context = {
        "request": request,
        "anio_inicio_default": 2021,
        "anio_fin_default": 2025,
        "total_facturas_default": 65_974,
        "total_facturacion_default": 53_609_928_028,
        "total_prestadores_default": 1338,
        "total_prestadores_solo_interno_default": 663,
        "seed_default": 42,
    }
    return templates.TemplateResponse("generador.html", context)


@app.post("/generador", response_class=StreamingResponse)
async def generar_datos_csv(
    anio_inicio: int = Form(...),
    anio_fin: int = Form(...),
    total_facturas_inicial: int = Form(...),
    total_facturacion_inicial: int = Form(...),
    total_prestadores: int = Form(...),
    total_prestadores_solo_interno: int = Form(...),
    seed: int = Form(42),
    filename: str = Form("DatosPrueba"),
):
    df = generar_dataset(
        anio_inicio=anio_inicio,
        anio_fin=anio_fin,
        total_facturas_inicial=total_facturas_inicial,
        total_facturacion_inicial=total_facturacion_inicial,
        total_prestadores=total_prestadores,
        total_prestadores_solo_interno=total_prestadores_solo_interno,
        seed=seed,
    )

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    safe_name = filename.strip() or "DatosPrueba"
    filename_csv = f"{safe_name}.csv"

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_csv}"'},
    )



# Página del formulario principal de simulación (usa templates/form.html)
@app.get("/form", response_class=HTMLResponse)
async def form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})


# Página de resultados de simulación (usa templates/simulation.html)
@app.post("/simulation", response_class=HTMLResponse)
async def simulation_page(
    request: Request,
    file: UploadFile = File(...),
    anio_proyeccion: int = Form(2026),
    crecimiento_facturas: float = Form(0.05),    # 5%
    crecimiento_facturacion: float = Form(0.03), # 3%
    p_interno: float = Form(0.92),               # 92% interno
    p_externo: float = Form(0.08),               # 8% externo
    horas_diarias_por_colaborador: float = Form(8.0),
    dias_laborales_mes: int = Form(20),          # 20 días/mes
):

    # Leer CSV
    contents = await file.read()
    df = pd.read_csv(io.StringIO(contents.decode("utf-8")))

    # Ejecutar simulación (mensual + anual)
    df_mensual, df_anual = simular_proyeccion(
        df,
        anio_proyeccion=anio_proyeccion,
        crecimiento_facturas=crecimiento_facturas,
        crecimiento_facturacion=crecimiento_facturacion,
        p_interno=p_interno,
        p_externo=p_externo,
        horas_diarias_por_colaborador=horas_diarias_por_colaborador,
        dias_laborales_mes=dias_laborales_mes,
    )

    results_mensual = df_mensual.to_dict(orient="records")
    results_anual = df_anual.to_dict(orient="records")

    # =========================
    # CÁLCULO DE COLABORADORES
    # =========================
    colabs_interno_anual = 0
    colabs_interno_mensual = 0.0
    colabs_externo_anual = 0
    colabs_externo_mensual = 0.0

    if not df_anual.empty:
        # Interno
        row_int = df_anual[df_anual["aplicativo"] == "Interno"]
        if not row_int.empty:
            r = row_int.iloc[0]
            colabs_interno_anual = int(round(r["colaboradores_pico_anual"]))
            colabs_interno_mensual = float(r["colaboradores_necesarios_mes"])

        # Externo
        row_ext = df_anual[df_anual["aplicativo"] == "Externo"]
        if not row_ext.empty:
            r = row_ext.iloc[0]
            colabs_externo_anual = int(round(r["colaboradores_pico_anual"]))
            colabs_externo_mensual = float(r["colaboradores_necesarios_mes"])

    # Totales (para la pestaña "Ambos")
    total_colabs_anual = colabs_interno_anual + colabs_externo_anual
    total_colabs_mensual = colabs_interno_mensual + colabs_externo_mensual

    return templates.TemplateResponse(
        "simulation.html",
        {
            "request": request,
            "anio_proyeccion": anio_proyeccion,
            "results_mensual": results_mensual,
            "results_anual": results_anual,
            # Colaboradores por modalidad (anual y mensual)
            "colabs_interno_anual": colabs_interno_anual,
            "colabs_interno_mensual": colabs_interno_mensual,
            "colabs_externo_anual": colabs_externo_anual,
            "colabs_externo_mensual": colabs_externo_mensual,
            # Totales combinados (para "Ambos")
            "total_colabs_anual": total_colabs_anual,
            "total_colabs_mensual": total_colabs_mensual,
        },
    )


# ==========================
# API JSON (para /docs y clientes externos)
# ==========================
@app.post("/simular")
async def simular_endpoint(
    file: UploadFile = File(...),
    anio_proyeccion: int = Form(2026),
    crecimiento_facturas: float = Form(0.05),
    crecimiento_facturacion: float = Form(0.03),
    p_interno: float = Form(0.92),
    p_externo: float = Form(0.08),
    horas_diarias_por_colaborador: float = Form(8.0),
    dias_laborales_mes: int = Form(20),
):

    contents = await file.read()
    df = pd.read_csv(io.StringIO(contents.decode("utf-8")))

    df_mensual, df_anual = simular_proyeccion(
        df,
        anio_proyeccion=anio_proyeccion,
        crecimiento_facturas=crecimiento_facturas,
        crecimiento_facturacion=crecimiento_facturacion,
        p_interno=p_interno,
        p_externo=p_externo,
        horas_diarias_por_colaborador=horas_diarias_por_colaborador,
        dias_laborales_mes=dias_laborales_mes,
    )

    return JSONResponse(
        content={
            "mensual": df_mensual.to_dict(orient="records"),
            "anual": df_anual.to_dict(orient="records"),
        }
    )
