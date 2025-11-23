# generator.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# DataFrame de prestadores (se crea dentro de generar_dataset)
prestadores = None


# ======================
# FUNCIÓN PARA FECHAS
# ======================
def generar_fecha_radicacion(anio: int) -> str:
    """
    Genera una fecha de radicación dentro del año dado, con distribución
    semanal aproximada: 16%, 23%, 24%, 37%.
    """
    # Distribución semanal: 16%, 23%, 24%, 37%
    semanas = [0.16, 0.23, 0.24, 0.37]
    mes = random.randint(1, 12)

    # Número de días del mes
    dias_mes = (datetime(anio if mes < 12 else anio + 1, (mes % 12) + 1, 1) - timedelta(days=1)).day

    # Elegir semana
    semana = np.random.choice([1, 2, 3, 4], p=semanas)
    if semana == 1:
        dia = random.randint(1, dias_mes // 4)
    elif semana == 2:
        dia = random.randint(dias_mes // 4 + 1, dias_mes // 2)
    elif semana == 3:
        dia = random.randint(dias_mes // 2 + 1, int(3 * dias_mes / 4))
    else:
        dia = random.randint(int(3 * dias_mes / 4) + 1, dias_mes)

    return datetime(anio, mes, min(dia, dias_mes)).strftime("%d/%m/%Y")


# ======================
# FUNCIÓN PARA VALOR DE FACTURA
# ======================
def generar_valor_factura() -> int:
    """
    Genera un valor de factura con distribución:
      - 65% hasta 5 millones
      - 35% entre 5 y 800 millones
    """
    if np.random.rand() < 0.65:
        # 65% hasta 5 millones
        return random.randint(5_000, 5_000_000)
    else:
        # 35% entre 5 y 800 millones
        valor = random.randint(5_000_001, 800_000_000)
        return valor


# ======================
# FUNCIÓN TIPO DE FACTURA
# ======================
def generar_tipo_factura() -> str:
    tipos = ["Salud básica", "Salud media", "Salud compleja", "Transporte"]
    probabilidades = [0.45, 0.30, 0.15, 0.10]
    return np.random.choice(tipos, p=probabilidades)


# ======================
# FUNCIÓN CANTIDAD DE LÍNEAS
# ======================
def generar_cantidad_lineas(tipo_factura: str) -> int:
    p = np.random.rand()

    if tipo_factura == "Transporte":
        if p < 0.9:
            return random.randint(1, 5)
        else:
            return random.randint(6, 50)

    elif tipo_factura == "Salud básica":
        if p < 0.9:
            return random.randint(1, 200)
        elif p < 0.99:
            return random.randint(201, 800)
        else:
            return random.randint(801, 1200)

    elif tipo_factura == "Salud media":
        if p < 0.7:
            return random.randint(50, 300)
        elif p < 0.99:
            return random.randint(301, 800)
        else:
            return random.randint(801, 1200)

    else:  # Salud compleja
        if p < 0.6:
            return random.randint(100, 400)
        elif p < 0.99:
            return random.randint(401, 800)
        else:
            return random.randint(801, 1200)


# ======================
# FUNCIÓN PARA GENERAR FACTURAS DE UN AÑO
# ======================
def generar_facturas_por_anio(anio: int, total_registros: int, total_facturacion: float) -> pd.DataFrame:
    """
    Genera un DataFrame con facturas sintéticas para un año dado.
    - Usa el DataFrame global 'prestadores' para seleccionar el prestador.
    - Ajusta los valores de las facturas para que la suma sea 'total_facturacion'.
    """
    global prestadores

    if prestadores is None or prestadores.empty:
        raise ValueError("El DataFrame 'prestadores' no ha sido inicializado.")

    facturas = []

    for i in range(total_registros):
        # Elegir prestador basado en peso de facturación
        prestador = prestadores.sample(weights=prestadores["peso_facturacion"], n=1).iloc[0]
        id_prestador = prestador["id_prestador"]
        nombre = prestador["nombre_prestador"]

        # Regla de aplicativo
        if prestador["tipo"] == "Interno":
            aplicativo = "Interno"
        else:
            aplicativo = np.random.choice(["Interno", "Externo"], p=[0.95, 0.05])

        tipo_factura = generar_tipo_factura()
        cantidad_lineas = generar_cantidad_lineas(tipo_factura)

        factura = {
            "anio": anio,
            "id_prestador": id_prestador,
            "nombre_prestador": nombre,
            "numero_factura": f"FAC-{anio}-{i+1:06d}",
            "fecha_radicacion": generar_fecha_radicacion(anio),
            "valor_factura": generar_valor_factura(),
            "aplicativo": aplicativo,
            "tipo_factura": tipo_factura,
            "cantidad_lineas": cantidad_lineas,
        }
        facturas.append(factura)

    df = pd.DataFrame(facturas)

    # Escalar valores de factura para que la suma coincida con total_facturacion
    factor = total_facturacion / df["valor_factura"].sum()
    df["valor_factura"] = (df["valor_factura"] * factor).round(0)

    return df


# ======================
# FUNCIÓN ORQUESTADORA: GENERAR DATASET MULTIAÑO
# ======================
def generar_dataset(
        anio_inicio: int,
        anio_fin: int,
        total_facturas_inicial: int,
        total_facturacion_inicial: float,
        total_prestadores: int,
        total_prestadores_solo_interno: int,
        seed: int = 42,
        max_crec_facturas: float = 0.05,
        max_crec_facturacion: float = 0.03,
    ) -> pd.DataFrame:
    """
    Genera un dataset sintético de facturación para varios años consecutivos.

    - anio_inicio, anio_fin: rango de años (incluyendo ambos).
    - total_facturas_inicial: número de facturas del primer año.
    - total_facturacion_inicial: facturación total del primer año.
    - total_prestadores: número total de prestadores.
    - total_prestadores_solo_interno: prestadores que solo facturan como 'Interno'.
    - seed: semilla aleatoria para reproducibilidad.
    - max_crec_facturas: máximo crecimiento anual relativo en número de facturas.
    - max_crec_facturacion: máximo crecimiento anual relativo en facturación.
    """

    global prestadores

    # Semilla para reproducibilidad
    np.random.seed(seed)
    random.seed(seed)

    # Crear DataFrame de prestadores
    prestadores = pd.DataFrame({
        "id_prestador": np.arange(900000001, 900000001 + total_prestadores),
        "nombre_prestador": [f"PRESTADOR_{i:04d}" for i in range(1, total_prestadores + 1)],
    })

    # Marcar prestadores "solo interno" y "mixtos"
    prestadores["tipo"] = "Mixto"
    prestadores.loc[: total_prestadores_solo_interno - 1, "tipo"] = "Interno"

    # Distribución Pareto simple: unos pocos concentran la mayoría de la facturación
    prestadores["peso_facturacion"] = 0.2  # el 20% de la facturación
    top_n = min(100, total_prestadores)    # por defecto, primeros 100
    prestadores.loc[: top_n - 1, "peso_facturacion"] = 0.8  # 80% de la facturación

    # Bucle por años
    df_total = pd.DataFrame()
    facturas_anio = float(total_facturas_inicial)
    facturacion_anio = float(total_facturacion_inicial)

    for anio in range(anio_inicio, anio_fin + 1):
        # Generar datos de ese año
        df_anio = generar_facturas_por_anio(
            anio=anio,
            total_registros=int(round(facturas_anio)),
            total_facturacion=facturacion_anio,
        )
        df_total = pd.concat([df_total, df_anio], ignore_index=True)

        # Actualizar facturas y facturación para el siguiente año
        crecimiento_facturas = np.random.uniform(0.0, max_crec_facturas)
        crecimiento_facturacion = np.random.uniform(0.0, max_crec_facturacion)

        facturas_anio *= (1 + crecimiento_facturas)
        facturacion_anio *= (1 + crecimiento_facturacion)

    return df_total
