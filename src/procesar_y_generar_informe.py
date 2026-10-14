"""
Limpia la base de asistencia, separa la participación orgánica de los cargues
administrativos, calcula los indicadores y genera el informe HTML.

Uso:
    python src/procesar_y_generar_informe.py [ruta_csv]
Salida:
    docs/index.html          (informe listo para GitHub Pages)
    docs/indicadores.json    (indicadores calculados, para trazabilidad)
"""
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "data" / "sintetico" / "asistencia_bienestar_sintetica.csv"
PLANTILLA = RAIZ / "src" / "plantilla_informe.html"
SALIDA_HTML = RAIZ / "docs" / "index.html"
SALIDA_JSON = RAIZ / "docs" / "indicadores.json"

# Regla de detección de cargues masivos: un mismo día, misma área y actividad,
# con al menos UMBRAL_MINIMO registros y FACTOR veces el promedio diario del área.
UMBRAL_MINIMO = 200
FACTOR = 10

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def cargar(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, parse_dates=["fecha"])
    columnas = {"id_registro", "id_estudiante", "fecha", "periodo", "area", "actividad",
                "facultad", "jornada", "genero", "municipio"}
    faltantes = columnas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en la base: {sorted(faltantes)}")
    return df


def marcar_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    clave = ["id_estudiante", "fecha", "area", "actividad"]
    df["es_duplicado"] = df.duplicated(subset=clave, keep="first")
    return df


