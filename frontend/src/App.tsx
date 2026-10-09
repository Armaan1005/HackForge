import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Toasts } from './components/Toasts';
import { TopNav } from './components/TopNav';
import { fade } from './lib/theme';
import { CaseView } from './pages/CaseView';
import { Challenge } from './pages/Challenge';
import { Command } from './pages/Command';
import { CourtPage } from './pages/Court';
import { Explained } from './pages/Explained';
import { Landing } from './pages/Landing';
import { QueuePage } from './pages/Queue';
import { Rulebook } from './pages/Rulebook';
import { Trust } from './pages/Trust';
import { Timelines } from './pages/Timelines';
import { Twin } from './pages/Twin';

function Page({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <motion.main key={pathname} className="page container" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={fade}>
      <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>
    </motion.main>
  );
}

const shell = (el: ReactNode) => <><TopNav /><Page>{el}</Page></>;

export default function App() {
  return (
    <BrowserRouter>
        <Toasts />
        <Routes>
          <Route path="/" element={<ErrorBoundary><Landing /></ErrorBoundary>} />
          <Route path="/home" element={shell(<Command />)} />
          <Route path="/queue" element={shell(<QueuePage />)} />
          <Route path="/court" element={shell(<CourtPage />)} />
          <Route path="/cases/:id" element={shell(<CaseView />)} />
          <Route path="/explained" element={shell(<Explained />)} />
          <Route path="/twin" element={shell(<Twin />)} />
          <Route path="/without-axon" element={shell(<Timelines />)} />
          <Route path="/timelines" element={<Navigate to="/without-axon" replace />} />
          <Route path="/deal-breaker" element={<Navigate to="/without-axon" replace />} />
          <Route path="/rulebook" element={shell(<Rulebook />)} />
          <Route path="/trust" element={shell(<Trust />)} />
          <Route path="/challenge" element={<Challenge />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    </BrowserRouter>
  );
}
