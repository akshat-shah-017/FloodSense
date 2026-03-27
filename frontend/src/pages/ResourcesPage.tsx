import { Shield, Users, Wrench } from 'lucide-react';
import type { ReactNode } from 'react';
import AppShell from '../components/layout/AppShell';
import GlassPanel from '../components/system/GlassPanel';
import StatCard from '../components/system/StatCard';
import StatusBadge, { toneFromTier } from '../components/system/StatusBadge';
import GlowButton from '../components/ui/GlowButton';
import RiskBadge from '../components/ui/RiskBadge';
import { useAlertPreview } from '../hooks/useAlerts';
import { useSystemStats } from '../hooks/useStats';

interface InventoryItem {
  name: string;
  id: string;
  location: string;
  status: 'IDLE' | 'ACTIVE' | 'SERVICE' | 'STANDBY';
  type: 'PUMP' | 'TEAM' | 'UNIT';
}

interface AlertLogItem {
  ward_name: string;
  alert_tier: 'RED' | 'YELLOW' | 'ALL_CLEAR';
  channel: 'SMS' | 'WHATSAPP';
  delivery_status: 'SENT' | 'FAILED' | 'PENDING';
  timestamp: string;
}

const inventoryItems: InventoryItem[] = [
  { name: 'Mobile Pump MP-08', status: 'IDLE', id: '994-A2', location: 'North Depot', type: 'PUMP' },
  { name: 'Maint. Team Alpha-4', status: 'ACTIVE', id: '112-T9', location: 'Ward 47 (Rohini)', type: 'TEAM' },
  { name: 'Heavy Pump HP-01', status: 'SERVICE', id: '004-X1', location: 'Central Yard', type: 'PUMP' },
  { name: 'Response Unit RU-12', status: 'ACTIVE', id: '221-R3', location: 'Ward 133 (Lajpat Nagar)', type: 'UNIT' },
  { name: 'Mobile Pump MP-15', status: 'IDLE', id: '447-A7', location: 'South Depot', type: 'PUMP' },
  { name: 'Maint. Team Beta-2', status: 'STANDBY', id: '089-T4', location: 'Okhla Sector B', type: 'TEAM' },
];

function iconForType(type: InventoryItem['type']): ReactNode {
  if (type === 'TEAM') {
    return <Users size={16} />;
  }
  if (type === 'UNIT') {
    return <Shield size={16} />;
  }
  return <Wrench size={16} />;
}

function formatTimestamp(isoString: string): string {
  const timestamp = new Date(isoString);
  if (Number.isNaN(timestamp.getTime())) {
    return '—';
  }
  return timestamp.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function ResourcesPage() {
  const { data: stats } = useSystemStats();
  const { data: liveAlerts } = useAlertPreview();

  const alertLog: AlertLogItem[] =
    liveAlerts && liveAlerts.length > 0
      ? liveAlerts.slice(0, 5).map((item, idx) => ({
          ward_name: item.ward_name,
          alert_tier: item.alert_tier === 'RED' ? 'RED' : item.alert_tier === 'YELLOW' ? 'YELLOW' : 'ALL_CLEAR',
          channel: item.channel === 'WHATSAPP' ? 'WHATSAPP' : 'SMS',
          delivery_status: item.delivery_status === 'FAILED' ? 'FAILED' : item.delivery_status === 'PENDING' ? 'PENDING' : 'SENT',
          timestamp: item.dispatched_at ?? new Date(Date.now() - idx * 12 * 60 * 1000).toISOString(),
        }))
      : [];

  return (
    <AppShell title="Resource Operations" subtitle="Deployment inventory, dispatch telemetry, and response orchestration.">
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Dispatch Success" value="94.2%" description="Channel delivery success in last cycle." />
        <StatCard label="Models Active" value={3} description="Forecast ensemble currently operational." />
        <StatCard label="Training Rows" value="2.09M" description="Prepared rows in current training corpus." />
        <StatCard label="High-Risk Areas" value={stats?.risk_distribution?.HIGH ?? 0} description="Wards requiring priority response." />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <GlassPanel>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="ui-headline text-xl">Live Inventory</h2>
            <StatusBadge label="36 Total Assets" tone="neutral" />
          </div>

          <div className="space-y-3">
            {inventoryItems.map((item) => (
              <div key={item.id} className="rounded-2xl border border-outline/20 bg-surface-container/55 p-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/30 bg-primary/12 text-primary">
                    {iconForType(item.type)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-on-surface">{item.name}</div>
                    <div className="ui-label mt-1">{item.id}</div>
                    <div className="text-xs text-on-surface-variant">{item.location}</div>
                  </div>
                  <StatusBadge label={item.status} tone={toneFromTier(item.status === 'ACTIVE' ? 'SUCCESS' : item.status === 'SERVICE' ? 'YELLOW' : 'UNKNOWN')} />
                </div>
              </div>
            ))}
          </div>
        </GlassPanel>

        <GlassPanel>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="ui-headline text-xl">Alert Dispatch Log</h2>
            <StatusBadge label="Last 24h" tone="neutral" />
          </div>

          {alertLog.length === 0 ? (
            <div className="rounded-2xl border border-secondary/35 bg-secondary/10 p-3 text-sm text-secondary">
              No active dispatch events are available from the alert feed.
            </div>
          ) : (
            <div className="space-y-3">
              {alertLog.map((alert, idx) => (
                <div key={`${alert.ward_name}-${idx}`} className="rounded-2xl border border-outline/20 bg-surface-container/55 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-on-surface">{alert.ward_name}</span>
                    <RiskBadge tier={alert.alert_tier} />
                  </div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="ui-label">{alert.channel}</span>
                    <StatusBadge label={alert.delivery_status} tone={toneFromTier(alert.delivery_status)} />
                  </div>
                  <div className="text-xs text-on-surface-variant">{formatTimestamp(alert.timestamp)}</div>
                </div>
              ))}
            </div>
          )}
        </GlassPanel>
      </div>

      <GlassPanel className="mt-6">
        <h2 className="ui-headline text-xl">Operational Logic</h2>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div>
            <div className="ui-label mb-2">Pump Allocation</div>
            <p className="ui-body">
              Wards crossing the score 75 threshold are prioritized by weighted demand index: risk score multiplied by population density and drainage strain.
            </p>
          </div>
          <div>
            <div className="ui-label mb-2">Alert Routing</div>
            <p className="ui-body">
              RED alerts trigger immediate multi-channel dispatch, while YELLOW alerts run advisory cadence with cooldown windows to reduce notification fatigue.
            </p>
          </div>
        </div>
        <GlowButton variant="ghost" className="mt-5">
          View Operational Playbook
        </GlowButton>
      </GlassPanel>
    </AppShell>
  );
}
