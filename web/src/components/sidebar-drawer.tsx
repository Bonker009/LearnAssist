"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/** The app's left column: fixed on desktop, a slide-in drawer on mobile. */
export function SidebarDrawer({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-72 border-r border-border transition-transform duration-200 ease-out md:static md:z-auto md:w-64 md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {children}
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
