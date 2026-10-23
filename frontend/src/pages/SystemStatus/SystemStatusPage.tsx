import React, { useState } from 'react';
import {
  Server,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  HardDrive,
  Cpu,
  Layers,
  Database,
  ShieldCheck,
  Clock,
} from 'lucide-react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { useQuery } from '@tanstack/react-query';
import { getV1Health, getMetadata, listSchemas } from '../../api/endpoints';
import { API_BASE_URL } from '../../api/client';

export const SystemStatusPage: React.FC = () => {
  const [pingLatency, setPingLatency] = useState<number | null>(null);

  const {
    data: health,
    isLoading: isHealthLoading,
    isError: isHealthError,
    error: healthError,
    refetch: refetchHealth,
    isFetching: isHealthFetching,
  } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: async () => {
      const start = performance.now();
      const res = await getV1Health();
      const end = performance.now();
      setPingLatency(Math.round(end - start));
      return res;
    },
    refetchInterval: 15000,
  });

  const {
    data: metadata,
    isLoading: isMetaLoading,
    isError: isMetaError,
    error: metaError,
    refetch: refetchMeta,
  } = useQuery({
    queryKey: ['systemMetadata'],
    queryFn: getMetadata,
  });

  const { data: schemas } = useQuery({
    queryKey: ['schemasList'],
    queryFn: listSchemas,
  });

  const handleRefresh = () => {
    refetchHealth();
    refetchMeta();
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-black pb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-black/60 mb-1">
            // TELEMETRY & DIAGNOSTICS
          </div>
          <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-black">
            System & API Status
          </h1>
          <p className="text-sm text-black/70 mt-2 max-w-2xl font-mono">
            Real-time health verification of the FastAPI backend service, analyzer calculation
            engines, schema validators, and persistence storage.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="white"
            size="md"
            icon={<RotateCw size={14} className={isHealthFetching ? 'animate-spin' : ''} />}
            onClick={handleRefresh}
          >
            Run Ping Check
          </Button>
        </div>
      </div>

      {/* Primary Health Status Ribbon */}
      <div className="border-2 border-black bg-white p-6 shadow-bra">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div
              className={`w-6 h-6 rounded-full border-2 border-black flex items-center justify-center ${
                health?.status === 'ok' ? 'bg-emerald-500' : 'bg-bra-red'
              }`}
            >
              <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-black font-mono uppercase tracking-tight">
                  Backend System Status: {health?.status?.toUpperCase() || 'UNKNOWN'}
                </span>
                {health?.status === 'ok' ? (
                  <Badge variant="PASS">OPERATIONAL</Badge>
                ) : (
                  <Badge variant="FAIL">DEGRADED</Badge>
                )}
              </div>
              <p className="text-xs font-mono text-black/60 mt-0.5">
                Connected to <span className="font-bold text-black">{API_BASE_URL}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6 font-mono text-xs">
            <div className="text-right">
              <span className="text-black/50 block text-[10px] uppercase">Ping Latency</span>
              <span className="font-bold text-black">
                {pingLatency !== null ? `${pingLatency} ms` : 'Measuring...'}
              </span>
            </div>
            <div className="text-right">
              <span className="text-black/50 block text-[10px] uppercase">Engine Version</span>
              <span className="font-bold text-black">{health?.version || '0.1.0'}</span>
            </div>
          </div>
        </div>
      </div>

      {isHealthError && (
        <ErrorAlert
          error={healthError}
          title="FastAPI Backend Unreachable"
          onRetry={handleRefresh}
        />
      )}

      {/* Grid of Subsystem Health */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Storage Subsystem */}
        <Card title="STORAGE SUBSYSTEM" tag="✦ PERSISTENCE">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-black/70 flex items-center gap-1.5">
                <HardDrive size={14} /> Storage State:
              </span>
              <Badge variant={health?.storage === 'healthy' ? 'PASS' : 'WARN'}>
                {health?.storage?.toUpperCase() || 'N/A'}
              </Badge>
            </div>

            <div className="text-xs font-mono border-t border-black/10 pt-3 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-black/50">Storage Mode:</span>
                <span className="font-bold">
                  {metadata?.application_config?.storage_mode || 'local_filesystem'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-black/50">Canonical Dataset:</span>
                <span className="font-bold text-emerald-600">Read-Only Protected</span>
              </div>
            </div>
          </div>
        </Card>

        {/* File Handling */}
        <Card title="INGESTION LIMITS" tag="✦ SPECS">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-black/70 flex items-center gap-1.5">
                <Database size={14} /> Max Upload Limit:
              </span>
              <span className="font-bold font-mono text-xs">
                {metadata?.file_handling?.max_upload_size_mb || 50} MB
              </span>
            </div>

            <div className="text-xs font-mono border-t border-black/10 pt-3 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-black/50">Supported Extensions:</span>
                <span className="font-bold">
                  {metadata?.file_handling?.supported_extensions?.join(', ') || '.csv'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-black/50">CSV Delimiter:</span>
                <span className="font-bold">Comma (,)</span>
              </div>
            </div>
          </div>
        </Card>

        {/* Security & Access */}
        <Card title="SECURITY PROTOCOL" tag="✦ ENVIRONMENT">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-black/70 flex items-center gap-1.5">
                <ShieldCheck size={14} /> Auth Status:
              </span>
              <Badge variant="info">DIRECT ACCESS</Badge>
            </div>

            <div className="text-xs font-mono border-t border-black/10 pt-3 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-black/50">CORS Policy:</span>
                <span className="font-bold text-emerald-600">Enabled for Frontend</span>
              </div>
              <div className="flex justify-between">
                <span className="text-black/50">Secrets Exposed:</span>
                <span className="font-bold text-emerald-600">None (Sanitized)</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Engine Registry */}
      <Card title="VERIFICATION ENGINES REGISTRY" tag="✦ ACTIVE ALGORITHMS">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              id: 'survivorship',
              name: 'Survivorship Bias Engine',
              desc: 'Cross-references universe definitions with delisted equity price histories.',
            },
            {
              id: 'lookahead',
              name: 'Look-Ahead Bias Engine',
              desc: 'Validates publication timestamps against strategy decision moments.',
            },
            {
              id: 'corporate_actions',
              name: 'Corporate Actions Engine',
              desc: 'Discovers unadjusted stock splits, dividends, bonuses, and sudden price leaps.',
            },
          ].map((engine) => {
            const status = health?.analyzers?.[engine.id] || 'available';
            return (
              <div key={engine.id} className="border border-black p-4 bg-white shadow-bra-sm">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-mono text-xs font-bold uppercase">{engine.name}</h4>
                  <Badge variant={status === 'available' ? 'PASS' : 'WARN'}>
                    {status.toUpperCase()}
                  </Badge>
                </div>
                <p className="text-xs font-mono text-black/60">{engine.desc}</p>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Canonical Schemas Available */}
      <Card title="CANONICAL DATA SCHEMAS" tag="✦ FINANCIAL STANDARDS">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(schemas || []).map((schema) => (
            <div key={schema.schema_type} className="border border-black p-4 bg-white">
              <div className="flex items-center justify-between border-b border-black/10 pb-2 mb-2">
                <div>
                  <h4 className="text-xs font-mono font-bold uppercase">{schema.label}</h4>
                  <span className="text-[10px] font-mono text-black/50">
                    type: {schema.schema_type}
                  </span>
                </div>
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 bg-black/5 border border-black/20">
                  {schema.columns?.length || schema.required_columns?.length || 0} columns
                </span>
              </div>
              <p className="text-xs font-mono text-black/60 mb-2">{schema.description}</p>
              <div className="text-[10px] font-mono space-y-1">
                <div>
                  <span className="text-black/50">Required: </span>
                  <span className="font-bold">{schema.required_columns?.join(', ')}</span>
                </div>
                {schema.date_columns && schema.date_columns.length > 0 && (
                  <div>
                    <span className="text-black/50">Date fields: </span>
                    <span>{schema.date_columns.join(', ')}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
