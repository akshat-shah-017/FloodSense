import { motion } from 'framer-motion';
import type { GeoJSONGeometry } from '../../types';
import GlassPanel from '../system/GlassPanel';

interface WardMiniMapProps {
  geometry?: GeoJSONGeometry;
  wardName: string;
}

function extractRing(geometry?: GeoJSONGeometry): Array<[number, number]> | null {
  if (!geometry || !geometry.coordinates) {
    return null;
  }

  if (geometry.type === 'Polygon') {
    const polygon = geometry.coordinates as number[][][];
    const ring = polygon?.[0];
    if (!Array.isArray(ring) || ring.length < 3) {
      return null;
    }
    return ring.map((point) => [Number(point[0]), Number(point[1])]);
  }

  if (geometry.type === 'MultiPolygon') {
    const multi = geometry.coordinates as number[][][][];
    const candidates = multi
      ?.map((poly) => poly?.[0])
      .filter((ring): ring is number[][] => Array.isArray(ring) && ring.length >= 3);

    if (!candidates?.length) {
      return null;
    }

    const largest = candidates.reduce((max, ring) => (ring.length > max.length ? ring : max), candidates[0]);
    return largest.map((point) => [Number(point[0]), Number(point[1])]);
  }

  return null;
}

function buildPath(points: Array<[number, number]>, width = 260, height = 170, padding = 14): string {
  const lngValues = points.map(([lng]) => lng);
  const latValues = points.map(([, lat]) => lat);
  const minLng = Math.min(...lngValues);
  const maxLng = Math.max(...lngValues);
  const minLat = Math.min(...latValues);
  const maxLat = Math.max(...latValues);

  const safeLngRange = maxLng - minLng || 1;
  const safeLatRange = maxLat - minLat || 1;
  const drawWidth = width - padding * 2;
  const drawHeight = height - padding * 2;

  return points
    .map(([lng, lat], index) => {
      const x = padding + ((lng - minLng) / safeLngRange) * drawWidth;
      const y = height - padding - ((lat - minLat) / safeLatRange) * drawHeight;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ')
    .concat(' Z');
}

export default function WardMiniMap({ geometry, wardName }: WardMiniMapProps) {
  const ring = extractRing(geometry);

  return (
    <GlassPanel>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="ui-headline text-lg">Ward Blueprint</h2>
        <span className="ui-label">Geo Boundary</span>
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-outline/25 bg-surface-container/60 p-3">
        <div className="pointer-events-none absolute -left-12 top-0 h-36 w-36 rounded-full bg-primary/20 blur-3xl" />

        {!ring ? (
          <div className="flex h-[170px] items-center justify-center text-sm text-on-surface-variant">
            Boundary geometry unavailable for this ward.
          </div>
        ) : (
          <svg viewBox="0 0 260 170" className="h-[170px] w-full">
            <defs>
              <linearGradient id="ward-fill-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgba(56,189,248,0.48)" />
                <stop offset="100%" stopColor="rgba(14,165,233,0.16)" />
              </linearGradient>
            </defs>

            <motion.path
              d={buildPath(ring)}
              fill="url(#ward-fill-gradient)"
              stroke="rgba(56,189,248,0.85)"
              strokeWidth="1.8"
              initial={{ pathLength: 0, opacity: 0.4 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            />
          </svg>
        )}
      </div>

      <div className="mt-3 text-sm font-semibold text-on-surface">{wardName}</div>
    </GlassPanel>
  );
}

