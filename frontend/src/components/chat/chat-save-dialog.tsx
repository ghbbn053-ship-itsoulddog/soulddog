"use client";

import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

type WorkspaceItem = {
  id: number;
  slug: string;
  name: string;
  description?: string;
  is_default: boolean;
};

type ChatSaveDialogProps = {
  open: boolean;
  workspaces: WorkspaceItem[];
  saveTargetWorkspaceId: number | null;
  saveWorkspaceName: string;
  saveWorkspaceDesc: string;
  saveStatus: string;
  savePending: boolean;
  canSave: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectWorkspace: (workspaceId: number) => void;
  onWorkspaceNameChange: (value: string) => void;
  onWorkspaceDescChange: (value: string) => void;
  onSave: () => void;
};

export function ChatSaveDialog({
  open,
  workspaces,
  saveTargetWorkspaceId,
  saveWorkspaceName,
  saveWorkspaceDesc,
  saveStatus,
  savePending,
  canSave,
  onOpenChange,
  onSelectWorkspace,
  onWorkspaceNameChange,
  onWorkspaceDescChange,
  onSave,
}: ChatSaveDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] shadow-[0_24px_64px_rgba(15,23,42,0.12)]">
        <DialogHeader>
          <DialogTitle>保存到工作区</DialogTitle>
          <DialogDescription>将当前对话整理为 Markdown 文档，存入工作区知识库。</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <div className="text-sm font-medium text-slate-900">选择工作区</div>
            <div className="space-y-2">
              {workspaces.map((item) => (
                <label
                  key={item.id}
                  className="flex cursor-pointer items-start gap-3 rounded-[1.1rem] border border-slate-200 bg-white/96 p-3 text-sm transition hover:bg-slate-50"
                >
                  <input
                    type="radio"
                    name="save-workspace"
                    checked={saveTargetWorkspaceId === item.id}
                    onChange={() => onSelectWorkspace(item.id)}
                    className="mt-1"
                  />
                  <div>
                    <div className="font-medium text-slate-900">{item.name}</div>
                    <div className="text-xs text-slate-500">{item.description || item.slug}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <div className="text-sm font-medium text-slate-900">或新建工作区</div>
            <Input
              value={saveWorkspaceName}
              onChange={(event) => onWorkspaceNameChange(event.target.value)}
              placeholder="例如：微积分答疑"
              className="border-slate-200 bg-white shadow-none"
            />
            <Textarea
              value={saveWorkspaceDesc}
              onChange={(event) => onWorkspaceDescChange(event.target.value)}
              placeholder="描述这个工作区的用途"
              className="min-h-24 border-slate-200 bg-white shadow-none"
            />
          </div>

          {saveStatus ? <div className="rounded-xl border border-slate-200 bg-slate-50/92 px-3 py-2 text-sm text-slate-700">{saveStatus}</div> : null}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            className="border-slate-300 bg-white/90 text-slate-700 hover:bg-slate-50"
            onClick={() => onOpenChange(false)}
            disabled={savePending}
          >
            取消
          </Button>
          <Button className="bg-blue-600 hover:bg-blue-700" onClick={onSave} disabled={savePending || !canSave}>
            {savePending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
