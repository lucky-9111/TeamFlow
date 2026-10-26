import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { invalidateTaskViews, useTeam } from "../../hooks/queries";
import { api, errorMessage } from "../../services/api";
import type { BulkResult } from "../../types/api";
import { PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL } from "../../utils/labels";
import { Button } from "../ui/Button";
import { useConfirm } from "../ui/Confirm";
import { useToast } from "../ui/Toast";

type Action = "assignee_id" | "priority" | "status" | "add_label";

const ACTIONS: { value: Action; label: string }[] = [
  { value: "assignee_id", label: "Assign to" },
  { value: "priority", label: "Set priority" },
  { value: "status", label: "Move to status" },
  { value: "add_label", label: "Add label" },
];

/**
 * Applies one change to the selected tasks. The server checks each task separately, so the result
 * can be partial; failed tasks stay selected and their reasons are listed.
 */
export function BulkBar({ keys, onDone }: { keys: string[]; onDone: (failedKeys: string[]) => void }) {
  const [action, setAction] = useState<Action>("priority");
  const [value, setValue] = useState("");
  const [failed, setFailed] = useState<BulkResult["failed"]>([]);
  const team = useTeam();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const apply = useMutation({
    mutationFn: () => {
      const v = action === "assignee_id" ? (value === "none" ? null : Number(value)) : value.trim();
      return api.post<BulkResult>("/tasks/bulk", { task_keys: keys, [action]: v });
    },
    onSuccess: (r) => {
      invalidateTaskViews(qc);
      setFailed(r.failed);
      if (r.updated.length) toast.success(`Updated ${r.updated.length} of ${keys.length} tasks`);
      if (r.failed.length) toast.error(`${r.failed.length} tasks could not be updated. See the list below.`);
      onDone(r.failed.map((f) => f.key));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const options =
    action === "assignee_id"
      ? [{ value: "none", label: "Unassigned" }, ...(team.data ?? []).filter((u) => u.is_active).map((u) => ({ value: String(u.id), label: u.full_name }))]
      : action === "priority"
        ? PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))
        : STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }));
  const valueLabel = action === "add_label" ? `"${value.trim()}"` : (options.find((o) => o.value === value)?.label ?? "");

  async function submit() {
    const what = ACTIONS.find((a) => a.value === action)!.label.toLowerCase();
    const ok = await confirm({
      title: `Update ${keys.length} ${keys.length === 1 ? "task" : "tasks"}?`,
      message: `${what[0].toUpperCase()}${what.slice(1)} ${valueLabel} for ${keys.length} selected ${keys.length === 1 ? "task" : "tasks"}. Tasks you can't change will be skipped and listed.`,
      confirmLabel: "Apply",
    });
    if (ok) apply.mutate();
  }

  return (
    <div className="card mb-4 border-brand-200 bg-brand-50/40 p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-gray-900">{keys.length} selected</span>
        <select
          aria-label="Bulk action"
          className="input h-8 w-40 py-0 text-sm"
          value={action}
          onChange={(e) => {
            setAction(e.target.value as Action);
            setValue("");
          }}
        >
          {ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
        {action === "add_label" ? (
          <input
            aria-label="Label"
            className="input h-8 w-40 py-0 text-sm"
            placeholder="Label name"
            maxLength={30}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        ) : (
          <select aria-label="New value" className="input h-8 w-44 py-0 text-sm" value={value} onChange={(e) => setValue(e.target.value)}>
            <option value="">Choose…</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
        <Button size="sm" variant="primary" disabled={!value.trim()} loading={apply.isPending} onClick={submit}>
          Apply
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onDone([])}>
          Clear selection
        </Button>
      </div>
      {failed.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-red-700" aria-label="Failed updates">
          {failed.map((f) => (
            <li key={f.key}>
              <span className="font-medium">{f.key}</span>: {f.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
