# Demo AIOps — Alertas inteligentes para E-commerce

Prototipo académico autocontenido para demostrar un pipeline AIOps de alertas inteligentes.

## Qué demuestra

1. Generación de señales simuladas de un e-commerce con cinco microservicios.
2. Estacionalidad normal y un pico legítimo de negocio, además de incidentes controlados.
3. Comparación de cuatro mecanismos: umbrales estáticos, Z-score dinámico, CUSUM e Isolation Forest.
4. Métricas cuantitativas: precisión, recall, F1, falsos positivos y MTTD.
5. Pipeline completo: señal raw → agregación → anomaly detection → deduplicación → correlación → notificación enriquecida.
6. Estimación del impacto sobre alert fatigue y MTTR.

## Requisitos

- Python 3.10 o superior.
- Windows, macOS o Linux.
- No requiere nube, base de datos ni servicios externos.

## Ejecución rápida en Windows

Puedes hacer doble clic en `run_windows.bat`. La primera ejecución crea un entorno virtual, instala las dependencias y abre la app.

O desde PowerShell:

```powershell
cd aiops_ecommerce_demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Si PowerShell bloquea la activación:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Ejecución en macOS/Linux

```bash
cd aiops_ecommerce_demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Evidencias recomendadas para el informe

Toma capturas de estas pestañas:

1. **Resumen**: línea base y reducción del ruido.
2. **Comparación de detectores**: tabla con precisión, recall, F1, falsos positivos y MTTD.
3. **Pipeline**: las seis etapas y el funnel de reducción.
4. **Incidentes**: una notificación enriquecida de `payments`.

## Regla principal del prototipo

La regla AIOps implementada usa Z-score con ventana móvil:

- latencia, tasa de error y CPU: anomalía si `z > umbral`;
- throughput: anomalía si `z < -umbral`;
- persistencia: 2 de las últimas 3 muestras;
- deduplicación: mismo servicio y métrica dentro de 5 minutos;
- correlación: varias métricas anómalas del mismo servicio dentro de la misma ventana;
- salida: una alerta enriquecida con servicio, severidad, métricas y causa sugerida.

## Nota académica sobre MTTR

La reducción de MTTR mostrada en la aplicación es una **estimación explícita basada en un supuesto configurable**. No debe presentarse como un resultado experimental medido.
