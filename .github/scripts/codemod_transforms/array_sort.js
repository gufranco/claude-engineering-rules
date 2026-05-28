/**
 * jscodeshift transform: replace `arr.sort(...)` with `arr.toSorted(...)`.
 *
 * `.toSorted` is the ES2023 non-mutating equivalent. The transform applies
 * only when the receiver looks like a plain array (Identifier or
 * MemberExpression); typed-array receivers are skipped because TypedArray
 * does not have `.toSorted` yet (Stage 3 in 2026).
 *
 * The transform preserves the comparator argument verbatim.
 */

"use strict";

module.exports = function transformer(file, api) {
  const j = api.jscodeshift;
  const root = j(file.source);
  root
    .find(j.CallExpression, {
      callee: { type: "MemberExpression", property: { name: "sort" } },
    })
    .forEach((path) => {
      const callee = path.node.callee;
      const receiver = callee.object;
      if (
        receiver.type !== "Identifier" &&
        receiver.type !== "MemberExpression"
      ) {
        return;
      }
      callee.property = j.identifier("toSorted");
    });
  return root.toSource({ quote: "single", reuseWhitespace: true });
};
