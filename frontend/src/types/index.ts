export interface WardPrediction {
  ward_id: number;
  ward_name: string;
  ward_number?: number;
  risk_score: number;
  ci_lower: number;
  ci_upper: number;
  risk_tier: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  shap_feature_1: string;
  shap_value_1: number;
  shap_feature_2: string;
  shap_value_2: number;
  shap_feature_3: string;
  shap_value_3: number;
  source_status: 'FRESH' | 'STALE' | 'DEGRADED' | 'NO_DATA';
  predicted_at: string;
  model_version: string;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

export interface GeoJSONGeometry {
  type: 'Polygon' | 'MultiPolygon' | string;
  coordinates: number[][][] | number[][][][] | unknown;
}

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: GeoJSONGeometry;
  properties: WardPrediction;
}

export interface SystemStats {
  total_wards: number;
  last_inference_at: string;
  risk_distribution: {
    HIGH: number;
    MEDIUM: number;
    LOW: number;
    UNKNOWN: number;
  };
  avg_risk_score: number;
  wards_with_stale_data: number;
}

export interface MockAlert {
  ward_id: number;
  ward_name: string;
  risk_score: number;
  alert_tier: 'RED' | 'YELLOW' | 'ALL_CLEAR';
  message_en: string;
  message_hi: string;
  channel?: 'SMS' | 'WHATSAPP';
  delivery_status?: 'SENT' | 'FAILED' | 'PENDING';
  dispatched_at?: string;
  silenced_by_window?: boolean;
}

export interface AlertLogEntry {
  ward_id: number;
  ward_name: string;
  alert_tier: 'RED' | 'YELLOW' | 'ALL_CLEAR';
  channel: 'SMS' | 'WHATSAPP';
  dispatched_at: string;
  delivery_status: 'SENT' | 'FAILED' | 'PENDING';
  risk_score?: number;
  message_en?: string;
}

export interface WardDetailResponse extends WardPrediction {
  score_history: Array<{ predicted_at: string; risk_score: number }>;
}

export interface WeatherSnapshot {
  configured: boolean;
  integration: string;
  status: 'live' | 'not_configured' | 'error' | string;
  latest_feature_at?: string | null;
  avg_precip_realtime?: number | null;
  max_precip_realtime?: number | null;
  ward_count?: number;
  provider_city?: string | null;
  fetched_at?: string;
  forecast?: {
    series_points: number;
    total_24h_mm: number;
    max_6hr_mm: number;
    next_3hr_mm: number;
  };
  error?: string;
}

export interface InferenceRunResult {
  wards_predicted: number;
  completed_at: string;
  scenario_applied?: boolean;
  rainfall_mm?: number | null;
  demo_mode?: boolean;
}
