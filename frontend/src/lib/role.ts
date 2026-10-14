import { useEffect, useState } from "react";
import { api } from "../api/client";

export type Role = "admin" | "viewer";
let cached: Promise<Role> | null = null;

/** "admin" only on the Mac itself; friends over Tailscale are view-only. Viewer until the server says otherwise. */
export function useRole(): Role {
  const [role, setRole] = useState<Role>("viewer");
  useEffect(() => {
    cached ??= api.whoami().then((r) => r.role, () => { cached = null; return "viewer" as Role; });
    let live = true;
    cached.then((r) => live && setRole(r));
    return () => { live = false; };
  }, []);
  return role;
}

export const resetRoleCache = () => { cached = null; };
