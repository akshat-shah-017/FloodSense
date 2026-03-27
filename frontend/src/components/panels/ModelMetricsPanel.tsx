const modelRows = [
  { label: 'LGBM AUC', value: 0.923 },
  { label: 'XGB AUC', value: 0.917 },
  { label: 'LSTM AUC', value: 0.901 },
];

export default function ModelMetricsPanel() {
  return (
    <div className="space-y-3">
      {modelRows.map((row) => (
        <div key={row.label}>
          <div className="mb-1 flex items-center justify-between">
            <span className="ui-label">{row.label}</span>
            <span className="font-mono text-sm text-primary">{row.value.toFixed(3)}</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-outline/20">
            <div className="h-1.5 rounded-full bg-primary/85" style={{ width: `${row.value * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

