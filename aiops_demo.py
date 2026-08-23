from __future__ import annotations
from typing import Dict, List
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

SERVICES = ["catalog", "cart", "inventory", "orders", "payments"]
METRICS = {
    "latency_ms": {"label": "Latencia (ms)", "direction": "high"},
    "error_rate_pct": {"label": "Tasa de error (%)", "direction": "high"},
    "throughput_rps": {"label": "Throughput (req/s)", "direction": "low"},
    "cpu_pct": {"label": "CPU (%)", "direction": "high"},
    "memory_pct": {"label": "Memoria (%)", "direction": "high"},
}
STATIC_THRESHOLDS = {
    "latency_ms": 500.0,
    "error_rate_pct": 1.0,
    "throughput_rps": 85.0,
    "cpu_pct": 75.0,
    "memory_pct": 75.0,
}

def _seasonality(minute_of_day: np.ndarray) -> np.ndarray:
    x = minute_of_day / 1440.0
    return 0.45 + 0.35*np.sin(2*np.pi*(x-0.25)) + 0.20*np.sin(4*np.pi*(x-0.10))

def generate_dataset(seed: int = 42, hours: int = 24) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    minutes = int(hours * 60)
    start = pd.Timestamp("2026-08-23 00:00:00")
    timestamps = pd.date_range(start, periods=minutes, freq="min")
    frames = []
    factors = {"catalog":1.00,"cart":0.92,"inventory":0.78,"orders":0.70,"payments":0.62}
    for service in SERVICES:
        minute = np.arange(minutes) % 1440
        seasonal = _seasonality(minute)
        sf = factors[service]
        throughput = 150*sf + 95*sf*seasonal + rng.normal(0,8,minutes)
        latency = 160/sf + 45*seasonal + rng.normal(0,14,minutes)
        error = np.clip(0.22 + 0.15*seasonal + rng.normal(0,0.08,minutes),0.01,None)
        cpu = np.clip(30 + 28*seasonal + 20*sf + rng.normal(0,4,minutes),3,98)
        memory = np.clip(42 + 9*seasonal + 6*sf + rng.normal(0,2.5,minutes),10,97)

        # Evento de negocio legítimo: alto tráfico sin incidente.
        ps = int(minutes*0.72); pe = min(minutes, ps+70)
        throughput[ps:pe] *= 1.45
        cpu[ps:pe] = np.clip(cpu[ps:pe] + 8, 0, 99)

        is_incident = np.zeros(minutes,dtype=bool)
        incident_name = np.array([""]*minutes,dtype=object)

        if service == "payments":
            s = int(minutes*0.40); e = min(minutes,s+35); ramp = np.linspace(1.0,2.0,e-s)
            latency[s:e] += 260*ramp
            error[s:e] += 1.7*ramp
            throughput[s:e] *= np.linspace(0.86,0.55,e-s)
            cpu[s:e] = np.clip(cpu[s:e] + np.linspace(8,24,e-s),0,99)
            is_incident[s:e] = True; incident_name[s:e] = "payments_degradation"
        if service == "inventory":
            s = int(minutes*0.58); e = min(minutes,s+25)
            cpu[s:e] = np.clip(cpu[s:e] + 37,0,99)
            latency[s:e] += np.linspace(80,210,e-s)
            throughput[s:e] *= 0.78
            is_incident[s:e] = True; incident_name[s:e] = "inventory_cpu_contention"
        if service == "orders":
            s = int(minutes*0.25); e = min(minutes,s+45)
            latency[s:e] += np.linspace(40,360,e-s)
            error[s:e] += np.linspace(0,0.65,e-s)
            is_incident[s:e] = True; incident_name[s:e] = "orders_latency_drift"

        frames.append(pd.DataFrame({
            "timestamp":timestamps,"service":service,
            "latency_ms":np.clip(latency,1,None),
            "error_rate_pct":np.clip(error,0,100),
            "throughput_rps":np.clip(throughput,1,None),
            "cpu_pct":np.clip(cpu,0,100),"memory_pct":np.clip(memory,0,100),
            "is_incident":is_incident,"incident_name":incident_name,
        }))
    return pd.concat(frames,ignore_index=True)

