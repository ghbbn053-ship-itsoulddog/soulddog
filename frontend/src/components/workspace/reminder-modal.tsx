import { BellRing } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type ReminderItem = {
  id: number;
  title: string;
  content: string;
  reason?: string;
  tone?: "normal" | "warning" | "urgent";
};

export function ReminderModal({
  open,
  item,
  onOpenChange,
  onAccept,
  onDismiss,
  onLater,
}: {
  open: boolean;
  item: ReminderItem | null;
  onOpenChange: (value: boolean) => void;
  onAccept: (id: number) => void;
  onDismiss: (id: number) => void;
  onLater: () => void;
}) {
  if (!item) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BellRing className="h-5 w-5 text-[hsl(var(--primary))]" />
            AI 提醒
          </DialogTitle>
          <DialogDescription>
            当前工作区检测到需要优先处理的事项，建议先处理它，再继续聊天或整理知识库。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="text-sm font-medium text-slate-950">{item.title}</div>
          <div className="text-sm leading-6 text-slate-700">{item.content}</div>
          {item.reason ? <div className="text-xs leading-5 text-slate-500">原因：{item.reason}</div> : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onLater}>
            稍后处理
          </Button>
          <Button variant="outline" onClick={() => onDismiss(item.id)}>
            忽略
          </Button>
          <Button onClick={() => onAccept(item.id)}>立即开始</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
