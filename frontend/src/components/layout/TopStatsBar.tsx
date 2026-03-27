import { Activity, AlertTriangle, CloudRain, Workflow } from 'lucide-react';
import { useAlertPreview } from '../../hooks/useAlerts';
import { useCurrentPredictions } from '../../hooks/usePredictions';
import type { SystemStats } from '../../types';
import StatCard from '../system/StatCard';

interface TopStatsBarProps {
  stats: SystemStats | undefined;
  isLoading: boolean;
}

export default function TopStatsBar({ stats, isLoading }: TopStatsBarProps) {
  const { data: alerts } = useAlertPreview();
  const { data: predictions } = useCurrentPredictions();
  const fallbackCriticalCount =
    predictions?.features.filter((feature) => Number(feature.properties.risk_score) >= 90).length ?? 0;
  const alertCount = alerts?.filter((item) => item.alert_tier === 'RED').length ?? fallbackCriticalCount;
  const staleWards = stats?.wards_with_stale_data ?? 0;

  return (
    <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <StatCard
        icon={<CloudRain size={16} />}
        label="High-Risk Wards"
        value={isLoading ? '—' : stats?.risk_distribution.HIGH ?? 0}
        unit="wards"
        description="Wards at risk score >= 75 in current cycle."
        highlight={(stats?.risk_distribution.HIGH ?? 0) > 5 ? 'warning' : 'none'}
      />
      <StatCard
        icon={<AlertTriangle size={16} />}
        label="Critical Alerts"
        value={alertCount}
        unit="active"
        description="Immediate response zones with RED alerts."
        highlight={alertCount > 0 ? 'critical' : 'none'}
      />
      <StatCard
        icon={<Activity size={16} />}
        label="City Risk Average"
        value={stats?.avg_risk_score?.toFixed(1) ?? '—'}
        unit="/100"
        description="Average flood probability across wards."
        trend="neutral"
      />
      <StatCard
        icon={<Workflow size={16} />}
        label="Telemetry Freshness"
        value={staleWards}
        unit="stale"
        description="Wards with stale or degraded input feeds."
        highlight={staleWards > 0 ? 'warning' : 'none'}
      />
    </section>
  );
}
