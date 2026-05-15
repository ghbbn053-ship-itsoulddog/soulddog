"use client";

export const DEV_PREVIEW_USERNAME = "dev-preview";

function resolveDevPreviewOverride() {
  const raw = (process.env.NEXT_PUBLIC_DEV_PREVIEW || "").trim().toLowerCase();
  if (["0", "false", "off"].includes(raw)) return false;
  if (["1", "true", "on"].includes(raw)) return true;
  return null;
}

function isLocalPreviewHost(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

export function isDevPreviewEnabled() {
  const override = resolveDevPreviewOverride();
  if (override !== null) return override;

  if (typeof window !== "undefined") {
    return isLocalPreviewHost(window.location.hostname);
  }

  return process.env.NODE_ENV !== "production";
}

export function getDevPreviewUsername() {
  return DEV_PREVIEW_USERNAME;
}
