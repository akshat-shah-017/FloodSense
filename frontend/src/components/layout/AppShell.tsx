import { motion } from 'framer-motion';
import { useIsMutating } from '@tanstack/react-query';
import { useEffect, type ReactNode } from 'react';
import Sidebar from './Sidebar';
import RainLoader from '../system/RainLoader';
import Topbar from './Topbar';
import { pageTransition } from '../system/motion';

interface AppShellProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  headerStats?: ReactNode;
  rightPanel?: ReactNode;
  children: ReactNode;
}

export default function AppShell({
  title,
  subtitle,
  actions,
  headerStats,
  rightPanel,
  children,
}: AppShellProps) {
  const activeInferenceMutations = useIsMutating({ mutationKey: ['inference', 'predict'] });

  useEffect(() => {
    document.title = `${title} · FloodSense`;
  }, [title]);

  return (
    <div className="min-h-screen w-full text-on-surface">
      <Sidebar />

      <div className="lg:pl-[272px]">
        <Topbar title={title} subtitle={subtitle} actions={actions} />

        <motion.main
          initial={pageTransition.initial}
          animate={pageTransition.animate}
          exit={pageTransition.exit}
          transition={pageTransition.transition}
          className="mx-auto max-w-[1800px] px-4 pb-24 pt-6 lg:px-6 lg:pb-8"
        >
          {headerStats ? <section className="mb-6">{headerStats}</section> : null}

          {rightPanel ? (
            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
              <div>{children}</div>
              <aside className="space-y-4">{rightPanel}</aside>
            </div>
          ) : (
            children
          )}
        </motion.main>
      </div>

      {activeInferenceMutations > 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          className="pointer-events-none fixed bottom-6 right-6 z-[80] rounded-2xl border border-outline/25 bg-surface/75 px-4 py-2 shadow-glass-lg backdrop-blur-xl"
        >
          <RainLoader mode="compact" label="Running FloodSense inference" />
        </motion.div>
      ) : null}
    </div>
  );
}
