import AppShell from '../components/layout/AppShell';
import GlassPanel from '../components/system/GlassPanel';
import GlowButton from '../components/ui/GlowButton';
import StatusBadge from '../components/system/StatusBadge';

const sections = [
  {
    title: 'Alerting Channels',
    description: 'Control delivery channels and escalation behavior for dispatch alerts.',
    rows: [
      { label: 'SMS Dispatch', status: 'ACTIVE' },
      { label: 'WhatsApp Fallback', status: 'ACTIVE' },
      { label: 'Silence Window (6h)', status: 'ENABLED' },
    ],
  },
  {
    title: 'Model Runtime',
    description: 'Configure inference cadence and model versioning in the control plane.',
    rows: [
      { label: 'Inference Trigger', status: 'MANUAL+SCHEDULED' },
      { label: 'Active Version', status: 'v1.0' },
      { label: 'Drift Monitor', status: 'ACTIVE' },
    ],
  },
  {
    title: 'Map & UI',
    description: 'Tune map visualization and operator-facing dashboard behavior.',
    rows: [
      { label: 'High-Contrast Map', status: 'ON' },
      { label: 'Ward Hover Tooltips', status: 'ON' },
      { label: 'Page Motion Preset', status: 'PREMIUM' },
    ],
  },
];

export default function SettingsPage() {
  return (
    <AppShell
      title="Settings"
      subtitle="System-level controls for alerting, model runtime, and operator interface."
    >
      <div className="grid gap-6 xl:grid-cols-3">
        {sections.map((section) => (
          <GlassPanel key={section.title}>
            <h2 className="ui-headline text-xl">{section.title}</h2>
            <p className="ui-body mt-2">{section.description}</p>

            <div className="mt-4 space-y-3">
              {section.rows.map((row) => (
                <div
                  key={row.label}
                  className="flex items-center justify-between rounded-2xl border border-outline/20 bg-surface-container/55 px-3 py-2"
                >
                  <span className="text-sm text-on-surface">{row.label}</span>
                  <StatusBadge label={row.status} tone="success" />
                </div>
              ))}
            </div>
          </GlassPanel>
        ))}
      </div>

      <GlassPanel className="mt-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="ui-headline text-lg">Configuration Actions</h3>
            <p className="ui-body mt-1">Persist control-plane settings and roll out updates to active operators.</p>
          </div>
          <div className="flex gap-2">
            <GlowButton variant="ghost">Discard Changes</GlowButton>
            <GlowButton>Save Settings</GlowButton>
          </div>
        </div>
      </GlassPanel>
    </AppShell>
  );
}
