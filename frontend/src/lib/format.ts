export function toTitleCase(raw: string): string {
  return raw
    .replace(/_/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function relativeTime(isoString?: string): string {
  if (!isoString) {
    return '—';
  }

  const timestamp = new Date(isoString).getTime();
  if (Number.isNaN(timestamp)) {
    return '—';
  }

  const diffMs = Date.now() - timestamp;
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diffMs < hour) {
    return `${Math.max(1, Math.floor(diffMs / minute))} min ago`;
  }
  if (diffMs < day) {
    return `${Math.max(1, Math.floor(diffMs / hour))} hr ago`;
  }
  return `${Math.max(1, Math.floor(diffMs / day))} days ago`;
}

export function formatChartDate(isoString?: string): string {
  if (!isoString) {
    return '—';
  }

  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}
