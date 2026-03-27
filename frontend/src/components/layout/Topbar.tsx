import type { ReactNode } from 'react';
import ProjectLogo from '../ui/ProjectLogo';
import StatusBadge from '../system/StatusBadge';

interface TopbarProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export default function Topbar({ title, subtitle, actions }: TopbarProps) {
  return (
    <header className="sticky top-2 z-30 px-4 lg:px-6">
      <div className="mx-auto max-w-[1800px] rounded-3xl border border-outline/25 bg-surface-container/65 shadow-glass-lg backdrop-blur-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 lg:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <ProjectLogo className="h-11 w-11 rounded-2xl border border-outline/25 object-cover object-[14%_50%] shadow-glass" />
            <div className="min-w-0">
              <div className="ui-headline text-2xl leading-tight">FloodSense</div>
              <div className="ui-label mt-1 truncate">{title}</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge tone="success" label="Live Systems" pulse />
            {actions}
          </div>
        </div>

        {subtitle ? (
          <div className="border-t border-outline/15 px-4 py-2 lg:px-5">
            <p className="ui-body">{subtitle}</p>
          </div>
        ) : null}
      </div>
    </header>
  );
}
