import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from aiops_demo import (
    SERVICES, METRICS, generate_dataset, detect_static, detect_zscore,
    detect_cusum, detect_isolation_forest, build_alerts,
    deduplicate_alerts, correlate_alerts, evaluate_method,
    detection_delay_minutes, impact_summary,
)

st.set_page_config(page_title="AIOps E-commerce Demo", page_icon="📈", layout="wide")
st.title("Demo AIOps — Alertas inteligentes para E-commerce")
st.caption("Prototipo académico de detección dinámica, deduplicación, correlación y notificación enriquecida.")

with st.sidebar:
    st.header("Escenario")
    seed = st.number_input("Semilla", 1, 9999, 42, 1)
    hours = st.slider("Horas simuladas", 8, 48, 24)
    z_threshold = st.slider("Umbral |Z|", 2.0, 4.5, 2.7, 0.1)
    rolling_window = st.slider("Ventana Z-score (min)", 15, 120, 60, 5)
    dedup_window = st.slider("Ventana de deduplicación (min)", 1, 15, 5)
    min_corr_metrics = st.slider("Métricas mínimas para correlación", 2, 4, 2)
    mttr_reduction = st.slider("Supuesto de reducción de MTTR (%)", 10, 60, 30, 5,
        help="Estimación explícita para el informe; no es una medición real.")
    if st.button("Regenerar escenario", use_container_width=True):
        st.cache_data.clear()

@st.cache_data(show_spinner=False)
def load_data(seed_value, hours_value):
    return generate_dataset(seed=int(seed_value), hours=int(hours_value))

df = load_data(seed, hours)
static_flags = detect_static(df)
z_flags = detect_zscore(df, window=rolling_window, threshold=z_threshold)
cusum_flags = detect_cusum(df)
iso_flags = detect_isolation_forest(df, seed=seed)

methods = {"Umbral estático": static_flags, "Z-score dinámico": z_flags, "CUSUM": cusum_flags, "Isolation Forest": iso_flags}
rows=[]
for name,flags in methods.items():
    ev=evaluate_method(df,flags); ev["Método"]=name; ev["MTTD (min)"]=detection_delay_minutes(df,flags); rows.append(ev)
eval_df=pd.DataFrame(rows)[["Método","Precisión","Recall","F1","Falsos positivos","Alertas","MTTD (min)"]]

raw_alerts = build_alerts(df, z_flags, window=rolling_window, threshold=z_threshold)
dedup_alerts = deduplicate_alerts(raw_alerts, window_minutes=dedup_window)
incidents = correlate_alerts(dedup_alerts, min_metrics=min_corr_metrics, correlation_window_minutes=dedup_window)
impact = impact_summary(demo_raw_alerts=len(raw_alerts), demo_incidents=len(incidents), mttr_reduction_assumption=mttr_reduction/100)

t1,t2,t3,t4,t5,t6,t7 = st.tabs(["Resumen","Señales","Comparación de detectores","Pipeline","Incidentes","Herramientas AIOps","Cobertura de la rúbrica"])

with t1:
    st.subheader("Línea base del caso")
    a,b,c,d=st.columns(4)
    a.metric("Alertas/día","800"); b.metric("Falsos positivos","72 %"); c.metric("Falsos positivos/día","576"); d.metric("MTTR actual","3,5 h")
    st.subheader("Resultado del pipeline del demo")
    a,b,c,d=st.columns(4)
    a.metric("Alertas raw (Z-score)",len(raw_alerts))
    b.metric("Después de deduplicar",len(dedup_alerts))
    c.metric("Incidentes correlacionados",len(incidents))
    d.metric("Reducción del ruido del demo",f"{impact['demo_noise_reduction_pct']:.1f} %")
    st.info("Objetivo de la actividad: reducir el alert fatigue al menos 60 %. El porcentaje del demo compara eventos raw contra incidentes finales correlacionados.")
    st.subheader("Estimación de impacto para 800 alertas/día")
    a,b,c=st.columns(3)
    a.metric("Falsos positivos objetivo/día",f"{impact['target_false_positives_per_day']:.0f}",delta=f"-{impact['false_positives_removed_per_day']:.0f}")
    b.metric("Falsos positivos evitados/mes",f"{impact['false_positives_removed_per_month']:.0f}")
    c.metric("MTTR estimado",f"{impact['estimated_mttr_hours']:.2f} h",delta=f"-{impact['mttr_minutes_saved']:.0f} min")
    st.caption("La reducción de MTTR es una estimación basada en el supuesto elegido y no debe presentarse como medición experimental.")

