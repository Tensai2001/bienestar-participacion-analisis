"""
Genera un dataset SINTÉTICO de asistencia a servicios de Bienestar Universitario.

Reproduce la estructura y los problemas típicos de una base real
(cargues administrativos masivos, duplicados, un área que deja de reportar),
sin contener ningún dato de personas reales.

Uso:
    python src/generar_datos_sinteticos.py
Salida:
    data/sintetico/asistencia_bienestar_sintetica.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 2026
rng = np.random.default_rng(SEMILLA)

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "sintetico" / "asistencia_bienestar_sintetica.csv"

PERIODOS = {
    # periodo: (meses del semestre, factor de crecimiento orgánico)
    "2025-1": ([2, 3, 4, 5, 6], 1.00),
    "2025-2": ([8, 9, 10, 11, 12], 1.06),
    "2026-1": ([2, 3, 4, 5, 6], 1.12),
}

# área: (registros orgánicos base por semestre, tendencia propia, actividades)
AREAS = {
    "Desarrollo Humano": (2600, 1.10, ["Asesoría psicológica", "Asesoría psicopedagógica", "Taller grupal", "Visita a aula"]),
    "Inclusión": (900, 1.15, ["Acompañamiento inclusión", "Taller de sensibilización", "Ajustes razonables"]),
    "Deportes": (3200, 1.08, ["Gimnasio", "Juegos deportivos", "Préstamo de implementos", "Selecciones"]),
    "Cultura": (1800, 1.06, ["Grupo de danza", "Grupo de música", "Taller de teatro", "Evento cultural"]),
    "Salud": (1500, 0.86, ["Consulta médica", "Jornada de salud", "Odontología"]),
    "Laboratorio Creativo": (700, 0.80, ["Taller creativo", "Hackatón", "Mentoría"]),
    "Proyección Social": (650, 0.84, ["Voluntariado", "Salida comunitaria"]),
    "Apoyo Socioeconómico": (800, 1.02, ["Asesoría socioeconómica", "Apoyo alimentario"]),
    "Bienestar Digital": (500, 1.00, ["Asesoría virtual", "Curso en línea"]),
}

# Beneficios que se registran por cargue administrativo masivo (no son asistencia real)
CARGUES_ADMIN = {
    "Beneficio matrícula cero": 0.45,
    "Auxilio de sostenimiento": 0.25,
    "Política de gratuidad": 0.30,
}
CARGUE_ADMIN_POR_PERIODO = {"2025-1": 2200, "2025-2": 3000, "2026-1": 5400}

FACULTADES = ["Ingeniería", "Producción y Diseño", "Ciencias Económicas", "Ciencias Sociales"]
JORNADAS = ["Diurna", "Nocturna"]
GENEROS = ["Femenino", "Masculino", "No binario / prefiere no decir"]
MUNICIPIOS = ["Medellín", "Bello", "Itagüí", "Envigado", "Sabaneta", "La Estrella",
              "Copacabana", "Girardota", "Caldas", "Rionegro", "Otro"]
PESOS_MUNICIPIO = [0.52, 0.12, 0.08, 0.06, 0.04, 0.03, 0.03, 0.02, 0.03, 0.03, 0.04]

N_ESTUDIANTES = 14000


def crear_estudiantes() -> pd.DataFrame:
    ids = [f"EST-{i:05d}" for i in rng.permutation(N_ESTUDIANTES)]
    return pd.DataFrame({
        "id_estudiante": ids,
        "facultad": rng.choice(FACULTADES, N_ESTUDIANTES, p=[0.42, 0.22, 0.20, 0.16]),
        "jornada": rng.choice(JORNADAS, N_ESTUDIANTES, p=[0.62, 0.38]),
        "genero": rng.choice(GENEROS, N_ESTUDIANTES, p=[0.47, 0.51, 0.02]),
        "municipio": rng.choice(MUNICIPIOS, N_ESTUDIANTES, p=PESOS_MUNICIPIO),
    })


def fechas_aleatorias(meses, anio, n):
    mes = rng.choice(meses, n)
    dia = rng.integers(1, 29, n)
    return pd.to_datetime({"year": anio, "month": mes, "day": dia})


def registros_organicos(estudiantes: pd.DataFrame) -> pd.DataFrame:
    partes = []
    # Una parte de estudiantes participa más (usuarios recurrentes)
    pesos = rng.pareto(2.5, len(estudiantes)) + 1
    pesos = pesos / pesos.sum()
    for periodo, (meses, crecimiento) in PERIODOS.items():
        anio = int(periodo[:4])
        t = list(PERIODOS).index(periodo)
        for area, (base, tendencia, actividades) in AREAS.items():
            if area == "Bienestar Digital" and periodo == "2026-1":
                continue  # el área deja de reportar: alerta de calidad de datos
            n = int(base * crecimiento * (tendencia ** t) * rng.normal(1, 0.03))
            idx = rng.choice(len(estudiantes), n, p=pesos)
            partes.append(pd.DataFrame({
                "id_estudiante": estudiantes["id_estudiante"].values[idx],
                "fecha": fechas_aleatorias(meses, anio, n),
                "periodo": periodo,
                "area": area,
                "actividad": rng.choice(actividades, n),
            }))
    return pd.concat(partes, ignore_index=True)


def registros_administrativos(estudiantes: pd.DataFrame) -> pd.DataFrame:
    partes = []
    for periodo, total in CARGUE_ADMIN_POR_PERIODO.items():
        anio = int(periodo[:4])
        mes = 3 if periodo.endswith("-1") else 9
        for beneficio, proporcion in CARGUES_ADMIN.items():
            n = int(total * proporcion)
            idx = rng.choice(len(estudiantes), n, replace=False)
            dia = int(rng.integers(5, 20))  # todo el cargue en uno o dos días
            fechas = pd.to_datetime([f"{anio}-{mes:02d}-{dia + int(rng.random() < 0.2):02d}"] * n)
            partes.append(pd.DataFrame({
                "id_estudiante": estudiantes["id_estudiante"].values[idx],
                "fecha": fechas,
                "periodo": periodo,
                "area": "Apoyo Socioeconómico",
                "actividad": beneficio,
            }))
    return pd.concat(partes, ignore_index=True)


def main():
    estudiantes = crear_estudiantes()
    df = pd.concat([registros_organicos(estudiantes), registros_administrativos(estudiantes)],
                   ignore_index=True)

    # Duplicados exactos (~1,5 %): errores típicos de digitación o doble cargue
    dup = df.sample(frac=0.015, random_state=SEMILLA)
    df = pd.concat([df, dup], ignore_index=True)

    df = df.merge(estudiantes, on="id_estudiante", how="left")
    df = df.sample(frac=1, random_state=SEMILLA).reset_index(drop=True)
    df.insert(0, "id_registro", [f"R{i:06d}" for i in range(1, len(df) + 1)])
    df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"Dataset sintético generado: {SALIDA.relative_to(RAIZ)} ({len(df):,} registros)")


if __name__ == "__main__":
    main()
