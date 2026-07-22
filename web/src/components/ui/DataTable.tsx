import { ChevronDown, ChevronUp, Filter, X } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

export interface Column<T> {
  id: string;
  header: string;
  cell: (item: T) => React.ReactNode;
  sortable?: boolean;
  sortValue?: (item: T) => string | number;
  filterValue?: (item: T) => string;
  filterable?: boolean;
  className?: string;
  headerClassName?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string | number;
  onRowClick?: (item: T) => void;
  rowClassName?: (item: T) => string | undefined;
  loading?: boolean;
  loadingRows?: number;
}

type SortDir = "asc" | "desc" | null;

function rawValue<T>(item: T, col: Column<T>): string {
  if (col.filterValue) return col.filterValue(item);
  if (col.sortValue) return String(col.sortValue(item));
  return String(item[col.id as keyof T] ?? "");
}

function SkeletonCell({ width }: { width?: string }) {
  return (
    <div className="h-4 bg-bg-muted rounded animate-pulse" style={{ width: width || "60%" }} />
  );
}

function SkeletonRow({ columns }: { columns: Column<unknown>[] }) {
  return (
    <tr>
      {columns.map((col) => (
        <td key={col.id} className="px-4 py-3">
          <SkeletonCell />
        </td>
      ))}
    </tr>
  );
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  rowClassName,
  loading = false,
  loadingRows = 5,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [filtersVisible, setFiltersVisible] = useState(() =>
    Object.values(filters).some((v) => v.trim()),
  );

  const hasActiveFilters = Object.keys(filters).some((k) => filters[k]?.trim());

  useEffect(() => {
    if (hasActiveFilters) setFiltersVisible(true);
  }, [hasActiveFilters]);

  const handleSort = (col: Column<T>) => {
    if (!col.sortable) return;
    if (sortKey !== col.id) {
      setSortKey(col.id);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else if (sortDir === "desc") {
      setSortKey(null);
      setSortDir(null);
    }
  };

  const setFilter = (colId: string, value: string) => {
    setFilters((prev) => {
      if (value) return { ...prev, [colId]: value };
      const next = { ...prev };
      delete next[colId];
      return next;
    });
  };

  const clearFilters = useCallback(() => {
    setFilters({});
    setFiltersVisible(false);
  }, []);

  const processed = useMemo(() => {
    let result = data;

    const activeFilters = Object.entries(filters).filter(([, v]) => v.trim());
    if (activeFilters.length > 0) {
      result = result.filter((item) =>
        activeFilters.every(([colId, q]) => {
          const col = columns.find((c) => c.id === colId);
          if (!col) return true;
          return rawValue(item, col).toLowerCase().includes(q.trim().toLowerCase());
        }),
      );
    }

    if (sortKey && sortDir) {
      const col = columns.find((c) => c.id === sortKey);
      if (col) {
        result = [...result].sort((a, b) => {
          const aVal = col.sortValue ? col.sortValue(a) : rawValue(a, col);
          const bVal = col.sortValue ? col.sortValue(b) : rawValue(b, col);
          if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
          if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
          return 0;
        });
      }
    }

    return result;
  }, [data, filters, sortKey, sortDir, columns]);

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg-muted sticky top-0">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.id}
                  onClick={() => handleSort(col)}
                  className={`px-4 py-3 text-left font-medium text-fg ${
                    col.sortable ? "cursor-pointer select-none hover:bg-bg-inset" : ""
                  } ${col.headerClassName || ""}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    {col.sortable &&
                      sortKey === col.id &&
                      sortDir &&
                      (sortDir === "asc" ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                    {col.filterable && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setFiltersVisible((v) => !v);
                        }}
                        className={`p-0.5 rounded transition-colors ${
                          filters[col.id]?.trim()
                            ? "text-accent-500 bg-accent-500/10"
                            : "text-fg-subtle hover:text-fg-muted"
                        }`}
                        title={filtersVisible ? "Hide filters" : "Show filters"}
                      >
                        <Filter size={12} />
                      </button>
                    )}
                  </span>
                </th>
              ))}
            </tr>
            {filtersVisible && (
              <tr>
                {columns.map((col) => (
                  <th key={col.id} className="px-4 py-2 text-left font-normal">
                    {col.filterable ? (
                      <div className="relative" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={filters[col.id] || ""}
                          onChange={(e) => setFilter(col.id, e.target.value)}
                          placeholder={`Filter ${col.header.toLowerCase()}...`}
                          className="w-full px-2.5 py-1.5 text-xs border border-border/60 rounded-md bg-bg-inset text-fg focus:outline-none focus:ring-1 focus:ring-accent-500/40 focus:border-accent-500/60 placeholder-fg-subtle transition-colors"
                        />
                        {filters[col.id] && (
                          <button
                            onClick={() => setFilter(col.id, "")}
                            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-fg-subtle hover:text-fg-muted"
                          >
                            <X size={12} />
                          </button>
                        )}
                      </div>
                    ) : null}
                  </th>
                ))}
              </tr>
            )}
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              Array.from({ length: loadingRows }).map((_, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: skeleton rows have no stable identity
                <SkeletonRow key={i} columns={columns as Column<unknown>[]} />
              ))
            ) : processed.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-fg-muted">
                  {hasActiveFilters ? "No results match your filters" : "No data"}
                </td>
              </tr>
            ) : (
              processed.map((item) => (
                <tr
                  key={keyExtractor(item)}
                  onClick={() => onRowClick?.(item)}
                  className={`${onRowClick ? "cursor-pointer" : ""} hover:bg-bg-muted transition-colors duration-fast ${rowClassName?.(item) || ""}`}
                >
                  {columns.map((col) => (
                    <td key={col.id} className={`px-4 py-3 ${col.className || ""}`}>
                      {col.cell(item)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {hasActiveFilters && !loading && (
        <div className="flex items-center gap-2 mt-2 text-xs text-fg-muted">
          <span>
            {processed.length} of {data.length} results
          </span>
          <button onClick={clearFilters} className="text-accent-500 hover:underline">
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}