def marcar_cargues_masivos(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = df[~df["es_duplicado"]]
    por_dia = base.groupby(["fecha", "area", "actividad"]).size().rename("registros").reset_index()
    promedio_area = base.groupby(["area", "fecha"]).size().groupby("area").median().rename("mediana_diaria_area")
    por_dia = por_dia.merge(promedio_area, on="area")
    por_dia["es_cargue"] = (por_dia["registros"] >= UMBRAL_MINIMO) & (
        por_dia["registros"] >= FACTOR * por_dia["mediana_diaria_area"])
    cargues = por_dia[por_dia["es_cargue"]].drop(columns="es_cargue")
    df = df.merge(por_dia[["fecha", "area", "actividad", "es_cargue"]],
                  on=["fecha", "area", "actividad"], how="left")
    df["es_cargue"] = df["es_cargue"].fillna(False).astype(bool)
    df["tipo_registro"] = "Orgánico"
    df.loc[df["es_cargue"], "tipo_registro"] = "Administrativo"
    df.loc[df["es_duplicado"], "tipo_registro"] = "Duplicado"
    return df, cargues


def variacion(a, b):
    return None if not a else round((b - a) / a * 100, 1)


def calcular_indicadores(df: pd.DataFrame, cargues: pd.DataFrame) -> dict:
    periodos = sorted(df["periodo"].unique())
    p0, pn = periodos[0], periodos[-1]
    org = df[df["tipo_registro"] == "Orgánico"]

    # KPIs por periodo
    kpis = []
    for p in periodos:
        d = df[df["periodo"] == p]
        o = org[org["periodo"] == p]
        kpis.append({
            "periodo": p,
            "total_bruto": int(len(d)),
            "duplicados": int((d["tipo_registro"] == "Duplicado").sum()),
            "administrativos": int((d["tipo_registro"] == "Administrativo").sum()),
            "organicos": int(len(o)),
            "usuarios_unicos": int(o["id_estudiante"].nunique()),
            "recurrencia": round(len(o) / max(o["id_estudiante"].nunique(), 1), 2),
        })

    # Serie mensual
    df["mes"] = df["fecha"].dt.to_period("M")
    mensual = (df[df["tipo_registro"] != "Duplicado"]
               .groupby(["mes", "tipo_registro"]).size().unstack(fill_value=0).sort_index())
    serie_mensual = {
        "etiquetas": [f"{MESES[m.month - 1]} {str(m.year)[2:]}" for m in mensual.index],
        "organico": [int(v) for v in mensual.get("Orgánico", pd.Series(0, mensual.index))],
        "administrativo": [int(v) for v in mensual.get("Administrativo", pd.Series(0, mensual.index))],
    }

    # Áreas (solo orgánico)
    tabla_areas = org.groupby(["area", "periodo"]).size().unstack(fill_value=0).reindex(columns=periodos, fill_value=0)
    tabla_areas = tabla_areas.sort_values(pn, ascending=False)
    areas = [{
        "area": area,
        "valores": [int(fila[p]) for p in periodos],
        "variacion": variacion(fila[p0], fila[pn]),
    } for area, fila in tabla_areas.iterrows()]

    # Alertas de calidad de datos
    alertas = []
    for area, fila in tabla_areas.iterrows():
        if fila[pn] == 0 and fila[periodos[-2]] > 0:
            alertas.append({"nivel": "critico", "titulo": f"{area} sin registros en {pn}",
                            "detalle": f"El área reportó {int(fila[periodos[-2]]):,} registros en {periodos[-2]} y ninguno en {pn}. "
                                       "Verificar si dejó de operar o si dejó de cargar la información."})
    total_cargues = int((df["tipo_registro"] == "Administrativo").sum())
    alertas.append({"nivel": "advertencia", "titulo": f"{len(cargues)} cargues masivos detectados",
                    "detalle": f"{total_cargues:,} registros de beneficios ({', '.join(sorted(cargues['actividad'].unique()))}) "
                               "se cargaron en bloque en uno o dos días. Se excluyen de la participación orgánica."})
    total_dup = int((df["tipo_registro"] == "Duplicado").sum())
    alertas.append({"nivel": "info", "titulo": f"{total_dup:,} registros repetidos",
                    "detalle": "Mismo estudiante, misma fecha, área y actividad. Se conserva solo el primero."})

    detalle_cargues = [{
        "fecha": r.fecha.strftime("%Y-%m-%d"), "area": r.area, "actividad": r.actividad,
        "registros": int(r.registros),
    } for r in cargues.sort_values("fecha").itertuples()]

    # Perfil de usuarios del último periodo (usuarios únicos orgánicos)
    u = org[org["periodo"] == pn].drop_duplicates("id_estudiante")

    def distribucion(col, top=None):
        s = u[col].replace({"Otro": "Otros"}).value_counts()
        if top:
            s = pd.concat([s.drop("Otros", errors="ignore"), s.loc[["Otros"]] if "Otros" in s else pd.Series(dtype=int)])
            otros = s.iloc[top:].sum()
            s = s.iloc[:top].copy()
            if otros:
                s["Otros"] = otros
        return {"etiquetas": list(s.index), "valores": [int(v) for v in s.values]}

    k0, kn = kpis[0], kpis[-1]
    return {
        "periodos": periodos,
        "periodo_inicial": p0,
        "periodo_final": pn,
        "kpis": kpis,
        "resumen": {
            "crecimiento_bruto": variacion(k0["total_bruto"], kn["total_bruto"]),
            "crecimiento_organico": variacion(k0["organicos"], kn["organicos"]),
            "crecimiento_usuarios": variacion(k0["usuarios_unicos"], kn["usuarios_unicos"]),
            "porcentaje_admin_final": round(kn["administrativos"] / kn["total_bruto"] * 100, 1),
        },
        "serie_mensual": serie_mensual,
        "areas": areas,
        "alertas": alertas,
        "cargues": detalle_cargues,
        "perfil": {
            "facultad": distribucion("facultad"),
            "jornada": distribucion("jornada"),
            "municipio": distribucion("municipio", top=6),
        },
        "regla_cargue": {"umbral_minimo": UMBRAL_MINIMO, "factor": FACTOR},
    }


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else ENTRADA
    df = marcar_duplicados(cargar(ruta))
    df, cargues = marcar_cargues_masivos(df)
    indicadores = calcular_indicadores(df, cargues)

    SALIDA_HTML.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_JSON.write_text(json.dumps(indicadores, ensure_ascii=False, indent=2), encoding="utf-8")
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    html = plantilla.replace("/*__DATOS__*/null", json.dumps(indicadores, ensure_ascii=False))
    SALIDA_HTML.write_text(html, encoding="utf-8")

    r = indicadores["resumen"]
    print(f"Informe generado: {SALIDA_HTML.relative_to(RAIZ)}")
    print(f"  Crecimiento bruto: {r['crecimiento_bruto']} % | orgánico: {r['crecimiento_organico']} % "
          f"| usuarios: {r['crecimiento_usuarios']} %")
    print(f"  Cargues masivos detectados: {len(cargues)}")


if __name__ == "__main__":
    main()
