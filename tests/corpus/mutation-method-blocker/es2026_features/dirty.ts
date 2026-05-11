// @claude-allow-mutation -- corpus fixture; ES2026 detector test cases retained for Phase B
//
// Phase B dirty fixture: Map upsert (MMB093/MMB094), ArrayBuffer.transfer
// (MMB095/MMB096), and Object.groupBy bucket push (MMB097).

declare const m: Map<string, number>;
declare const buf: ArrayBuffer;
declare const items: readonly { kind: string }[];

function upsertSimple(key: string, fallback: number): number {
  return m.getOrInsert(key, fallback);
}

function upsertComputed(key: string): number {
  return m.getOrInsertComputed(key, () => 42);
}

function detachAndCopy(): ArrayBuffer {
  return buf.transfer();
}

function detachToFixed(n: number): ArrayBuffer {
  return buf.transferToFixedLength(n);
}

function groupAndMutate(): Record<string, { kind: string }[]> {
  const grouped = Object.groupBy(items, (x) => x.kind);
  grouped["extra"].push({ kind: "extra" });
  return grouped as Record<string, { kind: string }[]>;
}

void [upsertSimple, upsertComputed, detachAndCopy, detachToFixed, groupAndMutate];
