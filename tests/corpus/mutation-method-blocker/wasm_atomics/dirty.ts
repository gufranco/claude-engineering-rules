// @allow-mutation -- corpus fixture; this file is the dirty input for Phase 34 detector tests
//
// WebAssembly / Atomics / DataView / Proxy / WeakRef dirty fixture.
//
// Every line below must be flagged by mutation-method-blocker outside hot
// paths. Detector tags expected (one per line where applicable):
//
//   web-api.dataview.setInt32           - DataView setter
//   web-api.dataview.setFloat64         - DataView setter
//   typed-array.uint8.set-with-offset   - two-arg Uint8Array.set
//   shared-memory.atomics.store         - SAB write
//   shared-memory.atomics.compareExchange
//   wasm.memory.grow                    - WebAssembly memory grow
//   proxy.trap.set                      - mutating Proxy trap
//   proxy.trap.deleteProperty           - mutating Proxy trap
//   weakref.deref-mutate.push           - mutate via WeakRef.deref()
//   finalization-registry.construct     - info signal

declare const WebAssembly: any;
declare const Atomics: any;

const buffer = new ArrayBuffer(64);
const view = new DataView(buffer);
view.setInt32(0, 42, true);
view.setFloat64(8, 3.14, false);
view.setBigInt64(16, 1n);

const buf = new Uint8Array(64);
const src = new Uint8Array([1, 2, 3, 4]);
buf.set(src, 8);

const sab = new SharedArrayBuffer(64);
const sabView = new Int32Array(sab);
Atomics.store(sabView, 0, 1);
Atomics.compareExchange(sabView, 0, 1, 2);

const memory = new WebAssembly.Memory({ initial: 1 });
memory.grow(1);

const handler = {
  set(target: any, key: string, value: any) {
    target[key] = value;
    return true;
  },
  deleteProperty(target: any, key: string) {
    return delete target[key];
  },
};
const proxy = new Proxy({}, handler);

const list: number[] = [];
const ref = new WeakRef(list);
ref.deref()?.push(1);

const registry = new FinalizationRegistry((heldValue: string) => {
  // info: registry construction reported regardless of body
});
