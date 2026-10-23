import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { AppLayout } from './components/layout/AppLayout';
import { LandingPage } from './pages/LandingPage';
import { OverviewDashboard } from './pages/OverviewDashboard';
import { DatasetsPage } from './pages/Datasets/DatasetsPage';
import { DatasetDetailPage } from './pages/Datasets/DatasetDetailPage';
import { ValidationPage } from './pages/Validation/ValidationPage';
import { SurvivorshipPage } from './pages/Survivorship/SurvivorshipPage';
import { LookAheadPage } from './pages/LookAhead/LookAheadPage';
import { CorporateActionsPage } from './pages/CorporateActions/CorporateActionsPage';
import { AnalysisRunsPage } from './pages/AnalysisRuns/AnalysisRunsPage';
import { AnalysisRunDetailPage } from './pages/AnalysisRuns/AnalysisRunDetailPage';
import { FindingsExplorerPage } from './pages/Findings/FindingsExplorerPage';
import { ReportsPage } from './pages/Reports/ReportsPage';
import { SystemStatusPage } from './pages/SystemStatus/SystemStatusPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 30, // 30 seconds
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public Devlab Landing Page */}
          <Route path="/" element={<LandingPage />} />

          {/* Internal Dashboard & Audit Workspace */}
          <Route
            path="/*"
            element={
              <AppLayout>
                <Routes>
                  <Route path="/dashboard" element={<OverviewDashboard />} />
                  <Route path="/datasets" element={<DatasetsPage />} />
                  <Route path="/datasets/:datasetId" element={<DatasetDetailPage />} />
                  <Route path="/validation" element={<ValidationPage />} />
                  <Route path="/survivorship" element={<SurvivorshipPage />} />
                  <Route path="/lookahead" element={<LookAheadPage />} />
                  <Route path="/corporate-actions" element={<CorporateActionsPage />} />
                  <Route path="/runs" element={<AnalysisRunsPage />} />
                  <Route path="/runs/:runId" element={<AnalysisRunDetailPage />} />
                  <Route path="/findings" element={<FindingsExplorerPage />} />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/system" element={<SystemStatusPage />} />
                  <Route path="/status" element={<SystemStatusPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </AppLayout>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
