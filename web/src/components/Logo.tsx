import { Cloud } from "lucide-react";
import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm", className)}>
      <Cloud className="h-[18px] w-[18px]" fill="currentColor" strokeWidth={1.5} />
    </div>
  );
}
