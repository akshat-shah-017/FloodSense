import axios from 'axios';
import type {
  AlertLogEntry,
  GeoJSONFeatureCollection,
  InferenceRunResult,
  MockAlert,
  SystemStats,
  WeatherSnapshot,
  WardDetailResponse,
} from '../types';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001',
  timeout: 30000,
});

export async function fetchCurrentPredictions(): Promise<GeoJSONFeatureCollection> {
  const response = await api.get<GeoJSONFeatureCollection>('/api/v1/predictions/current', {
    params: { _ts: Date.now() },
    headers: { 'Cache-Control': 'no-cache' },
  });
  return response.data;
}

export async function fetchWardDetail(
  wardId: number
): Promise<WardDetailResponse> {
  const response = await api.get<WardDetailResponse>(`/api/v1/predictions/${wardId}`);
  return response.data;
}

export async function fetchStats(): Promise<SystemStats> {
  try {
    const response = await api.get<SystemStats>('/api/v1/stats');
    return response.data;
  } catch {
    const predictions = await fetchCurrentPredictions();
    const tiers = { HIGH: 0, MEDIUM: 0, LOW: 0, UNKNOWN: 0 };
    let totalScore = 0;
    let staleCount = 0;
    let latest = '';

    predictions.features.forEach((feature) => {
      const props = feature.properties;
      const tier = props.risk_tier;
      if (tier in tiers) {
        tiers[tier as keyof typeof tiers] += 1;
      } else {
        tiers.UNKNOWN += 1;
      }

      totalScore += Number(props.risk_score ?? 0);
      if (props.source_status && props.source_status !== 'FRESH') {
        staleCount += 1;
      }

      if (props.predicted_at && (!latest || props.predicted_at > latest)) {
        latest = props.predicted_at;
      }
    });

    return {
      total_wards: predictions.features.length,
      last_inference_at: latest,
      risk_distribution: tiers,
      avg_risk_score: predictions.features.length
        ? totalScore / predictions.features.length
        : 0,
      wards_with_stale_data: staleCount,
    };
  }
}

export async function fetchAlertPreview(): Promise<MockAlert[]> {
  const response = await api.get<MockAlert[]>('/api/v1/alerts/mock-dispatch');
  return response.data;
}

export async function fetchAlertLog(): Promise<AlertLogEntry[]> {
  const response = await api.get<AlertLogEntry[]>('/api/v1/alerts/log');
  return response.data;
}

export async function triggerInference(payload?: { rainfall_mm?: number; demo_mode?: boolean }): Promise<InferenceRunResult> {
  const internalSecret =
    import.meta.env.VITE_INTERNAL_API_SECRET ?? 'vyrus-internal-secret-change-me';

  const response = await api.post<InferenceRunResult>(
    '/api/v1/internal/predict',
    payload ?? {},
    {
      headers: {
        'X-Internal-Secret': internalSecret,
      },
    }
  );

  return response.data;
}

export async function fetchOpenWeatherStatus(): Promise<WeatherSnapshot> {
  const response = await api.get<WeatherSnapshot>('/api/v1/weather/openweather');
  return response.data;
}
