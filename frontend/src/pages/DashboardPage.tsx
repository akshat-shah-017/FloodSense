import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import TopStatsBar from '../components/layout/TopStatsBar';
import FloodRiskMap from '../components/map/FloodRiskMap';
import AIDecisionPanel from '../components/panels/AIDecisionPanel';
import SimulationBar from '../components/panels/SimulationBar';
import GlassPanel from '../components/system/GlassPanel';
import { useSystemStats } from '../hooks/useStats';

export default function DashboardPage() {
  const [selectedWardId, setSelectedWardId] = useState<number | null>(null);
  const { data: stats, isLoading } = useSystemStats();
  const navigate = useNavigate();

  return (
    <AppShell
      title="FloodSense Dashboard"
      headerStats={<TopStatsBar stats={stats} isLoading={isLoading} />}
      rightPanel={<AIDecisionPanel onSelectWard={(wardId) => setSelectedWardId(wardId)} />}
    >
      <GlassPanel className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="ui-headline text-xl">Live Ward Risk Map</h2>
          <p className="ui-label">Hover for telemetry, click for profile</p>
        </div>

        <FloodRiskMap
          selectedWardId={selectedWardId}
          onSelectWard={setSelectedWardId}
          onNavigateToWard={(id) => navigate(`/ward/${id}`)}
        />
      </GlassPanel>

      <SimulationBar />
    </AppShell>
  );
}
