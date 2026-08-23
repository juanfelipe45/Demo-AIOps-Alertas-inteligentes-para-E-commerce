# Demo AIOps — Alertas inteligentes para E-commerce

Prototipo académico desarrollado para demostrar un pipeline AIOps orientado a la reducción de ruido operacional y la detección inteligente de anomalías en una plataforma de comercio electrónico.

La aplicación es autocontenida: genera datos simulados, aplica diferentes mecanismos de detección, compara sus resultados y ejecuta un flujo completo de deduplicación, correlación y generación de incidentes enriquecidos.

## Objetivo del demo

El escenario parte de una plataforma de e-commerce compuesta por varios servicios y de una problemática operacional con alto volumen de alertas y falsos positivos.

El demo permite observar cómo un enfoque AIOps puede complementar las reglas tradicionales mediante:

- detección dinámica de anomalías;
- comparación de distintos mecanismos de detección;
- deduplicación de alertas repetidas;
- correlación de señales del mismo servicio;
- generación de incidentes con contexto enriquecido;
- estimación del impacto sobre el volumen de alertas y el MTTR.

## Arquitectura funcional

El pipeline implementado sigue seis etapas:

```text
Señal raw
   ↓
Agregación
   ↓
Detección de anomalías
   ↓
Deduplicación
   ↓
Correlación
   ↓
Notificación enriquecida
```

Las señales simuladas incluyen:

- latencia;
- tasa de errores;
- throughput;
- CPU;
- memoria.

Los servicios simulados son:

- `catalog`;
- `cart`;
- `inventory`;
- `orders`;
- `payments`.

## Mecanismos de detección

La aplicación compara cuatro enfoques:

### Umbral estático

Representa el esquema tradicional de alertamiento mediante valores fijos.

### Z-score dinámico

Es la regla principal del prototipo. Calcula la desviación de cada observación frente a una ventana histórica reciente.

La lógica general es:

```text
z = (valor_actual - media) / desviación_estándar
```

Para reducir picos aislados, la anomalía debe persistir en al menos 2 de las últimas 3 muestras.

### CUSUM

Detecta cambios pequeños pero persistentes mediante acumulación de desviaciones respecto a una referencia.

### Isolation Forest

Algoritmo no supervisado utilizado para detectar comportamientos anómalos a partir de varias métricas simultáneamente.

## Métricas de evaluación

Todos los detectores se evalúan sobre el mismo conjunto de datos simulado y etiquetado.

La aplicación calcula:

- precisión;
- recall;
- F1-score;
- falsos positivos;
- número total de alertas;
- MTTD estimado dentro de la simulación.

## Reglas de deduplicación y correlación

El demo implementa reglas simples y explicables:

1. Las alertas del mismo `servicio + métrica` generadas dentro de una ventana de 5 minutos se agrupan.
2. Si un servicio presenta anomalías en 2 o más métricas dentro de la misma ventana, se genera un único incidente correlacionado.
3. Determinadas combinaciones elevan la severidad del incidente.
4. Las alertas individuales que forman parte de un incidente correlacionado se consideran suprimidas downstream.

Ejemplo:

```text
payments
 ├─ latencia alta
 ├─ tasa de errores alta
 ├─ throughput bajo
 └─ CPU anómala

        ↓

Incidente CRITICAL:
Posible degradación del servicio de pagos
```

## Tecnologías utilizadas

- **Python**: lógica del prototipo.
- **Streamlit**: interfaz web.
- **Pandas**: manipulación de series temporales.
- **NumPy**: generación y cálculo numérico.
- **scikit-learn**: implementación de Isolation Forest y métricas.
- **Plotly**: visualizaciones interactivas.

## Requisitos

- Python 3.10 o superior.
- Windows, macOS o Linux.
- Conexión a Internet únicamente durante la instalación inicial de dependencias.

No se requiere:

- Docker;
- base de datos;
- infraestructura cloud;
- servicios externos.

## Instalación y ejecución

### Opción 1 — Windows mediante script

Desde la carpeta del proyecto ejecuta:

```bat
run_windows.bat
```

El script:

1. crea el entorno virtual `.venv`;
2. instala las dependencias;
3. inicia la aplicación con Streamlit.

Después se abrirá la aplicación en el navegador, normalmente en:

```text
http://localhost:8501
```

## Opción 2 — Ejecución manual en Windows

Abre CMD o PowerShell en la carpeta del proyecto.

### 1. Crear el entorno virtual

```powershell
py -m venv .venv
```

### 2. Activarlo

En CMD:

```cmd
.venv\Scripts\activate
```

En PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la ejecución:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación

```powershell
streamlit run app.py
```

## Ejecución en macOS o Linux

### 1. Crear entorno virtual

```bash
python3 -m venv .venv
```

### 2. Activarlo

```bash
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Ejecutar

```bash
streamlit run app.py
```

## Prueba rápida del motor

El proyecto incluye `smoke_test.py` para validar que los componentes principales funcionan correctamente.

Con el entorno virtual activo:

```bash
python smoke_test.py
```

Una ejecución correcta debe terminar mostrando:

```text
OK
```

junto con el número de observaciones, alertas y eventos correlacionados generados.

## Uso de la aplicación

La interfaz contiene varias pestañas:

### Resumen

Presenta la línea base del caso, el volumen de eventos generado por el pipeline y una estimación de impacto.

### Señales

Permite explorar las métricas simuladas por servicio y visualizar los incidentes introducidos en el escenario.

### Comparación de detectores

Compara cuantitativamente los mecanismos de detección mediante precisión, recall, F1, falsos positivos y MTTD.

### Pipeline

Muestra las seis etapas del flujo AIOps y la reducción del volumen de eventos después de deduplicación y correlación.

### Incidentes

Presenta las notificaciones enriquecidas resultantes, incluyendo:

- servicio afectado;
- severidad;
- métricas correlacionadas;
- posible causa.

### Herramientas AIOps

Resume alternativas comerciales o nativas de nube consideradas como referencia para una implementación productiva.

### Cobertura de la rúbrica

Relaciona las capacidades del demo con los objetivos académicos del ejercicio.

## Parámetros configurables

Desde la barra lateral se pueden modificar:

- semilla de generación;
- cantidad de horas simuladas;
- umbral Z-score;
- tamaño de la ventana histórica;
- ventana de deduplicación;
- número mínimo de métricas necesarias para correlacionar;
- supuesto de reducción del MTTR.

Modificar estos valores permite observar cómo cambia la sensibilidad del detector y el número de incidentes generados.

## Consideraciones

Este proyecto es un **prototipo académico**.

Los datos son simulados y los incidentes se introducen de forma controlada para permitir la evaluación de los algoritmos. Por esta razón:

- los resultados no representan métricas de un sistema productivo;
- la reducción de ruido medida corresponde al escenario simulado;
- la reducción de MTTR mostrada por la aplicación es una estimación basada en un supuesto configurable.

El objetivo del demo es demostrar que el pipeline y las reglas propuestas son implementables y permiten comparar de forma reproducible distintos mecanismos de detección.
