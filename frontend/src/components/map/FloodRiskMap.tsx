import type { GeoJsonObject } from 'geojson';
import L, { type LeafletMouseEvent, type PathOptions } from 'leaflet';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { GeoJSON, MapContainer, Popup, TileLayer, ZoomControl } from 'react-leaflet';
import { useCurrentPredictions } from '../../hooks/usePredictions';
import type { GeoJSONFeature, WardPrediction } from '../../types';
import MapLegend from './MapLegend';
import WardPreviewPopup from './WardPreviewPopup';

interface FloodRiskMapProps {
  selectedWardId: number | null;
  onSelectWard: (wardId: number | null) => void;
  onNavigateToWard: (wardId: number) => void;
}

const tierColorMap: Record<string, string> = {
  HIGH: 'rgba(248,113,113,0.85)',
  MEDIUM: 'rgba(245,158,11,0.8)',
  LOW: 'rgba(52,211,153,0.7)',
  UNKNOWN: 'rgba(148,163,184,0.62)',
};

function styleForTier(tier?: string, selected = false, hovered = false): PathOptions {
  const fillColor = tierColorMap[tier ?? 'UNKNOWN'] ?? tierColorMap.UNKNOWN;
  const emphasis = selected || hovered;

  return {
    fillColor,
    fillOpacity: emphasis ? 0.84 : 0.56,
    color: emphasis ? 'rgba(56,189,248,0.95)' : 'rgba(148,163,184,0.25)',
    weight: emphasis ? 2.2 : 1,
    interactive: true,
  };
}

function getWardLayerCenter(layer: L.Layer): L.LatLng | null {
  const asBoundsLayer = layer as L.Layer & { getBounds?: () => L.LatLngBounds };
  if (!asBoundsLayer.getBounds) {
    return null;
  }
  return asBoundsLayer.getBounds().getCenter();
}

