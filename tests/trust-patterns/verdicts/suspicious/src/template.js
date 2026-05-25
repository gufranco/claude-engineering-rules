// Single dynamic eval. Section B HIGH if standalone, demoted to MEDIUM in fixture context.
export function renderTemplate(expression, context) {
  return eval(expression);
}
