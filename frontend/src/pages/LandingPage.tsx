import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowUpRight,
  TrendingDown,
  Clock,
  Sparkles,
  ShieldCheck,
  Database,
  FileCheck,
  CheckCircle2,
  ChevronRight,
  FileText,
  Activity,
  Layers,
  ArrowRight,
  Play,
  Download,
} from 'lucide-react';
import { GeometricGraphic } from '../components/common/GeometricGraphic';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { getRootHealth, listDatasets } from '../api/endpoints';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [activePreviewTab, setActivePreviewTab] = useState<'survivorship' | 'lookahead' | 'actions' | 'datasets'>('survivorship');

  const { data: health } = useQuery({
    queryKey: ['landingHealth'],
    queryFn: getRootHealth,
    staleTime: 30000,
  });

  const { data: datasets } = useQuery({
    queryKey: ['landingDatasets'],
    queryFn: () => listDatasets({ include_existing: true }),
    staleTime: 30000,
  });

  const isOnline = health?.status === 'ok';

  return (
    <div className="min-h-screen bg-[#f8f9fa] text-black font-sans selection:bg-black selection:text-white">
      {/* 1. Devlab Style Slim Top Navigation */}
      <header className="sticky top-0 z-50 bg-white border-b border-black">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-1.5 group">
              <span className="font-bold text-2xl tracking-tighter text-black flex items-center">
                <span className="text-black/40 font-mono mr-1">//</span>
                <span>BRA</span>
              </span>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 border border-black bg-zinc-100 text-zinc-800 hidden sm:inline-block">
                Backtest Reliability Analyzer
              </span>
            </Link>
          </div>

          {/* Navigation Links (Devlab editorial menu) */}
          <nav className="hidden md:flex items-center gap-8 text-xs font-mono font-bold uppercase tracking-wider text-black/70">
            <a href="#features" className="hover:text-black transition-colors">
              Features
            </a>
            <a href="#methodology" className="hover:text-black transition-colors">
              Methodology
            </a>
            <a href="#workflow" className="hover:text-black transition-colors">
              How It Works
            </a>
            <Link to="/status" className="hover:text-black transition-colors">
              System Telemetry
            </Link>
          </nav>

          {/* Action CTAs */}
          <div className="flex items-center gap-3">
            <Link
              to="/status"
              className="hidden sm:flex items-center gap-2 px-2.5 py-1 text-[11px] font-mono border border-black bg-white hover:bg-zinc-50 transition-colors"
              title="FastAPI Backend Health"
            >
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${
                  isOnline ? 'bg-emerald-500 animate-pulse' : 'bg-bra-red'
                }`}
              />
              <span className="font-bold">
                {isOnline ? 'API: ONLINE' : 'API: CHECKING'}
              </span>
            </Link>

            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold font-mono tracking-wider text-white bg-black border border-black rounded-full hover:bg-zinc-800 transition-all shadow-bra-sm active:translate-y-0.5"
            >
              <span>OPEN DASHBOARD</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* 2. Hero Section (Split Devlab Layout) */}
      <section className="border-b border-black bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[580px]">
            {/* Left Hero Content */}
            <div className="lg:col-span-7 p-6 sm:p-10 lg:p-14 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-black">
              <div className="space-y-6">
                <div className="inline-flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-[#ff3b30]">
                  <span>✦</span>
                  <span>QUANTITATIVE RELIABILITY FRAMEWORK</span>
                </div>

                <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black uppercase tracking-tight text-black leading-[1.05]">
                  Trust Your Backtests.
                  <br />
                  <span className="text-black/80">Challenge Your Assumptions.</span>
                </h1>

                <p className="text-base sm:text-lg text-black/70 font-mono max-w-xl leading-relaxed">
                  Systematic strategies fail when historical datasets silently embed survivorship
                  bias, look-ahead leaks, unadjusted corporate splits, or phantom liquidity. BRA
                  proves dataset integrity before you deploy real capital.
                </p>

                {/* Hero CTAs */}
                <div className="pt-2 flex flex-wrap items-center gap-4">
                  <Button
                    variant="black"
                    size="lg"
                    icon={<ArrowUpRight size={16} />}
                    onClick={() => navigate('/dashboard')}
                    className="shadow-bra hover:shadow-bra-lg"
                  >
                    Open Dashboard
                  </Button>

                  <a
                    href="#preview"
                    className="inline-flex items-center gap-2 px-6 py-3 text-sm font-bold font-mono uppercase tracking-wider text-black bg-white border border-black rounded-full hover:bg-zinc-100 transition-all"
                  >
                    <span>Explore Preview</span>
                    <ChevronRight size={14} />
                  </a>
                </div>
              </div>

              {/* Devlab Footnote */}
              <div className="pt-8 border-t border-black/10 mt-8">
                <div className="flex items-center gap-2 text-xs font-mono text-black/60">
                  <span className="text-[#ff3b30] font-bold">*</span>
                  <span>
                    Zero fabricated metrics. 100% deterministic mathematical verification backed by
                    FastAPI, Pandas, and NSE historical time series.
                  </span>
                </div>
              </div>
            </div>

            {/* Right Hero Visual Art (Devlab Geometric Art) */}
            <div className="lg:col-span-5 bg-[#fafafa] flex items-center justify-center p-6 sm:p-10 relative overflow-hidden">
              <div className="w-full max-w-[420px] aspect-square border border-black bg-white p-6 shadow-bra relative">
                <GeometricGraphic />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Devlab Signature 4-Column Metric Strip */}
      <section className="border-b border-black bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 divide-y md:divide-y-0 divide-x divide-black">
            {/* Col 1 */}
            <div className="p-6">
              <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-black/50 mb-1">
                // VERIFICATION ENGINES
              </div>
              <div className="text-3xl font-black font-mono text-black">3 Core</div>
              <div className="text-xs font-mono text-black/60 mt-1">
                Survivorship, Look-Ahead, Corporate Actions
              </div>
            </div>

            {/* Col 2 */}
            <div className="p-6">
              <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-black/50 mb-1">
                // REST ARCHITECTURE
              </div>
              <div className="text-3xl font-black font-mono text-black">46 Endpoints</div>
              <div className="text-xs font-mono text-black/60 mt-1">
                Fully typed FastAPI OpenAPI specification
              </div>
            </div>

            {/* Col 3 */}
            <div className="p-6">
              <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-black/50 mb-1">
                // DETERMINISTIC AUDITING
              </div>
              <div className="text-3xl font-black font-mono text-black">Point-in-Time</div>
              <div className="text-xs font-mono text-black/60 mt-1">
                Precise timestamp & publication alignment
              </div>
            </div>

            {/* Col 4 */}
            <div className="p-6">
              <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-black/50 mb-1">
                // EXPORT COMPLIANCE
              </div>
              <div className="text-3xl font-black font-mono text-black">PDF • CSV • JSON</div>
              <div className="text-xs font-mono text-black/60 mt-1">
                Formal dossiers generated via ReportLab
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Live Interactive Platform Preview */}
      <section id="preview" className="py-16 md:py-24 border-b border-black bg-[#f8f9fa]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-black pb-6">
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-[#ff3b30] font-bold mb-1">
                // LIVE ENGINE PREVIEW
              </div>
              <h2 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
                Interactive Verification Matrix
              </h2>
              <p className="text-sm font-mono text-black/70 mt-2 max-w-xl">
                Experience the real reliability engines directly from the live backend. Select an
                engine to inspect real data structures and validation workflows.
              </p>
            </div>

            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-mono font-bold uppercase tracking-wider text-white bg-black border border-black hover:bg-zinc-800 transition-colors shadow-bra-sm"
            >
              <span>Launch Full Workspace</span>
              <ArrowUpRight size={14} />
            </Link>
          </div>

          {/* Interactive Preview Container */}
          <div className="border-2 border-black bg-white shadow-bra-lg">
            {/* Tab Header Bar */}
            <div className="flex border-b border-black overflow-x-auto bg-bra-muted/50">
              {[
                { id: 'survivorship', label: '1. Survivorship Bias Engine', icon: <TrendingDown size={14} /> },
                { id: 'lookahead', label: '2. Look-Ahead Bias Timeline', icon: <Clock size={14} /> },
                { id: 'actions', label: '3. Corporate Actions Adjustments', icon: <Sparkles size={14} /> },
                { id: 'datasets', label: '4. Datasets & Quality Scoring', icon: <Database size={14} /> },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActivePreviewTab(tab.id as any)}
                  className={`flex items-center gap-2 px-6 py-3.5 text-xs font-mono uppercase font-bold tracking-wider whitespace-nowrap transition-colors border-r border-black ${
                    activePreviewTab === tab.id
                      ? 'bg-black text-white shadow-inner'
                      : 'bg-white text-black hover:bg-zinc-100'
                  }`}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Tab Preview Viewport */}
            <div className="p-6 md:p-10">
              {activePreviewTab === 'survivorship' && (
                <div className="space-y-6">
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-black/10 pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="pass">CORE ENGINE</Badge>
                        <h3 className="text-xl font-bold font-mono uppercase">
                          Historical Universe Reconstruction & Delisting Audit
                        </h3>
                      </div>
                      <p className="text-xs font-mono text-black/60 mt-1">
                        Detects strategies that trade only today's surviving index constituents,
                        ignoring liquidated, acquired, or failed companies.
                      </p>
                    </div>
                    <Button
                      variant="black"
                      size="sm"
                      onClick={() => navigate('/survivorship')}
                      icon={<ArrowUpRight size={12} />}
                    >
                      Open Survivorship Tool
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="border border-black p-4 bg-[#fcfcfc]">
                      <span className="text-[10px] font-mono uppercase text-black/50 block">
                        Audit Target
                      </span>
                      <span className="text-base font-bold font-mono">NIFTY50 Benchmark</span>
                      <p className="text-xs font-mono text-black/60 mt-1">
                        Reconstructs dynamic index constituents on each rebalance date.
                      </p>
                    </div>
                    <div className="border border-black p-4 bg-[#fcfcfc]">
                      <span className="text-[10px] font-mono uppercase text-black/50 block">
                        Delisted Security Handling
                      </span>
                      <span className="text-base font-bold font-mono text-bra-red">
                        Full Price Reconciliation
                      </span>
                      <p className="text-xs font-mono text-black/60 mt-1">
                        Flags liquidated symbols with frozen returns or survivorship leaks.
                      </p>
                    </div>
                    <div className="border border-black p-4 bg-[#fcfcfc]">
                      <span className="text-[10px] font-mono uppercase text-black/50 block">
                        Constituent Coverage Metric
                      </span>
                      <span className="text-base font-bold font-mono text-emerald-700">
                        Min 80% Threshold
                      </span>
                      <p className="text-xs font-mono text-black/60 mt-1">
                        Validates continuous trading presence without missing periods.
                      </p>
                    </div>
                  </div>

                  <div className="border border-black p-4 bg-bra-muted/40 font-mono text-xs">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold uppercase text-black">
                        Sample Finding Model (Deterministic Output)
                      </span>
                      <Badge variant="WARN">SEVERITY: WARNING</Badge>
                    </div>
                    <pre className="p-3 bg-white border border-black/20 text-[11px] overflow-x-auto">
{`{
  "code": "SURV_DELISTED_OMISSION",
  "analyzer": "survivorship",
  "classification": "violation",
  "message": "Universe omits 4 securities that were NIFTY50 members in 2021 before delisting.",
  "evidence": { "affected_symbols": ["UNITECH", "RPOWER", "JPASSOCIAT", "SUZLON"], "distortion_bps": 142 }
}`}
                    </pre>
                  </div>
                </div>
              )}

              {activePreviewTab === 'lookahead' && (
                <div className="space-y-6">
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-black/10 pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="red">TEMPORAL LEAK DETECTION</Badge>
                        <h3 className="text-xl font-bold font-mono uppercase">
                          Point-in-Time Event Stream Chronology
                        </h3>
                      </div>
                      <p className="text-xs font-mono text-black/60 mt-1">
                        Audits financial report availability timestamps against strategy decision
                        dates to prevent premature trading on unannounced statements.
                      </p>
                    </div>
                    <Button
                      variant="black"
                      size="sm"
                      onClick={() => navigate('/lookahead')}
                      icon={<ArrowUpRight size={12} />}
                    >
                      Open Look-Ahead Tool
                    </Button>
                  </div>

                  <div className="space-y-3 font-mono text-xs">
                    <div className="p-3 border border-black bg-emerald-50/50 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-emerald-700 font-bold">✓ VALID</span>
                        <span>2022-03-31 Period End</span>
                        <span className="text-black/50">→</span>
                        <span>2022-05-15 Publication Disclosed</span>
                        <span className="text-black/50">→</span>
                        <span className="font-bold">2022-05-16 Trade Executed</span>
                      </div>
                      <Badge variant="pass">PASSED</Badge>
                    </div>

                    <div className="p-3 border-2 border-[#ff3b30] bg-rose-50/70 flex items-center justify-between shadow-bra-sm">
                      <div className="flex items-center gap-3">
                        <span className="text-bra-red font-bold">✕ LOOK-AHEAD DETECTED</span>
                        <span>2022-09-30 Period End</span>
                        <span className="text-black/50">→</span>
                        <span className="font-bold text-bra-red">2022-10-01 Decision Date</span>
                        <span className="text-black/50">(Published 44 days later on 2022-11-14)</span>
                      </div>
                      <Badge variant="fail">CRITICAL LEAK</Badge>
                    </div>
                  </div>
                </div>
              )}

              {activePreviewTab === 'actions' && (
                <div className="space-y-6">
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-black/10 pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="blue">CORPORATE ACTIONS</Badge>
                        <h3 className="text-xl font-bold font-mono uppercase">
                          Split, Bonus & Price Leap Diagnostics
                        </h3>
                      </div>
                      <p className="text-xs font-mono text-black/60 mt-1">
                        Detects artificial -50% or -80% price collapses caused by unadjusted stock
                        splits or bonus issues that falsify strategy returns.
                      </p>
                    </div>
                    <Button
                      variant="black"
                      size="sm"
                      onClick={() => navigate('/corporate-actions')}
                      icon={<ArrowUpRight size={12} />}
                    >
                      Open Corporate Actions Tool
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
                    <div className="border border-black p-4 bg-white">
                      <span className="font-bold uppercase block mb-1 text-bra-red">
                        Unadjusted 1:1 Bonus Issue Detected
                      </span>
                      <p className="text-black/60 text-[11px] mb-2">
                        Close price fell from ₹2,400 to ₹1,200 overnight without adjustment factor,
                        simulating a false 50% drawdown.
                      </p>
                      <div className="p-2 bg-bra-muted border border-black/10 text-[10px]">
                        Symbol: INFY • Ex-Date: 2018-09-04 • Ratio: 1:1
                      </div>
                    </div>

                    <div className="border border-black p-4 bg-white">
                      <span className="font-bold uppercase block mb-1 text-black">
                        Volume-Supported Normal Leap
                      </span>
                      <p className="text-black/60 text-[11px] mb-2">
                        +14% genuine earnings announcement reaction verified against official NSE
                        circular filings.
                      </p>
                      <div className="p-2 bg-bra-muted border border-black/10 text-[10px]">
                        Symbol: TCS • Date: 2023-01-12 • Type: Earnings Surprise
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activePreviewTab === 'datasets' && (
                <div className="space-y-6">
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-black/10 pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="pass">DATA INTEGRITY</Badge>
                        <h3 className="text-xl font-bold font-mono uppercase">
                          Live Dataset Ingestion & Quality Scoring
                        </h3>
                      </div>
                      <p className="text-xs font-mono text-black/60 mt-1">
                        Live connection to datasets stored in the local FastAPI backend repository.
                      </p>
                    </div>
                    <Button
                      variant="black"
                      size="sm"
                      onClick={() => navigate('/datasets')}
                      icon={<ArrowUpRight size={12} />}
                    >
                      View All Datasets
                    </Button>
                  </div>

                  <div className="space-y-2">
                    {datasets && datasets.length > 0 ? (
                      datasets.slice(0, 3).map((ds) => (
                        <div
                          key={ds.dataset_id}
                          className="p-3 border border-black bg-white flex items-center justify-between font-mono text-xs"
                        >
                          <div>
                            <span className="font-bold">{ds.name || ds.dataset_id}</span>
                            <span className="text-black/50 ml-2">[{ds.dataset_id}]</span>
                            <span className="text-[10px] text-black/40 block">
                              {ds.file_count} files • {ds.is_existing ? 'Canonical (Read-Only)' : 'Uploaded'}
                            </span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/datasets/${ds.dataset_id}`)}
                          >
                            Inspect Schema →
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="p-4 border border-black text-xs font-mono text-black/60">
                        Connecting to live dataset registry...
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* 5. Core Feature Grid (Devlab 2x2 Clean Minimalist Cards) */}
      <section id="features" className="py-16 md:py-24 border-b border-black bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="max-w-2xl">
            <div className="text-xs font-mono uppercase tracking-widest text-[#ff3b30] font-bold mb-1">
              // ARCHITECTURAL CAPABILITIES
            </div>
            <h2 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
              Forensic Reliability Checks
            </h2>
            <p className="text-sm font-mono text-black/70 mt-3">
              Engineered specifically for quantitative investment teams, systematic hedge funds,
              and academic backtesters requiring audit-grade rigor.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Feature 1 */}
            <div className="border border-black p-8 bg-white shadow-bra hover:shadow-bra-lg transition-all space-y-4">
              <div className="w-10 h-10 border border-black bg-black text-white flex items-center justify-center font-mono font-bold">
                01
              </div>
              <h3 className="text-xl font-black font-mono uppercase tracking-tight">
                Dataset Schema Validation & Quality Scoring
              </h3>
              <p className="text-sm font-mono text-black/70 leading-relaxed">
                Automated inference and mapping against financial standards: Daily Prices (OHLCV),
                Trade Universe, Financial Statements, and Corporate Actions. Calculates 0–100 quality
                scores based on completeness, timestamp order, and zero missing date gaps.
              </p>
              <div className="pt-2">
                <Link
                  to="/validation"
                  className="text-xs font-mono font-bold uppercase underline underline-offset-4 hover:text-[#ff3b30] transition-colors inline-flex items-center gap-1"
                >
                  <span>Launch Data Validator</span>
                  <ArrowRight size={12} />
                </Link>
              </div>
            </div>

            {/* Feature 2 */}
            <div className="border border-black p-8 bg-white shadow-bra hover:shadow-bra-lg transition-all space-y-4">
              <div className="w-10 h-10 border border-black bg-black text-white flex items-center justify-center font-mono font-bold">
                02
              </div>
              <h3 className="text-xl font-black font-mono uppercase tracking-tight">
                Survivorship Bias Elimination
              </h3>
              <p className="text-sm font-mono text-black/70 leading-relaxed">
                Reconstructs point-in-time constituent universes without relying on modern
                membership lists. Reconciles delisted stocks, bankruptcies, mergers, and symbol reuse
                anomalies across historical benchmark periods.
              </p>
              <div className="pt-2">
                <Link
                  to="/survivorship"
                  className="text-xs font-mono font-bold uppercase underline underline-offset-4 hover:text-[#ff3b30] transition-colors inline-flex items-center gap-1"
                >
                  <span>Survivorship Bias Analyzer</span>
                  <ArrowRight size={12} />
                </Link>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="border border-black p-8 bg-white shadow-bra hover:shadow-bra-lg transition-all space-y-4">
              <div className="w-10 h-10 border border-black bg-black text-white flex items-center justify-center font-mono font-bold">
                03
              </div>
              <h3 className="text-xl font-black font-mono uppercase tracking-tight">
                Look-Ahead Bias & Publication Timing
              </h3>
              <p className="text-sm font-mono text-black/70 leading-relaxed">
                Maps strategy execution moments to audited financial statement publication dates
                rather than fiscal quarter end dates. Detects unannounced restatements and forward
                information leakage before trades occur.
              </p>
              <div className="pt-2">
                <Link
                  to="/lookahead"
                  className="text-xs font-mono font-bold uppercase underline underline-offset-4 hover:text-[#ff3b30] transition-colors inline-flex items-center gap-1"
                >
                  <span>Look-Ahead Bias Analyzer</span>
                  <ArrowRight size={12} />
                </Link>
              </div>
            </div>

            {/* Feature 4 */}
            <div className="border border-black p-8 bg-white shadow-bra hover:shadow-bra-lg transition-all space-y-4">
              <div className="w-10 h-10 border border-black bg-black text-white flex items-center justify-center font-mono font-bold">
                04
              </div>
              <h3 className="text-xl font-black font-mono uppercase tracking-tight">
                Audit Dossiers & Compliance Reporting
              </h3>
              <p className="text-sm font-mono text-black/70 leading-relaxed">
                Generates formal PDF audit reports formatted with ReportLab, flat CSV tables for
                Pandas, and full machine-readable JSON trees for institutional risk committees and
                independent validation audits.
              </p>
              <div className="pt-2">
                <Link
                  to="/reports"
                  className="text-xs font-mono font-bold uppercase underline underline-offset-4 hover:text-[#ff3b30] transition-colors inline-flex items-center gap-1"
                >
                  <span>Generated Reports Archive</span>
                  <ArrowRight size={12} />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. "How It Works" 3-Step Section */}
      <section id="workflow" className="py-16 md:py-24 border-b border-black bg-[#fafafa]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="text-center max-w-xl mx-auto">
            <div className="text-xs font-mono uppercase tracking-widest text-[#ff3b30] font-bold mb-1">
              // METHODOLOGY WORKFLOW
            </div>
            <h2 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
              How It Works
            </h2>
            <p className="text-sm font-mono text-black/70 mt-2">
              Three seamless steps from raw market data ingestion to institutional audit signoff.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Step 1 */}
            <div className="border-2 border-black bg-white p-6 shadow-bra flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-black/10 pb-3">
                  <span className="text-xs font-mono font-bold text-black/50">PHASE 01</span>
                  <Database size={16} className="text-[#4a8b9f]" />
                </div>
                <h3 className="text-lg font-black font-mono uppercase">Connect Your Data</h3>
                <p className="text-xs font-mono text-black/70 leading-relaxed">
                  Upload custom multi-file CSV datasets or select the canonical NSE India benchmark
                  dataset (`existing-data`). The schema engine automatically validates columns, types,
                  and date formats.
                </p>
              </div>
              <div className="pt-6">
                <Link
                  to="/datasets"
                  className="text-xs font-mono font-bold uppercase underline hover:text-[#ff3b30]"
                >
                  Explore Datasets →
                </Link>
              </div>
            </div>

            {/* Step 2 */}
            <div className="border-2 border-black bg-white p-6 shadow-bra flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-black/10 pb-3">
                  <span className="text-xs font-mono font-bold text-black/50">PHASE 02</span>
                  <Activity size={16} className="text-[#ff3b30]" />
                </div>
                <h3 className="text-lg font-black font-mono uppercase">Run Reliability Checks</h3>
                <p className="text-xs font-mono text-black/70 leading-relaxed">
                  Execute individual bias verification tools or run the combined orchestrator to scan
                  for survivorship omissions, publication timeline leaks, and unadjusted split leaps
                  simultaneously.
                </p>
              </div>
              <div className="pt-6">
                <Link
                  to="/runs"
                  className="text-xs font-mono font-bold uppercase underline hover:text-[#ff3b30]"
                >
                  View Analysis Runs →
                </Link>
              </div>
            </div>

            {/* Step 3 */}
            <div className="border-2 border-black bg-white p-6 shadow-bra flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-black/10 pb-3">
                  <span className="text-xs font-mono font-bold text-black/50">PHASE 03</span>
                  <FileCheck size={16} className="text-emerald-700" />
                </div>
                <h3 className="text-lg font-black font-mono uppercase">Review Findings & Reports</h3>
                <p className="text-xs font-mono text-black/70 leading-relaxed">
                  Inspect granular evidence payloads in the Findings Explorer. Download formal
                  audit dossiers in PDF, CSV, and JSON for risk committees and investment
                  mandates.
                </p>
              </div>
              <div className="pt-6">
                <Link
                  to="/findings"
                  className="text-xs font-mono font-bold uppercase underline hover:text-[#ff3b30]"
                >
                  Inspect Findings →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Institutional CTA Banner */}
      <section className="py-16 md:py-20 border-b border-black bg-black text-white">
        <div className="max-w-5xl mx-auto px-4 text-center space-y-6">
          <div className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-[#ff3b30] font-bold">
            <span>✦</span>
            <span>GET STARTED TODAY</span>
          </div>

          <h2 className="text-3xl sm:text-5xl font-black uppercase tracking-tight">
            Verify Your Backtests With Mathematical Certainty.
          </h2>

          <p className="text-sm sm:text-base font-mono text-zinc-400 max-w-xl mx-auto">
            Direct access to all verification engines, datasets, and reports. No signup required.
          </p>

          <div className="pt-4 flex flex-wrap items-center justify-center gap-4">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-8 py-3.5 text-sm font-bold font-mono uppercase tracking-wider text-black bg-white border border-white rounded-full hover:bg-zinc-200 transition-all shadow-bra-sm active:translate-y-0.5"
            >
              <span>Open Analyzer Dashboard</span>
              <ArrowUpRight size={16} />
            </Link>

            <Link
              to="/status"
              className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-bold font-mono uppercase tracking-wider text-white bg-transparent border border-white rounded-full hover:bg-white/10 transition-all"
            >
              <span>Check System Status</span>
            </Link>
          </div>
        </div>
      </section>

      {/* 8. Professional Editorial Footer */}
      <footer className="bg-white py-12 px-4 sm:px-6 lg:px-8 font-mono text-xs text-black/70">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
          {/* Brand Col */}
          <div className="space-y-3">
            <div className="font-bold text-xl tracking-tighter text-black flex items-center">
              <span className="text-black/40 mr-1">//</span>
              <span>BRA</span>
            </div>
            <p className="text-[11px] text-black/60 leading-relaxed">
              Backtest Reliability Analyzer. Quantitative financial data integrity and bias
              detection platform for systematic strategies.
            </p>
            <div className="pt-1">
              <Badge variant="pass">FASTAPI 0.1.0 ONLINE</Badge>
            </div>
          </div>

          {/* Col 2: Verification Engines */}
          <div className="space-y-2">
            <div className="font-bold text-black uppercase tracking-wider text-[11px]">
              Engines
            </div>
            <ul className="space-y-1.5 text-[11px]">
              <li>
                <Link to="/survivorship" className="hover:text-black hover:underline">
                  Survivorship Bias Analyzer
                </Link>
              </li>
              <li>
                <Link to="/lookahead" className="hover:text-black hover:underline">
                  Look-Ahead Bias Analyzer
                </Link>
              </li>
              <li>
                <Link to="/corporate-actions" className="hover:text-black hover:underline">
                  Corporate Actions Engine
                </Link>
              </li>
              <li>
                <Link to="/validation" className="hover:text-black hover:underline">
                  Data Quality & Schema Validator
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 3: Workspace & Reports */}
          <div className="space-y-2">
            <div className="font-bold text-black uppercase tracking-wider text-[11px]">
              Workspace
            </div>
            <ul className="space-y-1.5 text-[11px]">
              <li>
                <Link to="/dashboard" className="hover:text-black hover:underline">
                  Executive Dashboard
                </Link>
              </li>
              <li>
                <Link to="/datasets" className="hover:text-black hover:underline">
                  Datasets Directory
                </Link>
              </li>
              <li>
                <Link to="/runs" className="hover:text-black hover:underline">
                  Execution Pipeline & Runs
                </Link>
              </li>
              <li>
                <Link to="/findings" className="hover:text-black hover:underline">
                  Findings Explorer
                </Link>
              </li>
              <li>
                <Link to="/reports" className="hover:text-black hover:underline">
                  Compliance Reports
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 4: System & Specifications */}
          <div className="space-y-2">
            <div className="font-bold text-black uppercase tracking-wider text-[11px]">
              System Specifications
            </div>
            <ul className="space-y-1.5 text-[11px]">
              <li>
                <Link to="/status" className="hover:text-black hover:underline">
                  Health & Ping Latency
                </Link>
              </li>
              <li>
                <span className="text-black/50">API Base: http://localhost:8000</span>
              </li>
              <li>
                <span className="text-black/50">Storage: Local Filesystem</span>
              </li>
              <li>
                <span className="text-black/50">Canonical: existing-data</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="max-w-7xl mx-auto pt-8 border-t border-black/10 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px]">
          <div>
            © 2026 // Backtest Reliability Analyzer (BRA). All rights reserved.
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[#ff3b30] font-bold">NSE Point-in-Time</span>
            <span>•</span>
            <span>Zero-Hardcoding Architecture</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