with t2:
    st.subheader("Métricas simuladas")
    svc=st.selectbox("Servicio",SERVICES,index=SERVICES.index("payments"))
    metric=st.selectbox("Métrica",list(METRICS),format_func=lambda x:METRICS[x]["label"])
    s=df[df.service==svc]
    fig=px.line(s,x="timestamp",y=metric,title=f"{svc} — {METRICS[metric]['label']}")
    pts=s[s.is_incident]
    if not pts.empty:
        fig.add_trace(go.Scatter(x=pts.timestamp,y=pts[metric],mode="markers",name="Incidente inyectado",marker=dict(size=6,symbol="x")))
    fig.update_layout(legend_orientation="h")
    st.plotly_chart(fig,use_container_width=True)
    st.caption("El escenario incluye estacionalidad y un pico legítimo de negocio, además de incidentes controlados. is_incident sirve como verdad terreno para evaluar los detectores.")
    st.subheader("Regla AIOps implementada")
    st.code("""Cada minuto, por servicio y métrica:
1. Tomar una ventana móvil de N minutos.
2. Calcular media (μ) y desviación estándar (σ).
3. Calcular z = (valor_actual - μ) / σ.
4. Marcar anomalía:
   - latencia, errores o CPU: z > umbral
   - throughput: z < -umbral
5. Exigir persistencia: 2 de las últimas 3 muestras.
6. Deduplicar eventos del mismo servicio/métrica en 5 min.
7. Correlacionar varias métricas del mismo servicio.
8. Generar una sola notificación enriquecida.""",language="text")

with t3:
    st.subheader("Evaluación cuantitativa")
    st.dataframe(eval_df.style.format({"Precisión":"{:.3f}","Recall":"{:.3f}","F1":"{:.3f}","MTTD (min)":"{:.1f}"}),use_container_width=True,hide_index=True)
    st.caption("Los resultados se calculan sobre los mismos datos simulados y etiquetados para todos los métodos.")
    choice=st.radio("Métrica para comparar",["F1","Precisión","Recall","Falsos positivos"],horizontal=True)
    st.plotly_chart(px.bar(eval_df,x="Método",y=choice,text_auto=".2f"),use_container_width=True)
    st.markdown("""
- **Umbral estático:** simple, pero sensible a variaciones normales.
- **Z-score dinámico:** explicable y adecuado para el prototipo.
- **CUSUM:** útil para cambios pequeños y persistentes.
- **Isolation Forest:** multivariable, pero más complejo de explicar y ajustar.
""")

with t4:
    st.subheader("Pipeline AIOps implementado")
    stages=[
        ("1. Señal raw","Latencia, errores, throughput, CPU y memoria"),
        ("2. Agregación","Ventanas móviles por servicio"),
        ("3. Anomaly Detection","Z-score dinámico"),
        ("4. Deduplicación",f"Mismo servicio/métrica en {dedup_window} min"),
        ("5. Correlación",f"≥ {min_corr_metrics} métricas anómalas del mismo servicio"),
        ("6. Notificación","Servicio, evidencia, severidad y posible causa"),
    ]
    for i,(name,detail) in enumerate(stages):
        st.markdown(f"**{name}**  \n{detail}")
        if i<len(stages)-1: st.markdown("↓")
    st.subheader("Volumen a través del pipeline")
    volume=pd.DataFrame({"Etapa":["Alertas raw","Deduplicadas","Incidentes correlacionados"],"Eventos":[len(raw_alerts),len(dedup_alerts),len(incidents)]})
    st.plotly_chart(px.funnel(volume,y="Etapa",x="Eventos"),use_container_width=True)

