import { useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import { ErrorState, LoadingState, MetricCard, NotConnected, PageHeader, Panel } from "../components/UI";
import { api, ModelMetrics } from "../services/api";

const metricLabels = [["precision", "Precision"], ["recall", "Recall"], ["f1", "F1 score"], ["roc_auc", "ROC-AUC"], ["pr_auc", "PR-AUC"]] as const;

export default function ModelLab() {
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.modelMetrics().then(setMetrics).catch((err) => setError(err instanceof Error ? err.message : "Model service unavailable")); }, []);
  return <AppShell><section className="page"><PageHeader eyebrow="Models / evaluation" title="Model lab" description="Review model quality, calibration, feature importance, and drift before promoting a version." />
    {error ? <ErrorState message={error} /> : !metrics ? <LoadingState /> : <><div className="metric-grid">{metricLabels.map(([key, label]) => <MetricCard key={key} label={label} value={metrics[key] === undefined ? null : `${(metrics[key] as number * 100).toFixed(1)}%`} tone="cyan" />)}</div><div className="workspace-grid"><Panel title="Model version" eyebrow="Active production artifact"><div className="control-row"><span>Version</span><strong className="mono">{metrics.model_version}</strong></div><Panel title="Drift indicators" eyebrow="Feature and prediction health"><div className="metric-table">{Object.entries(metrics.drift || {}).map(([name, value]) => <div key={name}><span>{name.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}</div></Panel></Panel><Panel title="Confusion matrix" eyebrow="Held-out evaluation">{metrics.confusion_matrix ? <div className="confusion-matrix">{metrics.confusion_matrix.flatMap((row, rowIndex) => row.map((value, columnIndex) => <span key={`${rowIndex}-${columnIndex}`}>{rowIndex === columnIndex ? "Correct" : "Error"}<strong>{value}</strong></span>))}</div> : <NotConnected detail="Confusion matrix data is not available from the model contract." />}</Panel><Panel className="wide" title="Evaluation curves" eyebrow="Validation artifacts"><div className="workspace-grid"><div className="chart-placeholder">ROC curve data unavailable</div><div className="chart-placeholder">Precision-recall data unavailable</div></div></Panel><Panel className="wide" title="Feature importance" eyebrow="Model explanation">{metrics.feature_importance?.length ? <div className="evidence-list">{metrics.feature_importance.map((feature) => <div key={feature.name} className="evidence-bar"><div><span>{feature.name}</span><strong>{feature.value.toFixed(3)}</strong></div><i style={{ width: `${Math.min(100, feature.value * 100)}%` }} /></div>)}</div> : <NotConnected detail="Feature importance data is not available from the model contract." />}</Panel></div></>}
  </section></AppShell>;
}