export default function FloodRiskMap({ selectedWardId, onSelectWard, onNavigateToWard }: FloodRiskMapProps) {
  const { data, isLoading, isError } = useCurrentPredictions();
  const mapRef = useRef<L.Map | null>(null);
  const wardLayerRef = useRef<Record<number, L.Layer>>({});
  const [hoveredWardId, setHoveredWardId] = useState<number | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<{
    position: L.LatLngExpression;
    props: WardPrediction;
  } | null>(null);

  const featureMap = useMemo(() => {
    const map = new Map<number, WardPrediction>();
    data?.features.forEach((feature) => {
      if (typeof feature.properties?.ward_id === 'number') {
        map.set(feature.properties.ward_id, feature.properties);
      }
    });
    return map;
  }, [data]);

  const geoData = useMemo(
    () => ({
      type: 'FeatureCollection' as const,
      features: data?.features ?? [],
    }),
    [data]
  );

  const geoDataRevision = useMemo(() => {
    if (!data?.features?.length) {
      return 'empty';
    }

    let latest = '';
    let checksum = 0;
    for (const feature of data.features) {
      const props = feature.properties;
      const wardId = Number(props?.ward_id ?? 0);
      const score = Number(props?.risk_score ?? 0);
      const predictedAt = String(props?.predicted_at ?? '');
      checksum += Math.round((wardId * 7) + (score * 10));
      if (predictedAt && predictedAt > latest) {
        latest = predictedAt;
      }
    }

    return `${data.features.length}:${latest}:${checksum}`;
  }, [data]);

  const applyLayerStyle = useCallback(
    (wardId: number, layer: L.Layer) => {
      const path = layer as L.Path;
      if (!path.setStyle) {
        return;
      }
      const tier = featureMap.get(wardId)?.risk_tier;
      const selected = selectedWardId === wardId;
      const hovered = hoveredWardId === wardId;
      path.setStyle(styleForTier(tier, selected, hovered));
    },
    [featureMap, hoveredWardId, selectedWardId]
  );

  useEffect(() => {
    Object.entries(wardLayerRef.current).forEach(([wardId, layer]) => {
      applyLayerStyle(Number(wardId), layer);
    });
  }, [applyLayerStyle]);

  useEffect(() => {
    wardLayerRef.current = {};
  }, [geoDataRevision]);

  useEffect(() => {
    if (!selectedWardId) {
      return;
    }

    const selectedLayer = wardLayerRef.current[selectedWardId];
    const selectedProps = featureMap.get(selectedWardId);
    if (!selectedLayer || !selectedProps) {
      return;
    }

    const center = getWardLayerCenter(selectedLayer);
    if (!center) {
      return;
    }

    mapRef.current?.flyTo(center, 12, { duration: 0.35 });
    setSelectedFeature({
      position: center,
      props: selectedProps,
    });
  }, [featureMap, selectedWardId]);

  useEffect(() => {
    setSelectedFeature((current) => {
      if (!current) {
        return current;
      }

      const latestProps = featureMap.get(current.props.ward_id);
      if (!latestProps) {
        return current;
      }

      const unchanged =
        latestProps.predicted_at === current.props.predicted_at &&
        Number(latestProps.risk_score) === Number(current.props.risk_score) &&
        latestProps.risk_tier === current.props.risk_tier &&
        latestProps.source_status === current.props.source_status;

      if (unchanged) {
        return current;
      }

      return {
        ...current,
        props: latestProps,
      };
    });
  }, [featureMap]);

  const debugWardProps = useMemo(() => {
    if (!selectedWardId) {
      return null;
    }
    return featureMap.get(selectedWardId) ?? null;
  }, [featureMap, selectedWardId]);

  const onEachFeature = useCallback(
    (feature: GeoJSONFeature, layer: L.Layer) => {
      const props = feature.properties as WardPrediction;
      const wardId = props?.ward_id;

      if (typeof wardId !== 'number') {
        return;
      }

      wardLayerRef.current[wardId] = layer;
      applyLayerStyle(wardId, layer);

      const roundedScore = Math.round(Number(props.risk_score ?? 0));
      const tooltipHtml = `
        <div style="display:flex;flex-direction:column;gap:2px;">
          <strong style="font-size:12px;">${props.ward_name}</strong>
          <span style="font-size:11px;opacity:0.9;">Risk ${roundedScore} • ${props.risk_tier}</span>
        </div>
      `;

      (layer as L.Path).bindTooltip(tooltipHtml, {
        sticky: true,
        direction: 'top',
        className: 'floodsense-map-tooltip',
        opacity: 1,
      });

      layer.on({
        mouseover: () => {
          setHoveredWardId(wardId);
          (layer as L.Path).openTooltip();
        },
        mouseout: () => {
          setHoveredWardId((current) => (current === wardId ? null : current));
        },
        click: (event: LeafletMouseEvent) => {
          if (import.meta.env.DEV) {
            console.info('[WardMap Click]', {
              wardId,
              wardName: props.ward_name,
              riskScore: props.risk_score,
              tier: props.risk_tier,
              dataSource: 'predictions/current',
            });
          }
          onSelectWard(wardId);
          const center = getWardLayerCenter(layer) ?? event.latlng;
          mapRef.current?.flyTo(center, 12, { duration: 0.35 });
          setSelectedFeature({
            position: center,
            props,
          });
        },
      });
    },
    [applyLayerStyle, onSelectWard]
  );

  const hasFeatures = (data?.features?.length ?? 0) > 0;

  return (
    <div className="relative h-[560px] w-full overflow-hidden rounded-3xl border border-outline/25 bg-surface-container/35 shadow-glass-lg">
      <MapContainer
        className="h-full w-full"
        style={{ height: '100%', width: '100%' }}
        center={[28.6139, 77.209]}
        zoom={10}
        zoomControl={false}
        whenCreated={(map) => {
          mapRef.current = map;
        }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />
        <ZoomControl position="topright" />

        <GeoJSON
          key={geoDataRevision}
          data={geoData as unknown as GeoJsonObject}
          style={(feature) => {
            const typed = feature as GeoJSONFeature;
            const wardId = typed?.properties?.ward_id;
            const tier = typed?.properties?.risk_tier;
            return styleForTier(
              tier,
              typeof wardId === 'number' ? selectedWardId === wardId : false,
              typeof wardId === 'number' ? hoveredWardId === wardId : false
            );
          }}
          onEachFeature={(feature, layer) => onEachFeature(feature as GeoJSONFeature, layer)}
        />

        {selectedFeature ? (
          <Popup
            position={selectedFeature.position}
            onClose={() => setSelectedFeature(null)}
            maxWidth={310}
            minWidth={290}
          >
            <WardPreviewPopup
              ward={selectedFeature.props}
              onViewDetails={() => onNavigateToWard(selectedFeature.props.ward_id)}
            />
          </Popup>
        ) : null}
      </MapContainer>

      <MapLegend />

      {import.meta.env.DEV ? (
        <div className="pointer-events-none absolute left-3 top-3 z-[600] rounded-xl border border-outline/35 bg-surface/85 px-3 py-2 backdrop-blur-sm">
          <div className="ui-label">Debug Trace</div>
          <div className="mt-1 text-[11px] text-on-surface-variant">
            WARD {debugWardProps?.ward_id ?? '—'} | SCORE{' '}
            {typeof debugWardProps?.risk_score === 'number'
              ? debugWardProps.risk_score.toFixed(2)
              : '—'}{' '}
            | SOURCE {debugWardProps?.source_status ?? '—'}
          </div>
        </div>
      ) : null}

      {!isLoading && !isError && !hasFeatures ? (
        <div className="absolute inset-0 z-[500] flex items-center justify-center bg-surface/58 backdrop-blur-[1px]">
          <div className="rounded-2xl border border-outline/30 bg-surface-container/90 px-4 py-3 text-sm text-on-surface-variant">
            No ward predictions yet. Run inference to render ward overlays.
          </div>
        </div>
      ) : null}

      {isLoading ? (
        <div className="absolute inset-0 z-[500] flex items-center justify-center bg-surface/72 backdrop-blur-sm">
          <div className="glass-card p-4">
            <div className="ui-label animate-pulse text-primary">Loading ward telemetry…</div>
          </div>
        </div>
      ) : null}

      {isError ? (
        <div className="absolute inset-0 z-[500] flex items-center justify-center bg-surface/72 backdrop-blur-sm">
          <div className="rounded-2xl border border-error/30 bg-error/12 px-4 py-3 text-sm text-error">
            Telemetry feed unavailable. Please check API connectivity.
          </div>
        </div>
      ) : null}
    </div>
  );
}
