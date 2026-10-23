import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Database,
  CheckCircle2,
  TrendingDown,
  Clock,
  Sparkles,
  PlaySquare,
  Search,
  FileText,
  Server,
  ChevronRight,
} from 'lucide-react';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
  badge?: string;
  badgeColor?: 'red' | 'blue' | 'black';
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen = false, onClose }) => {
  const sections: NavSection[] = [
    {
      title: 'OVERVIEW',
      items: [
        {
          label: 'Dashboard',
          to: '/',
          icon: <LayoutDashboard className="w-4 h-4" />,
        },
      ],
    },
    {
      title: 'DATA MANAGEMENT',
      items: [
        {
          label: 'Datasets & Schemas',
          to: '/datasets',
          icon: <Database className="w-4 h-4" />,
        },
        {
          label: 'Data Validation',
          to: '/validation',
          icon: <CheckCircle2 className="w-4 h-4" />,
        },
      ],
    },
    {
      title: 'BIAS ANALYZERS',
      items: [
        {
          label: 'Survivorship Bias',
          to: '/survivorship',
          icon: <TrendingDown className="w-4 h-4" />,
          badge: 'CORE',
          badgeColor: 'blue',
        },
        {
          label: 'Look-Ahead Bias',
          to: '/lookahead',
          icon: <Clock className="w-4 h-4" />,
          badge: 'TEMPORAL',
          badgeColor: 'red',
        },
        {
          label: 'Corporate Actions',
          to: '/corporate-actions',
          icon: <Sparkles className="w-4 h-4" />,
        },
      ],
    },
    {
      title: 'PIPELINE & AUDITS',
      items: [
        {
          label: 'Analysis Runs',
          to: '/runs',
          icon: <PlaySquare className="w-4 h-4" />,
        },
        {
          label: 'Findings Explorer',
          to: '/findings',
          icon: <Search className="w-4 h-4" />,
        },
        {
          label: 'Reports & Exports',
          to: '/reports',
          icon: <FileText className="w-4 h-4" />,
        },
      ],
    },
    {
      title: 'SYSTEM',
      items: [
        {
          label: 'API & Metadata',
          to: '/status',
          icon: <Server className="w-4 h-4" />,
        },
      ],
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Shell */}
      <aside
        className={`fixed top-16 bottom-0 left-0 z-30 w-64 bg-white border-r border-black flex flex-col transition-transform duration-200 ease-in-out md:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {sections.map((section, idx) => (
            <div key={idx} className="space-y-1.5">
              <div className="px-2 text-[10px] font-mono font-bold uppercase tracking-wider text-zinc-400">
                {section.title}
              </div>
              <div className="space-y-1">
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `flex items-center justify-between px-3 py-2 text-xs font-mono font-bold tracking-tight border transition-all ${
                        isActive
                          ? 'bg-black text-white border-black shadow-[2px_2px_0px_0px_#ff3b30]'
                          : 'bg-white text-zinc-800 border-transparent hover:border-black hover:bg-zinc-50'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <div className="flex items-center gap-2.5 truncate">
                          <span className={isActive ? 'text-[#ff3b30]' : 'text-zinc-600'}>
                            {item.icon}
                          </span>
                          <span className="truncate">{item.label}</span>
                        </div>

                        {item.badge ? (
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.2 border ${
                              isActive
                                ? 'bg-[#ff3b30] text-white border-white'
                                : item.badgeColor === 'red'
                                ? 'bg-red-50 text-[#ff3b30] border-[#ff3b30]'
                                : 'bg-blue-50 text-[#4a8b9f] border-[#4a8b9f]'
                            }`}
                          >
                            {item.badge}
                          </span>
                        ) : isActive ? (
                          <ChevronRight className="w-3.5 h-3.5 text-[#ff3b30]" />
                        ) : null}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Sidebar Footer info */}
        <div className="p-4 border-t border-black bg-[#fafafa] text-[11px] font-mono text-zinc-500">
          <div className="flex items-center justify-between font-bold text-black">
            <span>ENGINE v0.1.0</span>
            <span className="text-[#ff3b30]">✦ READY</span>
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">
            Canonical Dataset: <span className="font-semibold text-zinc-700">existing-data</span>
          </div>
        </div>
      </aside>
    </>
  );
};
