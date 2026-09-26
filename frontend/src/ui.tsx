import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

/** Shared presentation primitives. Review state and actions stay with the caller. */
export function Modal({
  title,
  children,
  onClose,
  wide = false,
  feedback,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  feedback?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.showModal();
    return () => previous?.focus();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      className={wide ? "modal wide" : "modal"}
      onCancel={onClose}
    >
      <div className="modal-heading">
        <h2 id={titleId}>{title}</h2>
        <button
          aria-label="Close dialog"
          className="icon-btn"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      {feedback && (
        <div role="alert" className="modal-error">
          {feedback}
        </div>
      )}
      {children}
    </dialog>
  );
}

export function PanelHeading({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children?: ReactNode;
}) {
  return (
    <div className="panel-heading">
      <h2>
        {title}
        {count !== undefined && <span className="panel-count">{count}</span>}
      </h2>
      {children}
    </div>
  );
}

export function StatusLabel({
  status,
  children,
}: {
  status: string;
  children: ReactNode;
}) {
  return <span className={`status ${status}`}>{children}</span>;
}
