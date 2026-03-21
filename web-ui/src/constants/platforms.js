export const PLATFORM_EMOJIS = {
  claude_web: '\u{1F7E3}', chatgpt: '\u{1F7E2}', gemini: '\u{1F535}',
  grok: '\u{1F7E1}', deepseek: '\u{1F537}', claude_code: '\u26AB',
  codex: '\u{1F7E0}', gemini_cli: '\u{1F539}', antigravity: '\u{1FA90}',
  test: '\u{1F527}', test_manual: '\u{1F527}'
}

export const PLATFORM_CLASSES = {
  claude_web: 'bg-orange-100 text-orange-900',
  chatgpt: 'bg-emerald-100 text-emerald-900',
  gemini: 'bg-cyan-100 text-cyan-900',
  gemini_cli: 'bg-cyan-100 text-cyan-900',
  grok: 'bg-amber-100 text-amber-900',
  deepseek: 'bg-sky-100 text-sky-900',
  claude_code: 'bg-stone-200 text-stone-900',
  codex: 'bg-lime-100 text-lime-900',
  antigravity: 'bg-violet-100 text-violet-900',
}

export function platformEmoji(name) {
  return PLATFORM_EMOJIS[name] || '\u26AA'
}

export function platformClass(name) {
  return PLATFORM_CLASSES[name] || 'bg-gray-50 text-gray-700'
}
