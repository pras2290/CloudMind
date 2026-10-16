import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { Menu, Moon, PanelLeft, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";
import { KBStatusPill } from "./KBStatusPill";
import { Button } from "./ui/button";
import { Tooltip } from "./ui/tooltip";

export default function AppShell() {
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("cloudmind-sidebar") === "collapsed");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem("cloudmind-sidebar", collapsed ? "collapsed" : "open");
  }, [collapsed]);

  const title = location.pathname.startsWith("/knowledge") ? "Knowledge base" : "Chat";

  return (
    <div className="flex h-full overflow-hidden">
      <aside className={cn("hidden shrink-0 border-r transition-[width] duration-200 md:block", collapsed ? "w-0 overflow-hidden border-r-0" : "w-72")}>
        <Sidebar />
      </aside>

      <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/50 md:hidden" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-72 border-r shadow-xl animate-fade-in md:hidden" aria-describedby={undefined}>
            <Dialog.Title className="sr-only">Navigation</Dialog.Title>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur md:px-4">
          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu />
          </Button>
          <Tooltip content={collapsed ? "Show sidebar" : "Hide sidebar"} side="bottom">
            <Button variant="ghost" size="icon" className="hidden md:inline-flex" onClick={() => setCollapsed((c) => !c)} aria-label="Toggle sidebar">
              <PanelLeft />
            </Button>
          </Tooltip>
          <h1 className="text-sm font-medium">{title}</h1>
          <div className="ml-auto flex items-center gap-2">
            <KBStatusPill />
            <Tooltip content={theme === "dark" ? "Light mode" : "Dark mode"} side="bottom">
              <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
                {theme === "dark" ? <Sun /> : <Moon />}
              </Button>
            </Tooltip>
          </div>
        </header>
        <main className="min-h-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
