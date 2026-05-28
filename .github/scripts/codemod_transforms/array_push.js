/**
 * jscodeshift transform: replace `arr.push(item)` with `arr = [...arr, item]`.
 *
 * Skips:
 *   - `router.push`, `history.push`, `navigation.push` (navigation, not mutation)
 *   - `stream.push`, `subject.next` (auto-allowed receivers)
 *   - calls with no arguments
 *   - calls where the receiver is not a plain identifier or member expression
 */

"use strict";

const NAV_RECEIVERS = new Set([
  "router",
  "history",
  "navigation",
  "redirect",
  "stream",
  "ws",
  "res",
  "subject",
]);

function isNavReceiver(node) {
  if (!node) return false;
  if (node.type === "Identifier") {
    return NAV_RECEIVERS.has(node.name);
  }
  if (node.type === "MemberExpression") {
    return isNavReceiver(node.object);
  }
  return false;
}

module.exports = function transformer(file, api) {
  const j = api.jscodeshift;
  const root = j(file.source);
  root
    .find(j.ExpressionStatement, {
      expression: {
        type: "CallExpression",
        callee: { type: "MemberExpression", property: { name: "push" } },
      },
    })
    .forEach((path) => {
      const call = path.node.expression;
      const receiver = call.callee.object;
      if (isNavReceiver(receiver)) return;
      if (call.arguments.length === 0) return;
      if (receiver.type !== "Identifier" && receiver.type !== "MemberExpression") {
        return;
      }
      const newArray = j.arrayExpression([
        j.spreadElement(receiver),
        ...call.arguments,
      ]);
      const assign = j.assignmentExpression("=", receiver, newArray);
      path.replace(j.expressionStatement(assign));
    });
  return root.toSource({ quote: "single", reuseWhitespace: true });
};
