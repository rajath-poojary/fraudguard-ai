# Architecture

Scaffold phase: see the repository README for the intended layout.

Planned runtime: Next.js UI → FastAPI → PostgreSQL + Redis; offline ML artifacts loaded by the API.

The risk engine combines three independent signals: the supervised fraud
classifier's fraud probability, the Isolation Forest anomaly score and
configurable rule matches. It preserves each signal and emits an explainable
decision with reason codes, so the components can be tuned or replaced
independently.
