import GlassCard from '../system/GlassCard';

const legendRows = [
  { label: 'High Risk (>= 75)', color: 'bg-error' },
  { label: 'Medium Risk (40-74)', color: 'bg-tertiary' },
  { label: 'Low Risk (< 40)', color: 'bg-secondary' },
  { label: 'Unknown / No Data', color: 'bg-on-surface-variant' },
];

export default function MapLegend() {
  return (
    <GlassCard interactive={false} className="pointer-events-none absolute bottom-4 left-4 z-[450] w-[220px] p-3">
      <div className="ui-label mb-2">Risk Legend</div>
      <div className="space-y-1.5">
        {legendRows.map((row) => (
          <div key={row.label} className="flex items-center gap-2 text-xs text-on-surface">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${row.color}`} />
            <span>{row.label}</span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

