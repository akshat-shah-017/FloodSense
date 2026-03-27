import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import RainLoader from './components/system/RainLoader';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const WardDetailPage = lazy(() => import('./pages/WardDetailPage'));
const HistoricalPage = lazy(() => import('./pages/HistoricalPage'));
const ResourcesPage = lazy(() => import('./pages/ResourcesPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const PublicMapPage = lazy(() => import('./pages/PublicMapPage'));

function RouteFallback() {
  return <RainLoader mode="full" />;
}

function RouteTransitionOverlay() {
  const location = useLocation();
  const isFirstRoute = useRef(true);
  const [showOverlay, setShowOverlay] = useState(false);

  useEffect(() => {
    if (isFirstRoute.current) {
      isFirstRoute.current = false;
      return;
    }

    setShowOverlay(true);
    const timer = window.setTimeout(() => setShowOverlay(false), 340);
    return () => window.clearTimeout(timer);
  }, [location.pathname]);

  return (
    <AnimatePresence>
      {showOverlay ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="pointer-events-none fixed inset-0 z-[120] flex items-center justify-center bg-surface/55 backdrop-blur-sm"
        >
          <div className="rounded-3xl border border-outline/25 bg-surface-container/75 px-8 py-6 shadow-glass-lg">
            <RainLoader mode="compact" />
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function AppRoutes() {
  const location = useLocation();

  return (
    <>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route
            path="/"
            element={
              <Suspense fallback={<RouteFallback />}>
                <DashboardPage />
              </Suspense>
            }
          />
          <Route
            path="/ward/:wardId"
            element={
              <Suspense fallback={<RouteFallback />}>
                <WardDetailPage />
              </Suspense>
            }
          />
          <Route
            path="/historical"
            element={
              <Suspense fallback={<RouteFallback />}>
                <HistoricalPage />
              </Suspense>
            }
          />
          <Route
            path="/resources"
            element={
              <Suspense fallback={<RouteFallback />}>
                <ResourcesPage />
              </Suspense>
            }
          />
          <Route
            path="/settings"
            element={
              <Suspense fallback={<RouteFallback />}>
                <SettingsPage />
              </Suspense>
            }
          />
          <Route
            path="/public-map"
            element={
              <Suspense fallback={<RouteFallback />}>
                <PublicMapPage />
              </Suspense>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AnimatePresence>
      <RouteTransitionOverlay />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
