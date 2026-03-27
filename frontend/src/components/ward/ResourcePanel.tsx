import type { WardPrediction } from '../../types';
import { relativeTime, toTitleCase } from '../../lib/format';
import GlassPanel from '../system/GlassPanel';
import StatusBadge, { toneFromTier } from '../system/StatusBadge';

interface ResourcePanelProps {
  ward: WardPrediction;
}

export default function ResourcePanel({ ward }: ResourcePanelProps) {
  const shapRows = [
    { feature: ward.shap_feature_1, value: Number(ward.shap_value_1 ?? 0) },
    { feature: ward.shap_feature_2, value: Number(ward.shap_value_2 ?? 0) },
    { feature: ward.shap_feature_3, value: Number(ward.shap_value_3 ?? 0) },
  ];

  const maxAbs = Math.max(0.0001, ...shapRows.map((row) => Math.abs(row.value)));
  const sourceTone = toneFromTier(ward.source_status);

  return (
    <GlassPanel>
      <div className="mb-3">
        <h2 className="ui-headline text-xl">Resource Panel</h2>
        <p className="ui-body mt-1">Model metadata, source health, and top factors affecting this ward.</p>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-outline/20 bg-surface-container/55 p-3">
          <div className="ui-label">Model Version</div>
          <div className="mt-1 font-mono text-sm text-on-surface">{ward.model_version || '—'}</div>
        </div>
        <div className="rounded-2xl border border-outline/20 bg-surface-container/55 p-3">
          <div className="ui-label">Source Status</div>
          <div className="mt-2">
            <StatusBadge tone={sourceTone} label={ward.source_status} />
          </div>
        </div>
      </div>

      <div className="mb-2 ui-label">Top Risk Drivers</div>
      <div className="space-y-3">
        {shapRows.map((row, idx) => {
          const width = `${(Math.abs(row.value) / maxAbs) * 100}%`;
          const color = row.value >= 0 ? 'bg-error/75' : 'bg-primary/75';
          return (
            <div key={`${row.feature}-${idx}`}>
              <div className="mb-1 flex items-center justify-between text-xs text-on-surface-variant">
                <span>{toTitleCase(row.feature || 'no_data')}</span>
                <span className="font-mono">{row.value.toFixed(3)}</span>
              </div>
              <div className="h-2 w-full rounded-full bg-outline/20">
                <div className={`h-2 rounded-full ${color}`} style={{ width }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 ui-body !text-xs">Last updated: {relativeTime(ward.predicted_at)}</div>
    </GlassPanel>
  );
}

