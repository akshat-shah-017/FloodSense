import { BarChart3, LayoutDashboard, Package, Settings } from 'lucide-react';
import { useSystemStats } from '../../hooks/useStats';
import { relativeTime } from '../../lib/format';
import StatusBadge, { toneFromTier } from '../system/StatusBadge';
import ProjectLogo from '../ui/ProjectLogo';
import SidebarItem from './SidebarItem';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, disabled: false },
  { to: '/historical', label: 'Historical', icon: BarChart3, disabled: false },
  { to: '/resources', label: 'Resources', icon: Package, disabled: false },
  { to: '/settings', label: 'Settings', icon: Settings, disabled: false },
];

export default function Sidebar() {
  const { data: stats } = useSystemStats();
  const highRisk = stats?.risk_distribution?.HIGH ?? 0;

  return (
    <>
      <aside className="fixed inset-y-4 left-4 z-40 hidden w-[252px] flex-col rounded-3xl border border-outline/25 bg-surface-container/65 p-4 shadow-glass-lg backdrop-blur-xl lg:flex">
        <div className="mb-8">
          <div className="mb-3 flex items-center gap-3">
            <ProjectLogo className="h-10 w-10 rounded-2xl border border-outline/25 object-cover object-[14%_50%] shadow-glass" />
            <div>
              <div className="ui-label mb-1">FloodSense Command</div>
              <h2 className="ui-headline text-[28px] leading-tight">FloodSense</h2>
            </div>
          </div>
          <p className="ui-body mt-2">Ward-level flood intelligence for city response teams.</p>
        </div>

        <nav className="space-y-2">
          {navItems.map((item) => (
            <SidebarItem
              key={item.label}
              to={item.to}
              label={item.label}
              icon={item.icon}
              disabled={item.disabled}
            />
          ))}
        </nav>

        <div className="mt-auto rounded-2xl border border-outline/20 bg-surface/65 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="ui-label">Control Status</span>
            <StatusBadge label={highRisk > 0 ? 'Watched' : 'Clear'} tone={toneFromTier(highRisk > 0 ? 'YELLOW' : 'LOW')} />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-on-surface-variant">High risk wards</span>
              <span className="font-mono text-on-surface">{highRisk}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-on-surface-variant">Last inference</span>
              <span className="font-mono text-on-surface">{relativeTime(stats?.last_inference_at)}</span>
            </div>
          </div>
        </div>
      </aside>

      <nav className="fixed inset-x-4 bottom-4 z-40 rounded-2xl border border-outline/20 bg-surface/80 p-2 shadow-glass backdrop-blur-xl lg:hidden">
        <div className="grid grid-cols-4 gap-2">
          {navItems
            .filter((item) => !item.disabled)
            .map((item) => (
              <SidebarItem key={item.to} to={item.to} label={item.label} icon={item.icon} />
            ))}
        </div>
      </nav>
    </>
  );
}
