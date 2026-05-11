// Phase B clean fixture: non-mutating equivalents of MMB093-MMB097.

declare const m: Map<string, number>;
declare const buf: ArrayBuffer;
declare const items: readonly { kind: string }[];

function upsertImmutable(key: string, fallback: number): Map<string, number> {
  return m.has(key) ? m : new Map([...m, [key, fallback]]);
}

function upsertComputedImmutable(key: string): Map<string, number> {
  return m.has(key) ? m : new Map([...m, [key, 42]]);
}

function copyWithoutDetach(): ArrayBuffer {
  const target = new ArrayBuffer(buf.byteLength);
  new Uint8Array(target).set(new Uint8Array(buf));
  return target;
}

function groupImmutable(): Record<string, readonly { kind: string }[]> {
  return items.reduce<Record<string, readonly { kind: string }[]>>(
    (acc, x) => ({ ...acc, [x.kind]: [...(acc[x.kind] ?? []), x] }),
    {},
  );
}

void [upsertImmutable, upsertComputedImmutable, copyWithoutDetach, groupImmutable];
