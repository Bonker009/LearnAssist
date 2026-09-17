"use client";

import {
  IconDots,
  IconLayoutDashboard,
  IconSchool,
  IconLogout,
  IconMessage,
  IconPencil,
  IconSquareRoundedPlus,
  IconTrash,
} from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { useAuth } from "@/components/auth-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import type { ConversationSummary } from "@/lib/types";
import { cn, hasKhmer } from "@/lib/utils";

function groupLabel(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days < 1) return "Today";
  if (days < 2) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  if (days < 30) return "Previous 30 days";
  return "Older";
}

export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: {
  conversations: ConversationSummary[] | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  const { user, signOut } = useAuth();
  const onDashboard = usePathname() === "/dashboard";
  const [editing, setEditing] = React.useState<string | null>(null);

  const groups = React.useMemo(() => {
    const map = new Map<string, ConversationSummary[]>();
    for (const conversation of conversations ?? []) {
      const label = groupLabel(conversation.updatedAt);
      map.set(label, [...(map.get(label) ?? []), conversation]);
    }
    return [...map.entries()];
  }, [conversations]);

  return (
    <nav aria-label="Chats" className="flex h-full flex-col bg-canvas">
      <div className="flex h-14 items-center gap-2 px-3">
        <span
          aria-hidden
          className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground"
        >
          <IconSchool size={17} stroke={1.75} />
        </span>
        <span className="font-semibold tracking-tight">Trazyn</span>
      </div>

      <div className="px-2">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 rounded-lg"
          size="lg"
          onClick={onNew}
        >
          <IconSquareRoundedPlus size={17} />
          New chat
        </Button>
        <Link
          href="/dashboard"
          aria-current={onDashboard ? "page" : undefined}
          className={cn(
            "mt-1 flex h-9 items-center gap-2 rounded-md px-2.5 text-sm transition-colors duration-150 ease-out",
            onDashboard
              ? "bg-primary-soft font-medium text-primary-text"
              : "text-text-muted hover:bg-surface-muted hover:text-text",
          )}
        >
          <IconLayoutDashboard size={17} stroke={1.75} />
          Dashboard
        </Link>
      </div>

      <div className="mt-3 flex-1 overflow-y-auto px-2 pb-3">
        {conversations === null ? (
          <div className="flex flex-col gap-2 px-1">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-7 w-full" />
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-4 text-sm text-text-muted">
            Your chats will appear here.
          </p>
        ) : (
          groups.map(([label, items]) => (
            <div key={label} className="mb-3">
              <h3 className="micro-label px-2 pb-1.5 text-text-subtle">{label}</h3>
              <ul className="flex flex-col gap-0.5">
                {items.map((conversation) => (
                  <li key={conversation.id} className="group relative">
                    {editing === conversation.id ? (
                      <RenameField
                        initial={conversation.title}
                        onDone={(title) => {
                          setEditing(null);
                          if (title && title !== conversation.title) {
                            onRename(conversation.id, title);
                          }
                        }}
                      />
                    ) : (
                      <button
                        type="button"
                        onClick={() => onSelect(conversation.id)}
                        aria-current={conversation.id === activeId ? "page" : undefined}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-md py-2 pr-8 pl-2 text-left text-sm transition-colors duration-150 ease-out",
                          conversation.id === activeId
                            ? "bg-primary-soft font-medium text-primary-text"
                            : "text-text-muted hover:bg-surface-muted hover:text-text",
                        )}
                      >
                        <IconMessage size={15} className="shrink-0 opacity-60" />
                        <span className="truncate" lang={hasKhmer(conversation.title) ? "km" : undefined}>
                          {conversation.title}
                        </span>
                      </button>
                    )}

                    {editing !== conversation.id && (
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          render={
                            <Button
                              variant="ghost"
                              size="icon-xs"
                              aria-label={`Options for ${conversation.title}`}
                              className="absolute top-1/2 right-1 -translate-y-1/2 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 aria-expanded:opacity-100"
                            />
                          }
                        >
                          <IconDots size={14} />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-36">
                          <DropdownMenuItem onClick={() => setEditing(conversation.id)}>
                            <IconPencil size={15} /> Rename
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            variant="destructive"
                            onClick={() => onDelete(conversation.id)}
                          >
                            <IconTrash size={15} /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </div>

      <div className="flex items-center gap-1 border-t border-border px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-sm text-text-muted">{user?.displayName}</span>
        <ThemeToggle />
        <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out">
          <IconLogout size={16} />
        </Button>
      </div>
    </nav>
  );
}

function RenameField({ initial, onDone }: { initial: string; onDone: (title: string) => void }) {
  const [value, setValue] = React.useState(initial);
  return (
    <input
      autoFocus
      aria-label="Chat title"
      value={value}
      maxLength={200}
      onChange={(e) => setValue(e.target.value)}
      onFocus={(e) => e.target.select()}
      onBlur={() => onDone(value.trim())}
      onKeyDown={(e) => {
        if (e.key === "Enter") onDone(value.trim());
        if (e.key === "Escape") onDone(initial);
      }}
      className="h-8 w-full rounded-md border border-ring bg-background px-2 text-sm outline-none ring-3 ring-ring/40"
    />
  );
}
