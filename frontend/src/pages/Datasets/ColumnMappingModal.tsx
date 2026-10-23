import React, { useState, useEffect } from 'react';
import { Modal } from '../../components/common/Modal';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { useDatasetMapping, useSetDatasetMapping } from '../../hooks/useDatasets';
import { listSchemas } from '../../api/endpoints';
import { useQuery } from '@tanstack/react-query';
import { CanonicalSchemaMetadata, FileMappingItem } from '../../api/types';
import { formatApiError } from '../../api/client';
import { Wand2, Check, AlertCircle } from 'lucide-react';

interface ColumnMappingModalProps {
  datasetId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const ColumnMappingModal: React.FC<ColumnMappingModalProps> = ({
  datasetId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { data: mappingData, isLoading: isMappingLoading, refetch } = useDatasetMapping(
    isOpen ? datasetId : undefined
  );

  const { data: schemas, isLoading: isSchemasLoading } = useQuery({
    queryKey: ['schemas'],
    queryFn: listSchemas,
    enabled: isOpen,
  });

  const setMappingMutation = useSetDatasetMapping();

  // Local state for mappings
  const [activeFileId, setActiveFileId] = useState<string>('');
  const [fileMappings, setFileMappings] = useState<Record<string, { schemaType: string; mapping: Record<string, string> }>>({});
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Initialize local state when mappingData loads
  useEffect(() => {
    if (mappingData?.mappings && mappingData.mappings.length > 0) {
      const initial: Record<string, { schemaType: string; mapping: Record<string, string> }> = {};
      mappingData.mappings.forEach((m) => {
        initial[m.file_id] = {
          schemaType: m.schema_type,
          mapping: { ...m.column_mapping },
        };
      });
      setFileMappings(initial);
      if (!activeFileId || !initial[activeFileId]) {
        setActiveFileId(mappingData.mappings[0].file_id);
      }
    }
  }, [mappingData, activeFileId]);

  if (!isOpen) return null;

  const currentFile = mappingData?.mappings.find((m) => m.file_id === activeFileId);
  const currentConfig = fileMappings[activeFileId];
  const selectedSchema = schemas?.find((s) => s.schema_type === currentConfig?.schemaType);

  const handleApplyAutoSuggestions = () => {
    if (!mappingData?.auto_suggestions) return;
    const updated = { ...fileMappings };
    Object.entries(mappingData.auto_suggestions).forEach(([fid, autoMap]) => {
      if (updated[fid]) {
        updated[fid].mapping = { ...autoMap };
      }
    });
    setFileMappings(updated);
  };

  const handleColumnChange = (sourceHeader: string, targetCanonical: string) => {
    if (!activeFileId || !fileMappings[activeFileId]) return;
    setFileMappings((prev) => {
      const cur = { ...prev[activeFileId] };
      const newMap = { ...cur.mapping };
      if (!targetCanonical) {
        delete newMap[sourceHeader];
      } else {
        newMap[sourceHeader] = targetCanonical;
      }
      return {
        ...prev,
        [activeFileId]: { ...cur, mapping: newMap },
      };
    });
  };

  const handleSubmit = async () => {
    setErrorMsg(null);
    try {
      const items: FileMappingItem[] = Object.entries(fileMappings).map(([fid, conf]) => ({
        file_id: fid,
        schema_type: conf.schemaType,
        column_mapping: conf.mapping,
      }));

      await setMappingMutation.mutateAsync({
        datasetId,
        payload: { mappings: items, auto_suggest: false },
      });

      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      setErrorMsg(formatApiError(err));
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Canonical Schema & Column Mapping"
      subtitle={`Map vendor column headers to standard BRA schemas for dataset ${datasetId}`}
      maxWidth="4xl"
    >
      {isMappingLoading || isSchemasLoading ? (
        <LoadingSpinner label="Loading schema specifications..." />
      ) : (
        <div className="space-y-6">
          {errorMsg && <ErrorAlert title="Mapping Save Failed" message={errorMsg} />}

          {/* Top Auto-Suggest Bar */}
          <div className="p-3 bg-zinc-50 border border-black flex items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="text-[#ff3b30] font-bold">✦</span>
              <span>Need help aligning columns? Let BRA auto-map common industry aliases.</span>
            </div>
            <Button
              variant="white"
              size="sm"
              onClick={handleApplyAutoSuggestions}
              icon={<Wand2 className="w-3.5 h-3.5 text-[#ff3b30]" />}
            >
              AUTO-SUGGEST
            </Button>
          </div>

          {/* File Switcher Tabs */}
          {mappingData?.mappings && mappingData.mappings.length > 1 && (
            <div className="flex items-center gap-2 border-b border-black overflow-x-auto pb-1 text-xs font-mono">
              {mappingData.mappings.map((m) => (
                <button
                  key={m.file_id}
                  onClick={() => setActiveFileId(m.file_id)}
                  className={`px-3 py-1.5 border font-bold uppercase transition-colors whitespace-nowrap cursor-pointer ${
                    activeFileId === m.file_id
                      ? 'bg-black text-white border-black'
                      : 'bg-white text-zinc-700 border-zinc-200 hover:border-black'
                  }`}
                >
                  {m.filename}
                </button>
              ))}
            </div>
          )}

          {currentFile && currentConfig && (
            <div className="space-y-4">
              {/* Target Schema Selector */}
              <div className="flex items-center justify-between gap-4 p-3 bg-white border border-black">
                <div>
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block font-bold">
                    Target Canonical Schema
                  </span>
                  <div className="font-bold text-sm text-black font-mono">
                    {selectedSchema?.label || currentConfig.schemaType}
                  </div>
                </div>

                <div className="w-52">
                  <select
                    value={currentConfig.schemaType}
                    onChange={(e) =>
                      setFileMappings((prev) => ({
                        ...prev,
                        [activeFileId]: {
                          ...prev[activeFileId],
                          schemaType: e.target.value,
                          mapping: {}, // reset mapping when schema changes
                        },
                      }))
                    }
                    className="w-full text-xs font-mono p-1.5 bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
                  >
                    {schemas?.map((s) => (
                      <option key={s.schema_type} value={s.schema_type}>
                        {s.label} ({s.schema_type})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Column Mapping Table */}
              <div className="border border-black bg-white overflow-hidden">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="bg-zinc-50 border-b border-black">
                      <th className="py-2.5 px-4 font-bold text-black uppercase">Source File Column</th>
                      <th className="py-2.5 px-4 font-bold text-black uppercase text-center w-8">→</th>
                      <th className="py-2.5 px-4 font-bold text-black uppercase">Canonical Schema Field</th>
                      <th className="py-2.5 px-4 font-bold text-black uppercase text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {/* Unique source headers found in current mapping file */}
                    {Object.keys(currentFile.column_mapping || {}).concat(
                      currentFile.unmapped_source_columns || []
                    ).filter((v, i, a) => a.indexOf(v) === i).map((sourceCol) => {
                      const currentMappedTarget = currentConfig.mapping[sourceCol] || '';
                      const isRequired = selectedSchema?.required_columns.includes(currentMappedTarget);

                      return (
                        <tr key={sourceCol} className="hover:bg-zinc-50">
                          <td className="py-2 px-4 font-bold text-black">{sourceCol}</td>
                          <td className="py-2 px-4 text-center text-zinc-400 font-bold">→</td>
                          <td className="py-2 px-4">
                            <select
                              value={currentMappedTarget}
                              onChange={(e) => handleColumnChange(sourceCol, e.target.value)}
                              className="w-full p-1 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black"
                            >
                              <option value="">-- Ignored / Unmapped --</option>
                              {selectedSchema?.columns.map((col) => (
                                <option key={col.name} value={col.name}>
                                  {col.name} {col.required ? '(REQUIRED)' : ''}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 px-4 text-right">
                            {currentMappedTarget ? (
                              <Badge variant={isRequired ? 'pass' : 'neutral'} size="sm">
                                {isRequired ? 'REQUIRED' : 'OPTIONAL'}
                              </Badge>
                            ) : (
                              <span className="text-[10px] text-zinc-400 font-bold">UNMAPPED</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Modal Actions */}
          <div className="pt-3 border-t border-black flex items-center justify-between">
            <span className="text-xs font-mono text-zinc-500">
              * Original uploaded files are never altered. Normalization writes to <code className="bg-zinc-100 px-1 border border-zinc-200">prepared/</code>.
            </span>
            <div className="flex items-center gap-3">
              <Button variant="white" onClick={onClose} disabled={setMappingMutation.isPending}>
                CANCEL
              </Button>
              <Button
                variant="black"
                onClick={handleSubmit}
                isLoading={setMappingMutation.isPending}
                icon={<Check className="w-4 h-4" />}
              >
                SAVE COLUMN MAPPING
              </Button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
};
