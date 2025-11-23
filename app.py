# app.py
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from simulacion import simular_proyeccion  # lógica principal

app = FastAPI(title="Simulador de Proyección de Facturación y RRHH")

# ==========================
# CORS (útil si luego llamas desde un frontend separado)
# ==========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción puedes restringir dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carpeta de templates HTML
templates = Jinja2Templates(directory="templates")


@app.get("/")
def root():
    return {
        "message": (
            "API de simulación de facturación y colaboradores activa. "
            "Usa /form para el front, /simulation (POST) para ver resultados en página, "
            "o /docs para la interfaz de API."
        )
    }


# Página del formulario (usa templates/form.html)
@app.get("/form", response_class=HTMLResponse)
def form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})
@app.post("/simulation", response_class=HTMLResponse)
async def simulation_page(
    request: Request,
    file: UploadFile = File(...),
    anio_proyeccion: int = Form(2026),
    crecimiento_facturas: float = Form(0.05),
    crecimiento_facturacion: float = Form(0.08),
    p_interno: float = Form(0.6),
    p_externo: float = Form(0.4),
    horas_diarias_por_colaborador: float = Form(8.0),
    dias_laborales_mes: int = Form(22),
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
    # AHORA: usamos SOLO df_anual (que viene de tu bloque "proyeccion")
    #   - colaboradores_necesarios_mes  → lo que en tu script es "Colaboradores requeridos"
    #   - colaboradores_pico_anual      → viene de la simulación mensual (pico del año)

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




# API pura JSON (útil para /docs o clientes externos)
@app.post("/simular")
async def simular_endpoint(
    file: UploadFile = File(...),
    anio_proyeccion: int = Form(2026),
    crecimiento_facturas: float = Form(0.05),
    crecimiento_facturacion: float = Form(0.08),
    p_interno: float = Form(0.6),
    p_externo: float = Form(0.4),
    horas_diarias_por_colaborador: float = Form(8.0),
    dias_laborales_mes: int = Form(22),
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
