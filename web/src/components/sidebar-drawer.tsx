"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * The app's left column: a column on desktop that can be collapsed, and a slide-in
 * drawer on mobile. The two have separate state, because opening the drawer on a
 * phone should not decide whether the column is shown on a laptop.
 */
export function SidebarDrawer({
  open,
  collapsed = false,
  onClose,
  children,
}: {
  /** Mobile: the drawer is showing. */
  open: boolean;
  /** Desktop: the column is folded away. */
  collapsed?: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-72 overflow-hidden border-r border-border transition-[translate,width] duration-200 ease-out md:static md:z-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
          collapsed ? "md:w-0 md:border-r-0" : "md:w-64",
        )}
        // Out of the tab order and the accessibility tree while folded away.
        inert={collapsed && !open ? true : undefined}
      >
        {/* Fixed width inside, so the content doesn't squash while the column animates. */}
        <div className="h-full w-72 md:w-64">{children}</div>
      </div>
      {open && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={onClose}
        />
      )}
    </>
  );
}
