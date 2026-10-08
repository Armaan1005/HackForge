import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { TopNav } from './components/TopNav';
import { fade, ThemeProvider } from './lib/theme';
import { CaseView } from './pages/CaseView';
import { Challenge } from './pages/Challenge';
import { Command } from './pages/Command';
import { Explained } from './pages/Explained';
import { QueuePage } from './pages/Queue';
import { Trust } from './pages/Trust';
import { Twin } from './pages/Twin';

function Page({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <motion.main key={pathname} className="page container" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={fade}>
      {children}
    </motion.main>
  );
}

const shell = (el: ReactNode) => <><TopNav /><Page>{el}</Page></>;

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={shell(<Command />)} />
          <Route path="/queue" element={shell(<QueuePage />)} />
          <Route path="/cases/:id" element={shell(<CaseView />)} />
          <Route path="/explained" element={shell(<Explained />)} />
          <Route path="/twin" element={shell(<Twin />)} />
          <Route path="/trust" element={shell(<Trust />)} />
          <Route path="/challenge" element={<Challenge />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
