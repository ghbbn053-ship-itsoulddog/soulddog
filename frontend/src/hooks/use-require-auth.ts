"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getDevPreviewUsername, isDevPreviewEnabled } from "@/lib/dev-preview";

type AuthState = {
  authenticated: boolean;
  username?: string;
};

export function useRequireAuth(apiBase: string, fallbackPath = "/chat") {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const run = async () => {
      if (isDevPreviewEnabled()) {
        if (!active) return;
        setUsername(getDevPreviewUsername());
        setAuthLoading(false);
        return;
      }

      try {
        const meRes = await fetch(`${apiBase}/api/auth/me`, { credentials: "include" });
        const me = (meRes.ok ? await meRes.json() : null) as AuthState | null;
        if (!me?.authenticated || !me?.username) {
          router.replace("/login");
          return;
        }
        if (!active) return;
        setUsername(String(me.username));
      } catch {
        router.replace("/login");
      } finally {
        if (active) {
          setAuthLoading(false);
        }
      }
    };

    void run();
    return () => {
      active = false;
    };
  }, [apiBase, fallbackPath, router]);

  return { username, authLoading };
}
