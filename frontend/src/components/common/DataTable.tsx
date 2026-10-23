import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Search } from 'lucide-react';

export interface Column<T> {
  header: string;
  accessor?: keyof T | ((row: T) => React.ReactNode);
  className?: string;
  sortable?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T, index: number) => string;
  pageSize?: number;
  searchable?: boolean;
  searchPlaceholder?: string;
  searchFilter?: (row: T, query: string) => boolean;
  emptyMessage?: string;
  title?: React.ReactNode;
  headerAction?: React.ReactNode;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  pageSize = 10,
  searchable = true,
  searchPlaceholder = 'Filter records...',
  searchFilter,
  emptyMessage = 'No matching records found.',
  title,
  headerAction,
  className = '',
}: DataTableProps<T>) {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Filter
  const filteredData = React.useMemo(() => {
    if (!searchQuery.trim() || !searchFilter) return data;
    return data.filter((row) => searchFilter(row, searchQuery.toLowerCase().trim()));
  }, [data, searchQuery, searchFilter]);

  // Paginate
  const totalPages = Math.max(1, Math.ceil(filteredData.length / pageSize));
  const validPage = Math.min(currentPage, totalPages);
  const pagedData = React.useMemo(() => {
    const start = (validPage - 1) * pageSize;
    return filteredData.slice(start, start + pageSize);
  }, [filteredData, validPage, pageSize]);

  return (
    <div className={`border border-black bg-white rounded-none flex flex-col shadow-[2px_2px_0px_0px_#000000] ${className}`}>
      {/* Table Header Bar */}
      {(title || searchable || headerAction) && (
        <div className="px-5 py-3 border-b border-black flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white">
          <div className="flex items-center gap-3">
            {title && <div className="font-bold text-sm tracking-tight text-black">{title}</div>}
            <span className="text-xs font-mono font-bold px-2 py-0.5 border border-black bg-[#f4f4f5] text-zinc-700">
              {filteredData.length} {filteredData.length === 1 ? 'RECORD' : 'RECORDS'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {searchable && searchFilter && (
              <div className="relative w-full sm:w-64">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setCurrentPage(1);
                  }}
                  placeholder={searchPlaceholder}
                  className="w-full pl-9 pr-3 py-1.5 text-xs font-mono bg-white border border-black focus:outline-none focus:ring-1 focus:ring-black placeholder:text-zinc-400"
                />
              </div>
            )}
            {headerAction && <div>{headerAction}</div>}
          </div>
        </div>
      )}

      {/* Table Container */}
      <div className="overflow-x-auto flex-1">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-black bg-[#fafafa]">
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className={`px-4 py-2.5 text-xs font-mono font-bold text-black uppercase tracking-wider ${
                    col.className || ''
                  }`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200 text-sm">
            {pagedData.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-zinc-500 font-mono text-xs">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              pagedData.map((row, rowIdx) => (
                <tr key={keyExtractor(row, rowIdx)} className="hover:bg-zinc-50 transition-colors">
                  {columns.map((col, colIdx) => {
                    let content: React.ReactNode;
                    if (typeof col.accessor === 'function') {
                      content = col.accessor(row);
                    } else if (col.accessor) {
                      content = String(row[col.accessor] ?? '—');
                    } else {
                      content = '—';
                    }
                    return (
                      <td key={colIdx} className={`px-4 py-3 text-zinc-800 ${col.className || ''}`}>
                        {content}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="px-4 py-2.5 border-t border-black bg-[#fbfbfb] flex items-center justify-between text-xs font-mono">
          <div className="text-zinc-600">
            Page <span className="font-bold text-black">{validPage}</span> of{' '}
            <span className="font-bold text-black">{totalPages}</span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(1)}
              disabled={validPage <= 1}
              className="p-1 border border-black bg-white hover:bg-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              title="First Page"
            >
              <ChevronsLeft className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={validPage <= 1}
              className="p-1 border border-black bg-white hover:bg-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              title="Previous Page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="px-2 py-0.5 border border-black bg-white font-bold">
              {validPage}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={validPage >= totalPages}
              className="p-1 border border-black bg-white hover:bg-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              title="Next Page"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setCurrentPage(totalPages)}
              disabled={validPage >= totalPages}
              className="p-1 border border-black bg-white hover:bg-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              title="Last Page"
            >
              <ChevronsRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
