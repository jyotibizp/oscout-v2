import { useEffect, useState } from "react";
import { api } from "../api/client";

export interface Sym { symbol: string; testing: boolean }
const FALLBACK: Sym[] = [{ symbol: "NIFTY", testing: false }, { symbol: "SENSEX", testing: false }, { symbol: "BANKNIFTY", testing: true }];
let cached: Promise<Sym[]> | null = null;

/** Tradable indexes from the server (source of truth), fetched once; "testing" = on trial (#19), tagged and no chime. */
export function useSymbols(): Sym[] {
  const [syms, setSyms] = useState<Sym[]>(FALLBACK);
  useEffect(() => {
    cached ??= api.symbols().catch(() => { cached = null; return FALLBACK; });
    let live = true;
    cached.then((s) => live && setSyms(s));
    return () => { live = false; };
  }, []);
  return syms;
}

export const resetSymbolsCache = () => { cached = null; };
