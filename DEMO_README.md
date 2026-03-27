# Vyrus Urban Solutions — Demo Guide
**Ward-Level Flood Risk Intelligence Platform | Delhi NCR | March 2026**

## Quick Start
```bash
cd /Users/akshatshah17/Documents/FloodSense/vyrus
docker compose up -d
cd frontend && npm run dev
# Dashboard → http://localhost:3001
# API       → http://localhost:8001
# MLflow    → http://localhost:5001
```

## What You Can Show in the Demo

### 1. Live Flood Risk Map (Dashboard — http://localhost:3001)
- 250 Delhi ward polygons on a dark map, coloured by ML-predicted risk tier
  - 🔴 RED = High risk (score ≥ 75)
  - 🟡 AMBER = Medium risk (score 40–74)
  - 🟢 GREEN = Low risk (score < 40)
- Hover over any ward → cyan border highlight
- Click any ward → glassmorphism popup showing:
  - Real ML risk score (0–100) from ensemble of LGBM + XGB + LSTM
  - Confidence interval (ci_lower to ci_upper)
  - Top 3 SHAP feature drivers with proportional bar chart
  - Data freshness status (FRESH / STALE / DEGRADED)
  - "Open Ward Profile →" button to navigate to full ward page

### 2. Ward Detail Page (/ward/:wardId)
- Dedicated page for each of the 250 wards
- Shows: risk tier (with colour), circular risk score dial, CI bounds
- 30-day score history sparkline (populated after multiple inference runs)
- Full SHAP breakdown (which features drove the prediction and by how much)
- Alert status: what SMS/WhatsApp message WOULD be sent for this ward
- Model metadata: version, data source status, last updated

### 3. Run Inference (Dashboard — Simulation Bar at bottom)
- Click "▶ RUN INFERENCE" to trigger the full ML prediction pipeline:
  1. Loads latest ward features from PostgreSQL (2.09M rows)
  2. Runs LGBM + XGB models (scikit-learn ensemble)
  3. Runs LSTM model (PyTorch, 7-day sequence)
  4. Combines scores into final ensemble prediction per ward
  5. Writes 250 prediction rows to PostGIS DB
  6. Map automatically refreshes with updated colours
- Completion toast appears: "COMPLETE — 250 wards updated"
- Takes approximately 30–120 seconds depending on machine

### 4. AI Decision Support Panel (Dashboard — right sidebar)
- Shows real-time alert preview: which wards exceed risk threshold RIGHT NOW
- RED alerts (score ≥ 90): "EVACUATE NOW" with full Hindi + English message
- YELLOW alerts (score ≥ 75): "FLOOD WATCH ADVISORY"
- "ALL SYSTEMS OPTIMAL" if no wards are at risk
- Model performance metrics: LGBM AUC 0.923 · XGB AUC 0.917 · LSTM AUC 0.901

### 5. Historical Analysis Page (/historical)
- Training data lineage: 2.09M rows, 18 years IMD data, 1,583 flood labels
- Model accuracy metrics from walk-forward temporal validation
- Live risk distribution bar chart: current HIGH/MEDIUM/LOW/UNKNOWN ward counts
- Prediction accuracy: 92.3% (validated against IFI flood inventory)

### 6. Resource Center (/resources)
- Live count of high-risk wards (from real DB predictions)
- Mock field resource inventory: pumps, maintenance teams, response units
- Alert log: last 24h of mock dispatch records (SMS/WhatsApp simulation)
- AI Deployment Logic overview: how the pump allocation and alert pipeline works

### 7. MLflow Experiment Tracking (http://localhost:5001)
- Experiments: vyrus_flood_v1 · vyrus_drift_monitoring
- Logged parameters: city_id, ward count, SMOTE strategy, LSTM config, training years
- Logged metrics: LGBM/XGB/LSTM AUC, F1, precision, recall, combined test scores
- Data lineage artifact: training provenance JSON

## What is Real vs Mocked

| Feature | Status |
|---|---|
| 250-ward Delhi boundary GeoJSON | ✅ Real PostGIS data |
| ML risk scores (LGBM + XGB + LSTM ensemble) | ✅ Real trained models |
| SHAP feature attributions | ✅ Real TreeExplainer output |
| Confidence intervals | ✅ Real CI from model |
| IMD rainfall features (2.09M rows) | ✅ Real ETL from NetCDF |
| IFI flood labels (1,583 events) | ✅ Real historical data |
| Score history chart | ✅ Real (grows with each inference run) |
| SMS / WhatsApp dispatch | 🟡 Mocked — messages shown, not sent |
| Alert silence window (6h) | 🟡 Phase 7 |
| Scenario simulation (50/100/200mm) | 🟡 Phase 7 |
| PDF report generation | 🟡 Phase 7 |
| Resource field deployment | 🟡 Mocked with realistic Delhi data |
| Authentication / login | 🟡 Phase 7 |

## Common Demo Talking Points
- "The system ingested 18 years of IMD gridded rainfall data and trained on 2.09 million ward-day feature rows"
- "We use a three-model ensemble — LightGBM, XGBoost, and LSTM — with SMOTE for class imbalance (1:1321 ratio)"
- "SHAP values tell you exactly why each ward got its score, not just what the score is"
- "The map refreshes every 3 hours in production — click Run Inference to see a live update right now"
- "Every prediction carries a confidence interval, so municipal officers know how certain the model is"

## Troubleshooting
```bash
# If map is blank or shows error banner:
curl http://localhost:8001/api/v1/health

# If stats show "—":
curl http://localhost:8001/api/v1/stats

# If no predictions in DB, run inference:
curl -X POST http://localhost:8001/api/v1/internal/predict \
  -H "X-Internal-Secret: vyrus-internal-secret-change-me"

# Check prediction count:
docker compose exec postgres psql -U postgres -d vyrus \
  -c "SELECT COUNT(*), MAX(predicted_at) FROM predictions;"

# Restart after code changes:
docker compose build fastapi && docker compose up -d fastapi
cd frontend && npm run dev
```
