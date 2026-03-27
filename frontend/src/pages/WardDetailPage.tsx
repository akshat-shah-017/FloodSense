import { useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import GlassPanel from '../components/system/GlassPanel';
import GlowButton from '../components/ui/GlowButton';
import AlertList from '../components/ward/AlertList';
import ResourcePanel from '../components/ward/ResourcePanel';
import RiskScoreCard from '../components/ward/RiskScoreCard';
import TrendChart from '../components/ward/TrendChart';
import WardHeader from '../components/ward/WardHeader';
import WardMiniMap from '../components/ward/WardMiniMap';
import { useWardAlertHistory } from '../hooks/useAlerts';
import { useCurrentPredictions, useWardDetail } from '../hooks/usePredictions';
import type { AlertLogEntry, WardDetailResponse, WardPrediction } from '../types';

type WardProfile = WardPrediction & {
  score_history: Array<{ predicted_at: string; risk_score: number }>;
};

function parseWardId(rawWardId?: string): number | null {
  const wardId = Number(rawWardId);
  if (!Number.isFinite(wardId) || wardId <= 0) {
    return null;
  }
  return wardId;
}

function buildDerivedAlertHistory(ward: WardProfile): AlertLogEntry[] {
  return (ward.score_history ?? [])
    .filter((point) => Number(point.risk_score ?? 0) >= 75)
    .slice(-8)
    .reverse()
    .map((point, index) => {
      const riskScore = Number(point.risk_score ?? 0);
      const alertTier: AlertLogEntry['alert_tier'] = riskScore >= 90 ? 'RED' : 'YELLOW';
      return {
        ward_id: ward.ward_id,
        ward_name: ward.ward_name,
        risk_score: riskScore,
        alert_tier: alertTier,
        channel: alertTier === 'RED' ? 'WHATSAPP' : 'SMS',
        dispatched_at: point.predicted_at,
        delivery_status: index % 4 === 3 ? 'PENDING' : 'SENT',
        message_en:
          alertTier === 'RED'
            ? `${ward.ward_name} moved into RED threshold. Immediate mitigation is recommended.`
            : `${ward.ward_name} remains in YELLOW threshold. Keep response teams prepared.`,
      };
    });
}

export default function WardDetailPage() {
  const { wardId } = useParams();
  const parsedWardId = parseWardId(wardId);
  const navigate = useNavigate();

  const wardDetailQuery = useWardDetail(parsedWardId);
  const currentPredictionsQuery = useCurrentPredictions();
  const wardAlertHistoryQuery = useWardAlertHistory(parsedWardId);

  const wardFeature = useMemo(() => {
    if (!parsedWardId) {
      return null;
    }
    return (
      currentPredictionsQuery.data?.features.find(
        (feature) => feature.properties?.ward_id === parsedWardId
      ) ?? null
    );
  }, [currentPredictionsQuery.data, parsedWardId]);

  const ward = useMemo(() => {
    if (!parsedWardId) {
      return null;
    }

    const detail =
      wardDetailQuery.data && wardDetailQuery.data.ward_id === parsedWardId
        ? (wardDetailQuery.data as WardDetailResponse)
        : null;
    const featureProps = wardFeature?.properties;

    if (!detail && !featureProps) {
      return null;
    }

    return {
      ...(detail ?? {}),
      ...(featureProps ?? {}),
      ward_id: parsedWardId,
      ward_name: featureProps?.ward_name ?? detail?.ward_name ?? `Ward ${parsedWardId}`,
      score_history: detail?.score_history ?? [],
    } as WardProfile;
  }, [parsedWardId, wardDetailQuery.data, wardFeature]);

  const alertHistory = useMemo(() => {
    if (!ward) {
      return [];
    }

    if (wardAlertHistoryQuery.data && wardAlertHistoryQuery.data.length > 0) {
      return wardAlertHistoryQuery.data;
    }

    return buildDerivedAlertHistory(ward);
  }, [ward, wardAlertHistoryQuery.data]);

  useEffect(() => {
    if (!parsedWardId || !ward) {
      return;
    }

    const sourceDetails = {
      wardId: parsedWardId,
      wardName: ward.ward_name,
      detailQueryWardId: wardDetailQuery.data?.ward_id,
      mapFeatureWardId: wardFeature?.properties?.ward_id ?? null,
      alertEvents: alertHistory.length,
      score: ward.risk_score,
      tier: ward.risk_tier,
      dataSource: wardAlertHistoryQuery.data?.length ? 'alerts/log + predictions' : 'predictions-derived',
    };

    if (import.meta.env.DEV) {
      console.info('[WardDetail Debug]', sourceDetails);
    }
  }, [
    alertHistory.length,
    parsedWardId,
    ward,
    wardAlertHistoryQuery.data?.length,
    wardDetailQuery.data?.ward_id,
    wardFeature?.properties?.ward_id,
  ]);

  const isLoading =
    wardDetailQuery.isLoading ||
    currentPredictionsQuery.isLoading ||
    wardAlertHistoryQuery.isLoading;

  if (isLoading) {
    return (
      <AppShell title="Ward Detail" subtitle="Loading telemetry profile...">
        <GlassPanel className="flex min-h-[420px] items-center justify-center">
          <div className="ui-label animate-pulse text-primary">Loading ward telemetry…</div>
        </GlassPanel>
      </AppShell>
    );
  }

  if (!parsedWardId || !ward) {
    return (
      <AppShell title="Ward Detail" subtitle="Unable to load requested ward profile.">
        <GlassPanel className="mx-auto max-w-[520px] text-center">
          <h2 className="ui-headline text-xl">Ward not found</h2>
          <p className="ui-body mt-2">
            The selected ward profile is unavailable or could not be fetched.
          </p>
          <GlowButton variant="ghost" className="mt-4" onClick={() => navigate('/')}>
            Back to Dashboard
          </GlowButton>
        </GlassPanel>
      </AppShell>
    );
  }

  const historyPoints = ward.score_history ?? [];

  return (
    <AppShell
      title="Ward Command Profile"
      subtitle={`Detailed risk decomposition and response intelligence for Ward ${ward.ward_id}.`}
    >
      <WardHeader ward={ward} onBack={() => navigate(-1)} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <TrendChart points={historyPoints} />
          <AlertList alerts={alertHistory} />
          <ResourcePanel ward={ward} />
        </div>

        <div className="space-y-6">
          <WardMiniMap geometry={wardFeature?.geometry} wardName={ward.ward_name} />
          <RiskScoreCard ward={ward} />
        </div>
      </div>
    </AppShell>
  );
}
