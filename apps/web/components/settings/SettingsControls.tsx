"use client";

import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Check, LoaderCircle } from "lucide-react";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export function SettingsSectionHeading({
  icon: Icon,
  title,
  description,
  eyebrow,
  action,
  id,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  eyebrow?: string;
  action?: ReactNode;
  id?: string;
}) {
  return (
    <header className="settings-control-heading">
      <div>
        {Icon ? <Icon size={19} aria-hidden="true" /> : null}
        <span>
          {eyebrow ? <small>{eyebrow}</small> : null}
          <h2 id={id}>{title}</h2>
          {description ? <p>{description}</p> : null}
        </span>
      </div>
      {action ? <aside>{action}</aside> : null}
    </header>
  );
}

export function SettingsChoiceCard({
  selected,
  title,
  description,
  ...buttonProps
}: {
  selected: boolean;
  title: string;
  description: string;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-pressed">) {
  return (
    <button
      type="button"
      {...buttonProps}
      aria-pressed={selected}
      className={`settings-choice-card settings-interactive ${buttonProps.className ?? ""}`.trim()}
    >
      <span><strong>{title}</strong><small>{description}</small></span>
      {selected ? <Check size={17} aria-hidden="true" /> : null}
    </button>
  );
}

export function SettingsSegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: T;
  options: Array<{ value: T; label: string; disabled?: boolean }>;
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className="settings-segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          type="button"
          key={option.value}
          className="settings-interactive"
          aria-pressed={value === option.value}
          disabled={disabled || option.disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function SettingsStateSwitch({
  checked,
  label,
  onChange,
  disabled,
}: {
  checked: boolean;
  label?: string;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={`settings-state-switch settings-interactive ${checked ? "is-on" : ""}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    >
      <span aria-hidden="true" />
      {label ?? (checked ? "已启用" : "已关闭")}
    </button>
  );
}

export function SettingsField({
  label,
  description,
  children,
  className = "",
}: {
  label: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`settings-field ${className}`.trim()}>
      <span>{label}</span>
      {children}
      {description ? <small>{description}</small> : null}
    </label>
  );
}

export function SettingsAction({
  variant = "secondary",
  busy = false,
  children,
  ...buttonProps
}: {
  variant?: "primary" | "secondary" | "danger" | "quiet";
  busy?: boolean;
  children: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...buttonProps}
      disabled={busy || buttonProps.disabled}
      className={`settings-action is-${variant} settings-interactive ${buttonProps.className ?? ""}`.trim()}
    >
      {busy ? <LoaderCircle className="is-spinning" size={15} aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function SettingsInlineNotice({
  tone = "info",
  children,
  ...props
}: {
  tone?: Tone;
  children: ReactNode;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      role={tone === "danger" ? "alert" : "status"}
      className={`settings-inline-notice is-${tone} ${props.className ?? ""}`.trim()}
    >
      {children}
    </div>
  );
}

export function SettingsStatusPill({
  tone = "neutral",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return <span className={`settings-status-pill is-${tone}`}>{children}</span>;
}

export function SettingsActionBar({
  summary,
  meta,
  children,
  dirty = false,
}: {
  summary: string;
  meta?: ReactNode;
  children: ReactNode;
  dirty?: boolean;
}) {
  return (
    <footer className={`settings-action-bar ${dirty ? "has-draft" : ""}`}>
      <div><strong>{summary}</strong>{meta ? <span>{meta}</span> : null}</div>
      <div>{children}</div>
    </footer>
  );
}
