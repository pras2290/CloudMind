import type { ReactNode } from "react";
import * as T from "@radix-ui/react-tooltip";

export function Tooltip({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: T.TooltipContentProps["side"] }) {
  return (
    <T.Root>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          side={side}
          sideOffset={6}
          className="z-50 rounded-md bg-slate-900 px-2 py-1 text-xs text-white shadow-md animate-fade-in dark:bg-slate-100 dark:text-slate-900"
        >
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}
