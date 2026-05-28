/**
 * jscodeshift transform: replace `arr.reverse()` with `arr.toReversed()`.
 */

"use strict";

module.exports = function transformer(file, api) {
  const j = api.jscodeshift;
  const root = j(file.source);
  root
    .find(j.CallExpression, {
      callee: { type: "MemberExpression", property: { name: "reverse" } },
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
      callee.property = j.identifier("toReversed");
    });
  return root.toSource({ quote: "single", reuseWhitespace: true });
};
