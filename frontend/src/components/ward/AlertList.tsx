import type { AlertLogEntry } from '../../types';
import GlassPanel from '../system/GlassPanel';
import StatusBadge, { toneFromTier } from '../system/StatusBadge';
import RiskBadge from '../ui/RiskBadge';

interface AlertListProps {
  alerts: AlertLogEntry[];
}

function formatTimestamp(rawTimestamp: string): string {
  const parsed = new Date(rawTimestamp);
  if (Number.isNaN(parsed.getTime())) {
    return '—';
  }
  return parsed.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AlertList({ alerts }: AlertListProps) {
  return (
    <GlassPanel>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="ui-headline text-xl">Alert History</h2>
        <StatusBadge label={`${alerts.length} Events`} tone={alerts.length > 0 ? 'warning' : 'success'} />
      </div>

      {alerts.length === 0 ? (
        <div className="rounded-2xl border border-secondary/30 bg-secondary/10 p-3 text-sm text-secondary">
          No alert events recorded for this ward in the available window.
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert, index) => (
            <div key={`${alert.ward_id}-${alert.dispatched_at}-${index}`} className="rounded-2xl border border-outline/20 bg-surface-container/55 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <RiskBadge tier={alert.alert_tier} />
                  <span className="ui-label">{alert.channel}</span>
                </div>
                <StatusBadge label={alert.delivery_status} tone={toneFromTier(alert.delivery_status)} />
              </div>

              <div className="text-sm text-on-surface">{alert.message_en ?? `${alert.alert_tier} alert dispatched for ${alert.ward_name}.`}</div>
              <div className="mt-2 text-xs text-on-surface-variant">{formatTimestamp(alert.dispatched_at)}</div>
            </div>
          ))}
        </div>
      )}
    </GlassPanel>
  );
}

