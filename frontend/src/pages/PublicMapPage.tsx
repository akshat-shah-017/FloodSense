import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import FloodRiskMap from '../components/map/FloodRiskMap';
import GlassPanel from '../components/system/GlassPanel';

export default function PublicMapPage() {
  const [selectedWardId, setSelectedWardId] = useState<number | null>(null);
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-hero-gradient px-4 py-4 text-on-surface lg:px-6">
      <GlassPanel className="mb-4 flex items-center justify-between p-4">
        <div>
          <h1 className="ui-headline text-xl">FloodSense Public Map</h1>
          <p className="ui-body mt-1">Open ward-level risk visualization for public monitoring.</p>
        </div>
        <Link
          to="/"
          className="focus-ring rounded-2xl border border-outline/35 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.12em] text-on-surface transition-colors hover:border-primary/45 hover:text-primary"
        >
          Open Dashboard
        </Link>
      </GlassPanel>

      <FloodRiskMap
        selectedWardId={selectedWardId}
        onSelectWard={setSelectedWardId}
        onNavigateToWard={(wardId) => navigate(`/ward/${wardId}`)}
      />
    </div>
  );
}

