import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getRootHealth } from '../../api/endpoints';
import { Play, Activity, Menu, X, ArrowUpRight } from 'lucide-react';

interface TopNavProps {
  onToggleSidebar?: () => void;
  isSidebarOpen?: boolean;
}

export const TopNav: React.FC<TopNavProps> = ({ onToggleSidebar, isSidebarOpen }) => {
  const location = useLocation();

  const { data: health, isSuccess, isError } = useQuery({
    queryKey: ['rootHealth'],
    queryFn: getRootHealth,
    refetchInterval: 15000,
  });

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-black">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6">
        {/* Left: Mobile Toggle & Brand */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="md:hidden p-1.5 border border-black hover:bg-zinc-100 cursor-pointer"
            aria-label="Toggle menu"
          >
            {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <Link to="/" className="flex items-center gap-2 group">
            {/* Devlab style // BRA logo */}
            <span className="font-bold text-xl sm:text-2xl tracking-tighter text-black flex items-center">
              <span className="text-zinc-400 font-mono mr-1.5">//</span>
              <span>BRA</span>
            </span>
            <span className="hidden sm:inline-block text-[11px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 border border-black bg-zinc-100 text-zinc-800">
              Backtest Reliability Analyzer
            </span>
          </Link>
        </div>

        {/* Center: Quick navigation links (Devlab style) */}
        <nav className="hidden lg:flex items-center gap-8 text-xs font-bold uppercase tracking-wider font-mono">
          <Link
            to="/dashboard"
            className={`transition-colors hover:text-[#ff3b30] ${
              location.pathname === '/dashboard' ? 'text-[#ff3b30] underline underline-offset-4' : 'text-zinc-700'
            }`}
          >
            Dashboard
          </Link>
          <Link
            to="/datasets"
            className={`transition-colors hover:text-[#ff3b30] ${
              location.pathname.startsWith('/datasets') ? 'text-[#ff3b30] underline underline-offset-4' : 'text-zinc-700'
            }`}
          >
            Datasets
          </Link>
          <Link
            to="/validation"
            className={`transition-colors hover:text-[#ff3b30] ${
              location.pathname === '/validation' ? 'text-[#ff3b30] underline underline-offset-4' : 'text-zinc-700'
            }`}
          >
            Validation
          </Link>
          <Link
            to="/runs"
            className={`transition-colors hover:text-[#ff3b30] ${
              location.pathname.startsWith('/runs') ? 'text-[#ff3b30] underline underline-offset-4' : 'text-zinc-700'
            }`}
          >
            Analysis Runs
          </Link>
          <Link
            to="/reports"
            className={`transition-colors hover:text-[#ff3b30] ${
              location.pathname.startsWith('/reports') ? 'text-[#ff3b30] underline underline-offset-4' : 'text-zinc-700'
            }`}
          >
            Reports
          </Link>
          <Link
            to="/status"
            className={`transition-colors hover:text-[#ff3b30] ${
              location.pathname === '/status' ? 'text-[#ff3b30] underline underline-offset-4' : 'text-zinc-700'
            }`}
          >
            System Status
          </Link>
        </nav>

        {/* Right: Health Badge & Primary Action */}
        <div className="flex items-center gap-3">
          {/* Live API Status indicator */}
          <Link
            to="/status"
            className="flex items-center gap-2 px-2.5 py-1 text-[11px] font-mono border border-black bg-white hover:bg-zinc-50 transition-colors"
            title="Backend Health Status"
          >
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                isSuccess && health?.status === 'ok'
                  ? 'bg-[#16a34a] ring-2 ring-[#dcfce7]'
                  : isError
                  ? 'bg-[#dc2626] ring-2 ring-[#fee2e2]'
                  : 'bg-[#d97706]'
              }`}
            />
            <span className="font-bold hidden sm:inline">
              {isSuccess && health?.status === 'ok' ? 'API: ONLINE' : isError ? 'API: OFFLINE' : 'CHECKING'}
            </span>
          </Link>

          {/* Devlab style solid black pill button */}
          <Link
            to="/runs"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold font-mono tracking-wider text-white bg-black border border-black rounded-full hover:bg-zinc-800 transition-all hover:shadow-sm"
          >
            <span>NEW RUN</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </header>
  );
};
