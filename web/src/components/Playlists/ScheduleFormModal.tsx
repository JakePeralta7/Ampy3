import type { CreateScheduledSyncInput, ScheduledSync } from "../../api/schedules";
import { Modal } from "../ui/Modal";
import { ScheduleForm, type ScheduleFormPrefill } from "./ScheduleForm";

interface ScheduleFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (input: CreateScheduledSyncInput) => Promise<void>;
  editingSync?: ScheduledSync | null;
  prefill?: ScheduleFormPrefill;
  isLoading?: boolean;
  error?: string | null;
}

export function ScheduleFormModal({
  isOpen,
  onClose,
  onSubmit,
  editingSync,
  prefill,
  isLoading,
  error,
}: ScheduleFormModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        editingSync ? "Edit Schedule" : prefill ? "Create Sync from Explore" : "Add New Schedule"
      }
      size="sm"
    >
      <ScheduleForm
        onSubmit={async (input) => {
          await onSubmit(input);
          onClose();
        }}
        editingSync={editingSync}
        prefill={prefill}
        onCancel={onClose}
        isLoading={isLoading}
        error={error}
      />
    </Modal>
  );
}
