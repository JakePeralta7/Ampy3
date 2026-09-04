import { Button } from "../../components/ui/Button";
import { type ConfigFieldDef, getNodeDef, getVisibleConfigFields } from "./nodeTypes";

interface NodeInspectorProps {
  nodeId: string | null;
  nodeType: string | null;
  nodeName: string;
  config: Record<string, unknown>;
  onNameChange: (name: string) => void;
  onConfigChange: (config: Record<string, unknown>) => void;
  onDelete: () => void;
  onBreakpointToggle: () => void;
  hasBreakpoint: boolean;
  readOnly?: boolean;
}

export function NodeInspector({
  nodeId,
  nodeType,
  nodeName,
  config,
  onNameChange,
  onConfigChange,
  onDelete,
  onBreakpointToggle,
  hasBreakpoint,
  readOnly = false,
}: NodeInspectorProps) {
  const def = nodeType ? getNodeDef(nodeType) : undefined;

  if (!nodeId || !def) {
    return (
      <div className="w-72 bg-bg-muted border-l border-border p-4 flex-shrink-0">
        <p className="text-xs text-fg-subtle text-center mt-10">Select a node to inspect</p>
      </div>
    );
  }

  const handleFieldChange = (field: ConfigFieldDef, value: unknown) => {
    if (readOnly) return;
    onConfigChange({ ...config, [field.key]: value });
  };

  return (
    <div className="w-72 bg-bg-muted border-l border-border overflow-y-auto flex-shrink-0">
      <div className="p-4 space-y-4">
        {/* Header */}
        <div>
          <div className="text-xs text-fg-subtle uppercase tracking-wider mb-1">{def.label}</div>
          <input
            type="text"
            value={nodeName}
            onChange={(e) => onNameChange(e.target.value)}
            className="w-full px-2 py-1 text-sm font-medium bg-bg-surface border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus text-fg"
            placeholder="Node name"
          />
        </div>

        {/* Config fields */}
        {(() => {
          const visibleFields = getVisibleConfigFields(def, config);
          return (
            visibleFields.length > 0 && (
              <div>
                <div className="text-xs text-fg-subtle uppercase tracking-wider mb-2">
                  Configuration
                </div>
                <div className="space-y-3">
                  {visibleFields.map((field) => (
                    <div key={field.key}>
                      <label className="block text-xs text-fg-muted mb-1">{field.label}</label>
                      {field.type === "boolean" && (
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={(config[field.key] as boolean) ?? (field.default as boolean)}
                            onChange={(e) => handleFieldChange(field, e.target.checked)}
                            className="rounded border-border text-accent-500 focus:ring-border-focus"
                          />
                          <span className="text-xs text-fg-muted">Enabled</span>
                        </label>
                      )}
                      {field.type === "text" && (
                        <input
                          type="text"
                          value={(config[field.key] as string) ?? (field.default as string)}
                          onChange={(e) => handleFieldChange(field, e.target.value)}
                          className="w-full px-2 py-1 text-xs bg-bg-surface border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus text-fg"
                        />
                      )}
                      {field.type === "number" && (
                        <input
                          type="number"
                          value={(config[field.key] as number) ?? (field.default as number)}
                          onChange={(e) =>
                            handleFieldChange(field, parseFloat(e.target.value) || 0)
                          }
                          className="w-full px-2 py-1 text-xs bg-bg-surface border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus text-fg"
                        />
                      )}
                      {field.type === "slider" && (
                        <div className="flex items-center gap-2">
                          <input
                            type="range"
                            min={field.min ?? 0}
                            max={field.max ?? 1}
                            step={field.step ?? 0.05}
                            value={(config[field.key] as number) ?? (field.default as number)}
                            onChange={(e) => handleFieldChange(field, parseFloat(e.target.value))}
                            className="flex-1 accent-accent-500"
                          />
                          <span className="text-xs font-mono w-8 text-right text-fg-muted">
                            {((config[field.key] as number) ?? (field.default as number)).toFixed(
                              2,
                            )}
                          </span>
                        </div>
                      )}
                      {field.type === "select" && field.options && (
                        <select
                          value={(config[field.key] as string) ?? (field.default as string)}
                          onChange={(e) => handleFieldChange(field, e.target.value)}
                          className="w-full px-2 py-1 text-xs bg-bg-surface border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus text-fg"
                        >
                          {field.options.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      )}
                      {field.type === "checkbox_list" && field.options && (
                        <div className="space-y-2">
                          {field.options.map((opt) => {
                            const currentValue =
                              (config[field.key] as string[] | string) ??
                              (field.default as string[] | string);
                            const isArray = Array.isArray(currentValue);
                            const valueArray = isArray
                              ? currentValue
                              : typeof currentValue === "string"
                                ? currentValue.split(",")
                                : [];
                            const isChecked = valueArray.includes(String(opt.value));

                            return (
                              <label
                                key={opt.value}
                                className="flex items-center gap-2 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={(e) => {
                                    const newArray = e.target.checked
                                      ? [...valueArray, String(opt.value)]
                                      : valueArray.filter((v) => v !== String(opt.value));
                                    handleFieldChange(field, newArray);
                                  }}
                                  className="rounded border-border text-accent-500 focus:ring-border-focus"
                                />
                                <span className="text-xs text-fg-muted">{opt.label}</span>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          );
        })()}

        {/* Breakpoint */}
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={hasBreakpoint}
              onChange={onBreakpointToggle}
              className="rounded border-border text-danger-500 focus:ring-danger-500"
            />
            <span className="text-xs text-fg-muted">Breakpoint</span>
          </label>
        </div>

        {/* Delete */}
        {!readOnly && (
          <Button variant="danger" size="sm" onClick={onDelete}>
            Delete Node
          </Button>
        )}
      </div>
    </div>
  );
}