def detect_static(df: pd.DataFrame) -> pd.Series:
    f = pd.Series(False,index=df.index)
    f |= df.latency_ms > STATIC_THRESHOLDS["latency_ms"]
    f |= df.error_rate_pct > STATIC_THRESHOLDS["error_rate_pct"]
    f |= df.throughput_rps < STATIC_THRESHOLDS["throughput_rps"]
    f |= df.cpu_pct > STATIC_THRESHOLDS["cpu_pct"]
    f |= df.memory_pct > STATIC_THRESHOLDS["memory_pct"]
    return f

def _persistent(raw: pd.Series, services: pd.Series) -> pd.Series:
    out = pd.Series(False,index=raw.index)
    for _,idx in pd.DataFrame({"service":services}).groupby("service").groups.items():
        r = raw.loc[idx].astype(int)
        out.loc[idx] = r.rolling(3,min_periods=2).sum() >= 2
    return out

def zscore_metric_flags(df: pd.DataFrame, window: int = 60, threshold: float = 3.0) -> Dict[str,pd.Series]:
    result = {}
    for metric,meta in METRICS.items():
        f = pd.Series(False,index=df.index)
        for _,idx in df.groupby("service").groups.items():
            x = df.loc[idx,metric].astype(float)
            minp = max(10,window//3)
            mu = x.rolling(window,min_periods=minp).mean().shift(1)
            sd = x.rolling(window,min_periods=minp).std(ddof=0).shift(1).replace(0,np.nan)
            z = (x-mu)/sd
            f.loc[idx] = (z > threshold) if meta["direction"]=="high" else (z < -threshold)
        result[metric] = f
    return result

def detect_zscore(df: pd.DataFrame, window: int = 60, threshold: float = 3.0) -> pd.Series:
    m = zscore_metric_flags(df,window,threshold)
    raw = pd.concat(list(m.values()),axis=1).any(axis=1)
    return _persistent(raw,df.service)

def detect_cusum(df: pd.DataFrame) -> pd.Series:
    """CUSUM sobre residuales de una media móvil para no confundir estacionalidad con incidente."""
    flags = pd.Series(False,index=df.index)
    window = 60
    for _,idx in df.groupby("service").groups.items():
        x = df.loc[idx,"latency_ms"].astype(float)
        minp = max(20,window//3)
        baseline = x.rolling(window,min_periods=minp).mean().shift(1)
        residual = x - baseline
        sigma = residual.rolling(window,min_periods=minp).std(ddof=0).shift(1)
        local=[]; s_pos=0.0
        for r,sd in zip(residual.fillna(0.0),sigma.fillna(np.inf)):
            if not np.isfinite(sd) or sd<=0:
                local.append(False); continue
            k=0.5*sd; h=4.0*sd
            s_pos=max(0.0,s_pos+(r-k))
            hit=s_pos>h
            local.append(hit)
            if hit: s_pos*=0.4
        flags.loc[idx]=local
    return _persistent(flags,df.service)

def detect_isolation_forest(df: pd.DataFrame, seed: int = 42) -> pd.Series:
    flags = pd.Series(False,index=df.index)
    feats = list(METRICS.keys())
    for _,idx in df.groupby("service").groups.items():
        X = df.loc[idx,feats].astype(float)
        med = X.median(); iqr=(X.quantile(.75)-X.quantile(.25)).replace(0,1.0)
        Xs = (X-med)/iqr
        model = IsolationForest(n_estimators=160,contamination=.035,random_state=seed,n_jobs=-1)
        flags.loc[idx] = model.fit_predict(Xs) == -1
    return _persistent(flags,df.service)

def evaluate_method(df: pd.DataFrame, flags: pd.Series) -> Dict[str,float]:
    y = df.is_incident.astype(int); p = flags.astype(int)
    return {
        "Precisión":float(precision_score(y,p,zero_division=0)),
        "Recall":float(recall_score(y,p,zero_division=0)),
        "F1":float(f1_score(y,p,zero_division=0)),
        "Falsos positivos":int(((p==1)&(y==0)).sum()),
        "Alertas":int(p.sum()),
    }

def detection_delay_minutes(df: pd.DataFrame, flags: pd.Series) -> float:
    tmp=df.copy(); tmp["flag"]=flags.values; delays=[]
    for name in sorted(x for x in tmp.incident_name.unique() if x):
        inc=tmp[tmp.incident_name==name]; det=inc[inc.flag]
        if not det.empty:
            delays.append((det.timestamp.min()-inc.timestamp.min()).total_seconds()/60)
    return float(np.mean(delays)) if delays else float("nan")

def build_alerts(df: pd.DataFrame, overall_flags: pd.Series, window: int=60, threshold: float=3.0) -> List[dict]:
    metric_flags = zscore_metric_flags(df,window,threshold)
    alerts=[]
    for idx in df.index[overall_flags]:
        row=df.loc[idx]
        active=[m for m,f in metric_flags.items() if bool(f.loc[idx])]
        if not active: active=["persistent_anomaly"]
        for metric in active:
            alerts.append({"timestamp":pd.Timestamp(row.timestamp),"service":row.service,
                           "metric":metric,"method":"Z-score","is_true_incident":bool(row.is_incident),
                           "incident_name":row.incident_name})
    return sorted(alerts,key=lambda a:a["timestamp"])

def deduplicate_alerts(alerts: List[dict], window_minutes: int=5) -> List[dict]:
    kept=[]; last_seen={}; window=pd.Timedelta(minutes=window_minutes)
    for a in alerts:
        key=(a["service"],a["metric"],a["method"]); ts=a["timestamp"]
        if key not in last_seen or ts-last_seen[key] > window:
            item=dict(a); item["duplicate_count"]=1; kept.append(item)
        else:
            for item in reversed(kept):
                if (item["service"],item["metric"],item["method"])==key:
                    item["duplicate_count"]+=1; break
        last_seen[key]=ts
    return kept

def correlate_alerts(alerts: List[dict], min_metrics: int=2, correlation_window_minutes: int=5) -> List[dict]:
    if not alerts: return []
    d=pd.DataFrame(alerts).sort_values("timestamp"); incidents=[]; window=pd.Timedelta(minutes=correlation_window_minutes)
    for service,g in d.groupby("service"):
        g=g.sort_values("timestamp").reset_index(drop=True); consumed=set()
        for i in range(len(g)):
            if i in consumed: continue
            start=g.loc[i,"timestamp"]; idxs=list(g.index[(g.timestamp>=start)&(g.timestamp<=start+window)])
            metrics=sorted(set(g.loc[idxs,"metric"])-{"persistent_anomaly"})
            if len(metrics)<min_metrics: continue
            consumed.update(idxs)
            severity="CRITICAL" if service=="payments" and len(metrics)>=3 else ("HIGH" if len(metrics)>=3 else "MEDIUM")
            cause="degradación multivariable del servicio"
            if "cpu_pct" in metrics and "latency_ms" in metrics: cause="posible contención de recursos"
            if service=="payments" and {"latency_ms","error_rate_pct"}.issubset(metrics): cause="posible degradación del servicio de pagos"
            names=[x for x in g.loc[idxs,"incident_name"].unique() if x]
            incidents.append({
                "timestamp":str(start),"service":service,"severity":severity,"metrics":metrics,
                "possible_cause":cause,"true_incident_in_simulation":bool(g.loc[idxs,"is_true_incident"].any()),
                "ground_truth_incident":names[0] if names else "",
                "message":f"[{severity}] {service}: {len(metrics)} señales correlacionadas ({', '.join(metrics)}). Causa sugerida: {cause}."
            })
    return incidents

def impact_summary(baseline_alerts_per_day:int=800, baseline_false_positive_rate:float=.72, current_mttr_hours:float=3.5,
                   demo_raw_alerts:int=0, demo_incidents:int=0, mttr_reduction_assumption:float=.30) -> Dict[str,float]:
    fp=baseline_alerts_per_day*baseline_false_positive_rate; target=fp*.40; removed=fp-target
    demo_noise=0.0 if demo_raw_alerts==0 else (1-demo_incidents/demo_raw_alerts)*100
    est=current_mttr_hours*(1-mttr_reduction_assumption)
    return {"baseline_false_positives_per_day":fp,"target_false_positives_per_day":target,
            "false_positives_removed_per_day":removed,"false_positives_removed_per_month":removed*30,
            "demo_noise_reduction_pct":max(0.0,demo_noise),"estimated_mttr_hours":est,
            "mttr_minutes_saved":(current_mttr_hours-est)*60}
