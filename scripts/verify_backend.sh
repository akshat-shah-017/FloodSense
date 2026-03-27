#!/bin/bash
set -e
BASE=http://localhost:8001
SECRET="vyrus-internal-secret-change-me"

echo "=== 1. Health check ==="
curl -s $BASE/api/v1/health | python3 -m json.tool

echo "=== 2. Trigger inference ==="
curl -s -X POST $BASE/api/v1/internal/predict \
  -H "X-Internal-Secret: $SECRET" | python3 -m json.tool

echo "=== 3. Count predictions in latest batch ==="
docker compose -f /Users/akshatshah17/Documents/FloodSense/vyrus/docker-compose.yml \
  exec -T postgres psql -U postgres -d vyrus -Atc \
  "SELECT COUNT(*), MAX(predicted_at) FROM predictions WHERE predicted_at = (SELECT MAX(predicted_at) FROM predictions);"

echo "=== 4. GeoJSON feature count ==="
curl -s $BASE/api/v1/predictions/current | python3 -c "
import json,sys
d=json.load(sys.stdin)
tiers = {}
for f in d['features']:
    t = f['properties'].get('risk_tier','?')
    tiers[t] = tiers.get(t,0)+1
print('Total features:', len(d['features']))
print('Tier breakdown:', tiers)
"

echo "=== 5. Ward detail ==="
curl -s $BASE/api/v1/predictions/1 | python3 -m json.tool

echo "=== 6. Alert preview ==="
curl -s $BASE/api/v1/alerts/mock-dispatch | python3 -m json.tool | head -60
