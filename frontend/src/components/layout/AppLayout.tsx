import React, { useState } from 'react';
import { Outlet, useLocation, Link } from 'react-router-dom';
import { TopNav } from './TopNav';
import { Sidebar } from './Sidebar';
import { ChevronRight, Home } from 'lucide-react';

interface AppLayoutProps {
  children?: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const location = useLocation();

  // Generate breadcrumb items from pathname
  const pathParts = location.pathname.split('/').filter(Boolean);
  const breadcrumbs = [
    { label: 'Home', path: '/' },
    ...pathParts.map((part, index) => {
      const url = `/${pathParts.slice(0, index + 1).join('/')}`;
      const formattedLabel = part
        .replace(/-/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
      return { label: formattedLabel, path: url };
    }),
  ];

  return (
    <div className="min-h-screen bg-[#f8f9fa] flex flex-col font-sans">
      <TopNav
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        isSidebarOpen={isSidebarOpen}
      />

      <div className="flex-1 flex">
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
        />

        {/* Main Content Area */}
        <main className="flex-1 md:pl-64 flex flex-col min-w-0">
          {/* Breadcrumbs & Status Bar */}
          <div className="px-6 py-3 border-b border-black bg-white flex items-center justify-between gap-4 text-xs font-mono">
            <nav className="flex items-center gap-1.5 overflow-x-auto whitespace-nowrap">
              {breadcrumbs.map((crumb, idx) => {
                const isLast = idx === breadcrumbs.length - 1;
                return (
                  <React.Fragment key={crumb.path}>
                    {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-zinc-400 shrink-0" />}
                    {isLast ? (
                      <span className="font-bold text-black bg-zinc-100 px-2 py-0.5 border border-black">
                        {crumb.label}
                      </span>
                    ) : (
                      <Link
                        to={crumb.path}
                        className="text-zinc-600 hover:text-black hover:underline transition-colors flex items-center gap-1"
                      >
                        {idx === 0 && <Home className="w-3 h-3" />}
                        <span>{crumb.label}</span>
                      </Link>
                    )}
                  </React.Fragment>
                );
              })}
            </nav>

            <div className="hidden sm:flex items-center gap-3 text-[11px] text-zinc-500 font-bold uppercase">
              <span className="text-[#ff3b30]">✦</span>
              <span>QUANT AUDIT PLATFORM</span>
            </div>
          </div>

          {/* Page Viewport */}
          <div className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
            {children || <Outlet />}
          </div>

          {/* Footer Bar */}
          <footer className="mt-auto px-6 py-4 border-t border-black bg-white text-xs font-mono flex flex-col sm:flex-row items-center justify-between gap-3 text-zinc-600">
            <div>
              <span className="font-bold text-black">// BRA</span> — Backtest Reliability Analyzer © 2026. Audit & Bias Verification.
            </div>
            <div className="flex items-center gap-4 text-[11px]">
              <span>FastAPI 0.1.0</span>
              <span>•</span>
              <span>Zero-Hardcoding Engine</span>
              <span>•</span>
              <span className="text-[#ff3b30] font-bold">NSE Point-in-Time</span>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
};
