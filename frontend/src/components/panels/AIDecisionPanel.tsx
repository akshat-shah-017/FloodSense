import { AlertTriangle, Bell, Siren } from 'lucide-react';
import { useMemo } from 'react';
import { useAlertPreview } from '../../hooks/useAlerts';
import { useCurrentPredictions } from '../../hooks/usePredictions';
import type { MockAlert } from '../../types';
import GlowButton from '../ui/GlowButton';
import GlassPanel from '../system/GlassPanel';
import RiskBadge from '../ui/RiskBadge';
import ModelMetricsPanel from './ModelMetricsPanel';

interface AIDecisionPanelProps {
  onSelectWard: (wardId: number) => void;
}

export default function AIDecisionPanel({ onSelectWard }: AIDecisionPanelProps) {
  const { data: alerts } = useAlertPreview();
  const { data: predictions } = useCurrentPredictions();

  const derivedAlerts = useMemo<MockAlert[]>(() => {
    if (!predictions?.features?.length) {
      return [];
    }

    return predictions.features
      .map((feature) => feature.properties)
      .filter((ward) => Number(ward.risk_score) >= 65 || ward.risk_tier === 'HIGH')
      .sort((a, b) => Number(b.risk_score) - Number(a.risk_score))
      .slice(0, 4)
      .map((ward) => {
        const score = Number(ward.risk_score) || 0;
        const tier = score >= 90 ? 'RED' : 'YELLOW';
        return {
          ward_id: ward.ward_id,
          ward_name: ward.ward_name,
          risk_score: score,
          alert_tier: tier,
          message_en:
            tier === 'RED'
              ? `${ward.ward_name} has severe flood pressure (${score.toFixed(
                  1
                )}/100). Mobilize rapid-response teams and prioritize vulnerable households.`
              : `${ward.ward_name} is under elevated flood stress (${score.toFixed(
                  1
                )}/100). Keep local crews on standby and monitor low-lying pockets.`,
          message_hi: '',
          channel: tier === 'RED' ? 'WHATSAPP' : 'SMS',
          delivery_status: 'PENDING',
          dispatched_at: ward.predicted_at,
          silenced_by_window: false,
        };
      });
  }, [predictions]);

  const usingDerivedFeed = (!alerts || alerts.length === 0) && derivedAlerts.length > 0;

  const topAlerts = useMemo(
    () => [...(alerts?.length ? alerts : derivedAlerts)].sort((a, b) => Number(b.risk_score) - Number(a.risk_score)).slice(0, 4),
    [alerts, derivedAlerts]
  );

  return (
    <GlassPanel className="h-full p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="ui-headline text-lg">AI Decision Feed</h2>
        <RiskBadge tier={topAlerts[0]?.alert_tier ?? 'LOW'} pulse={Boolean(topAlerts.length)} />
      </div>
      {usingDerivedFeed ? (
        <p className="ui-label mb-3 text-on-surface-variant/80">Live advisory from prediction stream</p>
      ) : null}

      <div className="space-y-3">
        {topAlerts.length ? (
          topAlerts.map((alert) => {
            const Icon = alert.alert_tier === 'RED' ? Siren : alert.alert_tier === 'YELLOW' ? AlertTriangle : Bell;
            return (
              <div key={alert.ward_id} className="glass-card p-3">
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Icon size={14} className={alert.alert_tier === 'RED' ? 'text-error' : 'text-tertiary'} />
                    <span className="text-sm font-semibold text-on-surface">{alert.ward_name}</span>
                  </div>
                  <RiskBadge tier={alert.alert_tier} />
                </div>

                <p className="ui-body mb-3">{alert.message_en}</p>

                <GlowButton variant="ghost" className="w-full" onClick={() => onSelectWard(alert.ward_id)}>
                  Focus Ward
                </GlowButton>
              </div>
            );
          })
        ) : (
          <div className="rounded-2xl border border-secondary/35 bg-secondary/10 p-4">
            <div className="ui-label text-secondary">All Clear</div>
            <p className="ui-body mt-1">No wards currently exceed the warning threshold.</p>
          </div>
        )}
      </div>

      <div className="my-4 h-px bg-outline/20" />
      <div className="mb-2 ui-label">Model Reliability</div>
      <ModelMetricsPanel />
    </GlassPanel>
  );
}
