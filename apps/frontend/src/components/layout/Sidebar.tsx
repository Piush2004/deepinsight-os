"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { Users, Settings, LayoutDashboard, Briefcase, FileText, PenTool, BookOpen, CheckSquare, Sparkles, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { isDemoMode, DEMO_USERS, getDemoUser } from "@/lib/demo-auth";

const navigation = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Client Portals", href: "/clients", icon: Briefcase },
  { name: "Approval Center", href: "/approvals", icon: CheckSquare },
  { name: "Agent Center", href: "/agents", icon: Sparkles },
  { name: "Reporting Engine", href: "/reports", icon: FileText },
  { name: "Content Platform", href: "/content", icon: PenTool },
  { name: "SEO Intelligence", href: "/seo", icon: Search },
  { name: "Knowledge Base", href: "/knowledge", icon: BookOpen },
  { name: "Team Settings", href: "/settings", icon: Settings },
];

// Branches at module scope, not inside the component - isDemoMode() is a build-time
// constant, and useUser() must never actually be called when there's no ClerkProvider
// in the tree (demo mode, see src/app/layout.tsx). Same pattern as src/hooks/useApiClient.ts.
function useDemoDisplayUser() {
  const demoUser = DEMO_USERS.find((u) => u.clerkId === getDemoUser()) ?? DEMO_USERS[0];
  return { fullName: demoUser.label, email: `${demoUser.clerkId}@demo.deepinsight.local` };
}

function useClerkDisplayUser() {
  const { user } = useUser();
  return { fullName: user?.fullName ?? null, email: user?.primaryEmailAddress?.emailAddress ?? null };
}

const useDisplayUser = isDemoMode() ? useDemoDisplayUser : useClerkDisplayUser;

export function Sidebar() {
  const pathname = usePathname();
  const user = useDisplayUser();

  return (
    <div className="flex h-full w-64 flex-col border-r border-border bg-card">
      <div className="flex h-20 items-center px-8 border-b border-border/50">
        <span className="text-xl font-heading font-medium tracking-tight text-foreground">
          DeepInsight OS
        </span>
      </div>
      <nav className="flex-1 space-y-1.5 px-4 py-8">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center rounded-md px-4 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
              )}
            >
              <item.icon
                className={cn(
                  "mr-3 h-4 w-4 flex-shrink-0 transition-colors",
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground group-hover:text-primary"
                )}
                aria-hidden="true"
              />
              {item.name}
            </Link>
          );
        })}
      </nav>
      
      {/* Mini Profile Section at Bottom */}
      <div className="p-4 border-t border-border/50">
        <div className="flex items-center space-x-3 px-4 py-2 rounded-md hover:bg-muted/50 transition-colors cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Users className="w-4 h-4 text-primary" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{user.fullName ?? user.email ?? "Loading..."}</p>
            <p className="text-xs text-muted-foreground">{user.email ?? ""}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