with t5:
    st.subheader("Notificaciones enriquecidas")
    if not incidents:
        st.warning("No se generaron incidentes correlacionados con estos parámetros. Baja el umbral Z o el número mínimo de métricas.")
    for inc in incidents[:12]:
        if inc["severity"]=="CRITICAL": st.error(inc["message"])
        elif inc["severity"]=="HIGH": st.warning(inc["message"])
        else: st.info(inc["message"])
        with st.expander("Ver detalle"): st.json(inc)
    st.subheader("Reglas de deduplicación, correlación y supresión")
    st.markdown(f"""
1. Alertas del mismo **servicio + métrica** dentro de **{dedup_window} min** se agrupan.
2. Si un servicio tiene anomalías en **{min_corr_metrics} o más métricas** en la misma ventana, se crea un único incidente.
3. En `payments`, latencia alta + errores altos + throughput bajo eleva la severidad.
4. Las alertas individuales incluidas en un incidente correlacionado se consideran **suprimidas downstream**.
""")

with t6:
    st.subheader("Evaluación de herramientas AIOps")
    st.caption("Precios de referencia consultados en fuentes oficiales en agosto de 2026; pueden cambiar. La comparación usa unidades de cobro publicadas, no un costo mensual inventado para el caso.")
    tools = pd.DataFrame([
        ["Google Cloud Monitoring", "Umbrales dinámicos con PromQL, alertas de varias métricas y pronóstico (preview)", "$0.258/MiB para los primeros 150–100,000 MiB de datos de Monitoring facturables; 150 MiB gratis. Alerting empieza a cobrarse no antes de sep-2027.", "Adecuado si la plataforma ya opera en GCP y se busca una solución nativa."],
        ["Amazon DevOps Guru", "Insights operacionales con ML sobre recursos AWS", "$0.0028/recurso-hora (grupo A) o $0.0042/recurso-hora (grupo B) + $0.000040 por llamada API.", "Adecuado para cargas principalmente AWS con poca configuración de ML."],
        ["Datadog Watchdog", "Baseline automático, detección de anomalías, impacto y análisis de causa raíz", "Watchdog está integrado; Infrastructure Enterprise parte de $23/host/mes facturado anualmente e incluye alertas basadas en ML.", "Muy completo para ambientes multicloud, pero el costo por host puede crecer con la escala."],
        ["New Relic", "Anomaly detection, correlación de incidentes y contexto de causa raíz", "100 GB/mes gratis; datos originales a $0.40/GB después del nivel gratuito. Algunas capacidades avanzadas pueden generar cargos adicionales.", "Atractivo para comenzar con bajo costo y un modelo basado en ingesta."],
    ], columns=["Herramienta","Capacidad relevante","Modelo / referencia de costo","Lectura para el caso"])
    st.dataframe(tools, use_container_width=True, hide_index=True)
    st.info("Para el informe, los costos deben presentarse como referencias del modelo de cobro y no como una equivalencia directa, porque cada proveedor factura unidades distintas.")

with t7:
    st.subheader("Cómo el demo cubre la rúbrica")
    rubric=pd.DataFrame([
        ["Limitaciones de alertas estáticas","Comparación contra detectores dinámicos y medición de falsos positivos."],
        ["Comparativa de mecanismos AIOps","Umbral estático, Z-score, CUSUM e Isolation Forest con precisión, recall, F1 y MTTD."],
        ["Pipeline completo","Señal raw → agregación → detección → deduplicación → correlación → notificación enriquecida."],
        ["Prototipo implementable","Regla Z-score real con ventana móvil, persistencia, deduplicación y correlación."],
        ["Impacto cuantitativo","Reducción de eventos, falsos positivos objetivo y estimación explícita de MTTR."],
    ],columns=["Criterio","Evidencia en el demo"])
    st.dataframe(rubric,use_container_width=True,hide_index=True)
    st.subheader("Tecnologías")
    st.markdown("**Python** para la lógica; **Streamlit** para la interfaz; **Pandas/NumPy** para series; **scikit-learn** para Isolation Forest; **Plotly** para visualizaciones.")

st.divider()
st.caption("Demo académico autocontenido: no requiere nube, base de datos ni servicios externos.")
