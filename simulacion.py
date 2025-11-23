# simulacion.py
import numpy as np
import pandas as pd


# =========================
# FUNCIONES DE TIEMPO
# =========================
def horas_por_factura_interno(valor, lineas):
    """
    Tiempo promedio interno según valor + líneas.
    Copiado de tu script:
      base = 0.25 si valor <= 5M
      base = 0.8  si 5M < valor <= 300M
      base = 1.5  si valor > 300M
    Ajuste por líneas: hasta +30% si supera 400 líneas.
    """
    base = 0.25 if valor <= 5_000_000 else 0.8 if valor <= 300_000_000 else 1.5
    ajuste_lineas = 1 + min(lineas / 400, 1.2) * 0.3  # máximo +30%
    return base * ajuste_lineas


def horas_por_factura_externo(valor, lineas):
    """
    Externo tarda 50% más que interno (como en tu script).
    """
    base = horas_por_factura_interno(valor, lineas)
    return base * 1.5


def simular_proyeccion(
    df: pd.DataFrame,
    anio_proyeccion: int = 2026,
    crecimiento_facturas: float = 0.05,
    crecimiento_facturacion: float = 0.03,
    p_interno: float = 0.92,
    p_externo: float = 0.08,
    horas_diarias_por_colaborador: float = 8.0,
    dias_laborales_mes: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Implementa:
      1) PARTE ANUAL: exactamente tu bloque de proyección anual.
      2) PARTE MENSUAL: tu bloque de simulación mes a mes.
    """

    # =========================
    # LIMPIEZA BÁSICA (equivalente a tu script)
    # =========================
    df = df.copy()
    df.columns = df.columns.str.strip()

    # fecha_radicacion con formato dd/mm/YYYY como en tu notebook
    df["fecha_radicacion"] = pd.to_datetime(
        df["fecha_radicacion"], format="%d/%m/%Y", errors="coerce"
    )
    df = df.dropna(subset=["fecha_radicacion"])

    # columna anio si no existe
    if "anio" not in df.columns:
        df["anio"] = df["fecha_radicacion"].dt.year

    # Limpieza de valor_factura (igual que en tu código)
    df["valor_factura"] = (
        df["valor_factura"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(".", "", regex=False)
    )
    df["valor_factura"] = pd.to_numeric(df["valor_factura"], errors="coerce")

    # cantidad_lineas a numérico
    df["cantidad_lineas"] = pd.to_numeric(df["cantidad_lineas"], errors="coerce")

    df = df.dropna(subset=["valor_factura", "cantidad_lineas", "aplicativo"])
    if df.empty:
        # DF vacíos coherentes con la UI
        df_mensual = pd.DataFrame(
            columns=[
                "anio",
                "mes",
                "aplicativo",
                "facturas_mes",
                "facturacion_mes",
                "horas_totales_mes",
                "colaboradores_necesarios_mes",
                "nombre_mes",
            ]
        )
        df_anual = pd.DataFrame(
            columns=[
                "aplicativo",
                "facturas_anuales",
                "facturacion_anual",
                "horas_totales_anuales",
                "horas_por_factura",
                "total_horas_mes_promedio",
                "colaboradores_necesarios_mes",
                "colaboradores_pico_anual",
                "anio_proyeccion",
            ]
        )
        return df_mensual, df_anual

    # =========================
    # 1) PARTE ANUAL (TU BLOQUE, CASI COPY-PASTE)
    # =========================

    # AGRUPAR POR AÑO Y APLICATIVO
    historico = (
        df.groupby(["anio", "aplicativo"])
        .agg(
            numero_factura=("numero_factura", "count"),
            valor_factura=("valor_factura", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "numero_factura": "facturas",
                "valor_factura": "facturacion",
            }
        )
    )

    # CALCULAR TENDENCIAS (aunque aquí no las usamos, las dejo igual que tu script)
    promedio_facturas = (
        historico.groupby("aplicativo")["facturas"].mean().to_dict()
    )
    promedio_facturacion = (
        historico.groupby("aplicativo")["facturacion"].mean().to_dict()
    )

    # PROYECCIÓN 2026
    proyeccion = pd.DataFrame(
        {
            "aplicativo": ["Interno", "Externo"],
            "porcentaje": [p_interno, p_externo],
        }
    )

    # Calculamos con crecimiento basado en el promedio histórico
    n_anios = historico["anio"].nunique()
    total_facturas = historico["facturas"].sum() / n_anios
    total_facturacion = historico["facturacion"].sum() / n_anios

    proyeccion["facturas_estimadas"] = (
        total_facturas * (1 + crecimiento_facturas) * proyeccion["porcentaje"]
    )
    proyeccion["facturacion_estimadas"] = (
        total_facturacion * (1 + crecimiento_facturacion) * proyeccion["porcentaje"]
    )

    # CÁLCULO DE HORAS (exactamente tu lógica)
    def calcular_horas_promedio(app: str, df_full: pd.DataFrame) -> float:
        sub = df_full[df_full["aplicativo"] == app]
        if sub.empty:
            return 0.0
        if app == "Interno":
            horas = [
                horas_por_factura_interno(v, l)
                for v, l in zip(sub["valor_factura"], sub["cantidad_lineas"])
            ]
        else:
            horas = [
                horas_por_factura_externo(v, l)
                for v, l in zip(sub["valor_factura"], sub["cantidad_lineas"])
            ]
        return float(np.mean(horas)) if len(horas) > 0 else 0.0

    promedio_interno = calcular_horas_promedio("Interno", df)
    promedio_externo = calcular_horas_promedio("Externo", df)

    proyeccion["horas_por_factura"] = [promedio_interno, promedio_externo]
    proyeccion["total_horas_mes"] = (
        proyeccion["facturas_estimadas"] / 12.0 * proyeccion["horas_por_factura"]
    )

    # CAPACIDAD OPERATIVA
    capacidad_colaborador_mes = horas_diarias_por_colaborador * dias_laborales_mes
    if capacidad_colaborador_mes > 0:
        proyeccion["colaboradores_necesarios"] = np.ceil(
            proyeccion["total_horas_mes"] / capacidad_colaborador_mes
        )
    else:
        proyeccion["colaboradores_necesarios"] = 0.0

    # Construimos df_anual con los campos que usa el template
    anual_records = []
    for _, row in proyeccion.iterrows():
        app = row["aplicativo"]
        facturas_anuales = float(row["facturas_estimadas"])
        facturacion_anual = float(row["facturacion_estimadas"])
        horas_pf = float(row["horas_por_factura"])
        horas_mes = float(row["total_horas_mes"])
        colabs_mes = float(row["colaboradores_necesarios"])
        horas_anuales = facturas_anuales * horas_pf

        anual_records.append(
            {
                "aplicativo": app,
                "facturas_anuales": facturas_anuales,
                "facturacion_anual": facturacion_anual,
                "horas_totales_anuales": horas_anuales,
                "horas_por_factura": horas_pf,
                "total_horas_mes_promedio": horas_mes,
                "colaboradores_necesarios_mes": colabs_mes,
                # pico anual lo llenamos después con la simulación mensual
                "colaboradores_pico_anual": colabs_mes,
                "anio_proyeccion": anio_proyeccion,
            }
        )

    df_anual = pd.DataFrame(anual_records)

    # =========================
    # 2) PARTE MENSUAL (tu bloque de simulación mes a mes)
    # =========================

    # PROMEDIOS HISTÓRICOS
    df["mes"] = df["fecha_radicacion"].dt.month
    historico_mensual = (
        df.groupby(["anio", "mes", "aplicativo"])
        .agg(
            numero_factura=("numero_factura", "count"),
            valor_factura=("valor_factura", "sum"),
            cantidad_lineas=("cantidad_lineas", "mean"),
        )
        .reset_index()
        .rename(
            columns={
                "numero_factura": "facturas",
                "valor_factura": "facturacion",
            }
        )
    )

    promedios = (
        historico_mensual.groupby("aplicativo")
        .agg(
            facturas=("facturas", "mean"),
            facturacion=("facturacion", "mean"),
            cantidad_lineas=("cantidad_lineas", "mean"),
        )
        .reset_index()
    )

    meses = range(1, 13)
    resultados = []

    for app in ["Interno", "Externo"]:
        row_app = promedios[promedios["aplicativo"] == app]
        if row_app.empty:
            continue

        prom_f = row_app["facturas"].values[0]
        prom_v = row_app["facturacion"].values[0]
        prom_l = row_app["cantidad_lineas"].values[0]

        # Ajuste por porcentaje de aplicativo y crecimiento anual
        factor = p_interno if app == "Interno" else p_externo
        prom_f = prom_f * (1 + crecimiento_facturas) * factor
        prom_v = prom_v * (1 + crecimiento_facturacion) * factor

        for mes in meses:
            # Simulamos facturas y facturación mensualmente
            facturas_mes = int(prom_f * np.random.uniform(0.95, 1.05))  # +/-5%
            facturas_mes = max(facturas_mes, 0)

            if facturas_mes > 0:
                facturacion_mes = prom_v * np.random.uniform(0.95, 1.05)
            else:
                facturacion_mes = 0.0

            # Estimación de horas promedio por factura
            horas = []
            if facturas_mes > 0:
                valor_prom = facturacion_mes / max(facturas_mes, 1)
                hi = max(5_000, valor_prom * 1.5)

                for _ in range(facturas_mes):
                    valor = np.random.uniform(5_000, hi)
                    lineas = max(
                        1, int(np.random.normal(prom_l, prom_l * 0.3))
                    )  # desviación 30 %
                    if app == "Interno":
                        horas.append(horas_por_factura_interno(valor, lineas))
                    else:
                        horas.append(horas_por_factura_externo(valor, lineas))

            total_horas = float(sum(horas))
            denom = horas_diarias_por_colaborador * dias_laborales_mes
            colaboradores_necesarios = (
                float(np.ceil(total_horas / denom)) if denom > 0 else 0.0
            )

            resultados.append(
                {
                    "anio": anio_proyeccion,
                    "mes": mes,
                    "aplicativo": app,
                    "facturas": facturas_mes,
                    "facturacion": facturacion_mes,
                    "horas_totales": total_horas,
                    "colaboradores_necesarios": colaboradores_necesarios,
                }
            )

    df_proyeccion = pd.DataFrame(resultados)

    # =========================
    # SALIDA MENSUAL (df_mensual)
    # =========================
    mes_map = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }

    if df_proyeccion.empty:
        df_mensual = pd.DataFrame(
            columns=[
                "anio",
                "mes",
                "aplicativo",
                "facturas_mes",
                "facturacion_mes",
                "horas_totales_mes",
                "colaboradores_necesarios_mes",
                "nombre_mes",
            ]
        )
    else:
        df_mensual = df_proyeccion.rename(
            columns={
                "facturas": "facturas_mes",
                "facturacion": "facturacion_mes",
                "horas_totales": "horas_totales_mes",
                "colaboradores_necesarios": "colaboradores_necesarios_mes",
            }
        )
        df_mensual["nombre_mes"] = df_mensual["mes"].map(mes_map)

    # Actualizamos pico anual en df_anual con el máximo de la simulación
    if not df_proyeccion.empty:
        picos = (
            df_proyeccion.groupby("aplicativo")["colaboradores_necesarios"]
            .max()
            .to_dict()
        )
        df_anual["colaboradores_pico_anual"] = df_anual["aplicativo"].map(
            lambda app: float(
                picos.get(
                    app,
                    df_anual.loc[
                        df_anual["aplicativo"] == app, "colaboradores_necesarios_mes"
                    ].iloc[0],
                )
            )
        )

    return df_mensual, df_anual
