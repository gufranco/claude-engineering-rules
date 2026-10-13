export function renderTemplate(template, context) {
  return template.replace(/\{\{(\w+)\}\}/g, (_match, key) => String(context[key] ?? ''));
}
