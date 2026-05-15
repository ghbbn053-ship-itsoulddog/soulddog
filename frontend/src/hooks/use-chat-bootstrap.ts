"use client";

import { useEffect, type MutableRefObject } from "react";

import {
  getConversationStorageKey,
  migrateLegacyConversationStorage,
  type ChatHistoryMessage,
  type ChatViewMessage,
} from "@/components/chat/chat-history";

type UseChatBootstrapArgs = {
  apiBase: string;
  username: string;
  authLoading: boolean;
  requestedConversationId: number | null;
  fetchModelPrefs: (username: string) => Promise<void>;
  fetchWorkspacePrefs: (username: string) => Promise<void>;
  mapMessages: (messages: ChatHistoryMessage[]) => ChatViewMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatViewMessage[]>>;
  setCurrentConversationId: React.Dispatch<React.SetStateAction<number | null>>;
  setInitialLoading: React.Dispatch<React.SetStateAction<boolean>>;
  activeHistoryReqRef: MutableRefObject<number>;
};

export function useChatBootstrap({
  apiBase,
  username,
  authLoading,
  requestedConversationId,
  fetchModelPrefs,
  fetchWorkspacePrefs,
  mapMessages,
  setMessages,
  setCurrentConversationId,
  setInitialLoading,
  activeHistoryReqRef,
}: UseChatBootstrapArgs) {
  useEffect(() => {
    let mounted = true;
    if (authLoading || !username) {
      return () => {
        mounted = false;
      };
    }

    const bootstrap = async () => {
      try {
        localStorage.setItem("username", username);
        await Promise.all([fetchModelPrefs(username), fetchWorkspacePrefs(username)]);

        const storageKey = migrateLegacyConversationStorage(username);
        const initialConversationId =
          requestedConversationId || Number(localStorage.getItem(storageKey) || 0);

        if (!initialConversationId) {
          setInitialLoading(false);
          return;
        }

        setCurrentConversationId(initialConversationId);
        const reqId = ++activeHistoryReqRef.current;
        const res = await fetch(
          `${apiBase}/api/chat/history/${initialConversationId}?username=${encodeURIComponent(username)}`,
          { credentials: "include" }
        );

        if (reqId !== activeHistoryReqRef.current || !mounted) return;

        if (res.ok) {
          const data = await res.json();
          if (reqId !== activeHistoryReqRef.current || !mounted) return;
          if (data?.messages) {
            setMessages(mapMessages(data.messages as ChatHistoryMessage[]));
          }
        } else if (res.status === 404) {
          localStorage.removeItem(getConversationStorageKey(username));
          setCurrentConversationId(null);
        }
      } catch (error) {
        console.error("初始化聊天会话失败:", error);
      } finally {
        if (mounted) {
          setInitialLoading(false);
        }
      }
    };

    void bootstrap();
    return () => {
      mounted = false;
    };
  }, [
    activeHistoryReqRef,
    apiBase,
    authLoading,
    fetchModelPrefs,
    fetchWorkspacePrefs,
    mapMessages,
    requestedConversationId,
    setCurrentConversationId,
    setInitialLoading,
    setMessages,
    username,
  ]);
}
