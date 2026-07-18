import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-edge bg-panel p-4 ${className}`}>{children}</div>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  const styles = {
    primary:
      "bg-accent hover:bg-accent-2 text-accent-ink font-semibold disabled:opacity-40 disabled:hover:bg-accent",
    ghost:
      "bg-transparent hover:bg-panel-2 text-ink-dim hover:text-ink border border-edge disabled:opacity-40",
    danger: "bg-err/15 hover:bg-err/25 text-err border border-err/30 disabled:opacity-40",
  }[variant];
  return (
    <button
      className={`rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${styles} ${className}`}
      {...props}
    />
  );
}

export function Input({
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`selectable w-full rounded-lg border border-edge bg-bg px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none ${className}`}
      {...props}
    />
  );
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative block h-[20px] w-[36px] shrink-0 rounded-full transition-colors ${
          checked ? "bg-accent" : "bg-edge"
        }`}
      >
        <span
          className={`absolute top-[2px] left-[2px] block h-[16px] w-[16px] rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-[16px]" : "translate-x-0"
          }`}
        />
      </button>
      {label && <span className="text-sm text-ink-dim">{label}</span>}
    </label>
  );
}

/** macOS-System-Settings-style row: label + description left, control right. */
export function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-3.5 first:pt-1 last:pb-1 [&+&]:border-t [&+&]:border-edge/60">
      <div className="min-w-0">
        <div className="text-sm text-ink">{label}</div>
        {description && <div className="mt-0.5 text-xs leading-relaxed text-ink-faint">{description}</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">{children}</div>
    </div>
  );
}

export function Badge({
  tone = "dim",
  children,
}: {
  tone?: "ok" | "warn" | "err" | "dim" | "accent";
  children: ReactNode;
}) {
  const styles = {
    ok: "bg-ok/10 text-ok border-ok/25",
    warn: "bg-warn/10 text-warn border-warn/25",
    err: "bg-err/10 text-err border-err/25",
    dim: "bg-panel-2 text-ink-dim border-edge",
    accent: "bg-accent/10 text-accent-2 border-accent/25",
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${styles}`}>
      {children}
    </span>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 text-xs font-semibold tracking-widest text-ink-faint uppercase">
      {children}
    </h2>
  );
}
