# ¿Cuánto creció realmente la participación en Bienestar?

Análisis de participación en servicios de Bienestar Universitario que **separa la asistencia real de los cargues administrativos de beneficios**, con un informe HTML que se genera automáticamente desde la base de datos.

**[Ver el informe en vivo](https://Tensai2001.github.io/bienestar-participacion-analisis/)**

> Todos los datos de este repositorio son **sintéticos**. Reproducen la estructura y los problemas de una base real, pero no corresponden a ninguna institución ni a personas reales.

---

## El problema

Las bases de asistencia de Bienestar suelen mezclar dos cosas distintas:

- **Participación orgánica:** un estudiante que asiste a una asesoría, un taller o al gimnasio.
- **Registros administrativos:** beneficios (matrícula cero, gratuidad, auxilios) que se cargan en bloque al inicio de cada semestre.

Si se reportan juntos, aparecen picos en marzo y septiembre que parecen éxitos de convocatoria, y el crecimiento anual se sobreestima.

## El hallazgo

| Indicador (2025-1 → 2026-1) | Resultado |
|---|---|
| Crecimiento según la base completa | **+35,7 %** |
| Crecimiento de la participación orgánica | **+16,8 %** |
| Crecimiento de usuarios únicos | +8,1 % |
| Registros administrativos en 2026-1 | 26,2 % del total |

Más de la mitad del crecimiento reportado venía de cargues de beneficios. Además, el análisis detecta un área que dejó de reportar registros y 790 registros repetidos.

## Cómo funciona

```
data/sintetico/*.csv
        │
        ▼
src/procesar_y_generar_informe.py
  1. Valida las columnas de la base
  2. Marca registros repetidos (mismo estudiante, fecha, área y actividad)
  3. Detecta cargues masivos (≥ 200 registros en un día y ≥ 10× la mediana diaria del área)
  4. Calcula indicadores, alertas de calidad y perfil de usuarios
        │
        ├──► docs/indicadores.json   (trazabilidad de cada cifra)
        └──► docs/index.html         (informe con Chart.js, publicado en GitHub Pages)
```

Las conclusiones del informe se redactan a partir de los datos, así que al cambiar la base el informe se actualiza solo.

## Ejecutarlo

```bash
pip install -r requirements.txt
python src/generar_datos_sinteticos.py      # crea el dataset sintético
python src/procesar_y_generar_informe.py    # genera docs/index.html
```

Para usar otra base con la misma estructura:

```bash
python src/procesar_y_generar_informe.py ruta/a/mi_base.csv
```

Columnas esperadas: `id_registro, id_estudiante, fecha, periodo, area, actividad, facultad, jornada, genero, municipio`.

## Estructura

```
├── data/sintetico/     Dataset sintético (52.930 registros)
├── docs/               Informe generado (GitHub Pages)
├── src/
│   ├── generar_datos_sinteticos.py
│   ├── procesar_y_generar_informe.py
│   └── plantilla_informe.html
└── requirements.txt
```

## Herramientas

Python (pandas, NumPy) · HTML/CSS · Chart.js · GitHub Pages

## Próximos pasos

- Cruzar la participación con la permanencia del semestre siguiente para medir impacto.
- Proponer en la fuente un campo de **origen del registro** (asistencia o beneficio) y así no depender de reglas de detección.

---

**Autor:** Daniel Rueda B. · Analista de datos en bienestar y permanencia estudiantil
