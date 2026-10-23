import React, { useState } from 'react';
import { Modal } from '../../components/common/Modal';
import { Button } from '../../components/common/Button';
import { ErrorAlert } from '../../components/common/ErrorAlert';
import { useUploadDataset } from '../../hooks/useDatasets';
import { UploadCloud, File, X, CheckCircle2 } from 'lucide-react';
import { formatApiError } from '../../api/client';

interface DatasetUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (datasetId: string) => void;
}

export const DatasetUploadModal: React.FC<DatasetUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const uploadMutation = useUploadDataset();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const fileList = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...fileList]);
      setErrorMessage(null);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFiles.length === 0) {
      setErrorMessage('Please select at least one CSV file to upload.');
      return;
    }

    setErrorMessage(null);
    try {
      const result = await uploadMutation.mutateAsync({
        files: selectedFiles,
        meta: { name: name.trim() || undefined, description: description.trim() || undefined },
      });
      setSelectedFiles([]);
      setName('');
      setDescription('');
      onClose();
      if (onSuccess) onSuccess(result.dataset_id);
    } catch (err) {
      setErrorMessage(formatApiError(err));
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Upload Market Dataset"
      subtitle="Register one or multiple CSV files to create an isolated dataset collection"
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {errorMessage && (
          <ErrorAlert title="Upload Failed" message={errorMessage} />
        )}

        {/* Dataset Meta Inputs */}
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
              Dataset Name (Optional)
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. NSE Equities 2021-2026 Feed"
              className="w-full px-3 py-2 text-sm bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black font-mono placeholder:text-zinc-400"
            />
          </div>

          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
              Description (Optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Source provider, market segment, or backtest notes..."
              rows={2}
              className="w-full px-3 py-2 text-sm bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black font-mono placeholder:text-zinc-400"
            />
          </div>
        </div>

        {/* Drag and drop / file selector */}
        <div>
          <label className="block text-xs font-mono font-bold uppercase tracking-wider text-black mb-1">
            CSV File Upload (.csv only)
          </label>
          <div className="border-2 border-dashed border-black bg-zinc-50 p-6 text-center hover:bg-zinc-100 transition-colors relative cursor-pointer">
            <input
              type="file"
              multiple
              accept=".csv"
              onChange={handleFileChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="flex flex-col items-center justify-center pointer-events-none">
              <UploadCloud className="w-8 h-8 text-black mb-2" />
              <p className="text-sm font-bold text-black font-mono">
                Click or drag CSV files here
              </p>
              <p className="text-xs text-zinc-500 font-mono mt-1">
                Supports single or multiple related CSVs (Prices, Delistings, Corporate Actions)
              </p>
            </div>
          </div>
        </div>

        {/* Selected files list */}
        {selectedFiles.length > 0 && (
          <div className="space-y-2 border border-black bg-white p-3 max-h-48 overflow-y-auto">
            <div className="text-xs font-mono font-bold uppercase text-black flex items-center justify-between">
              <span>SELECTED FILES ({selectedFiles.length})</span>
              <span className="text-[10px] text-zinc-500">
                {(selectedFiles.reduce((acc, f) => acc + f.size, 0) / 1024).toFixed(1)} KB total
              </span>
            </div>
            <div className="divide-y divide-zinc-200">
              {selectedFiles.map((file, idx) => (
                <div key={idx} className="py-2 flex items-center justify-between gap-2 text-xs font-mono">
                  <div className="flex items-center gap-2 truncate">
                    <File className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                    <span className="truncate text-black font-medium">{file.name}</span>
                    <span className="text-[10px] text-zinc-400 shrink-0">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeFile(idx)}
                    className="p-1 hover:bg-red-50 text-red-600 rounded-sm"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="pt-3 border-t border-black flex items-center justify-end gap-3">
          <Button type="button" variant="white" onClick={onClose} disabled={uploadMutation.isPending}>
            CANCEL
          </Button>
          <Button
            type="submit"
            variant="black"
            isLoading={uploadMutation.isPending}
            disabled={selectedFiles.length === 0}
            icon={<CheckCircle2 className="w-4 h-4" />}
          >
            CONFIRM & UPLOAD
          </Button>
        </div>
      </form>
    </Modal>
  );
};
