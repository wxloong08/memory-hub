/**
 * PlatformExtractor - Base class for AI platform conversation extractors.
 * Each platform implements its own subclass with DOM-specific selectors.
 */
class PlatformExtractor {
  /**
   * Returns the platform identifier string (e.g. 'claude_web', 'chatgpt').
   * @returns {string}
   */
  getPlatformName() {
    throw new Error('getPlatformName() must be implemented by subclass');
  }

  /**
   * Returns true if the current page belongs to this platform.
   * @returns {boolean}
   */
  isOnPlatform() {
    throw new Error('isOnPlatform() must be implemented by subclass');
  }

  /**
   * Extract all conversation messages from the current page DOM.
   * @returns {Array<{role: string, content: string}>}
   */
  extractConversation() {
    throw new Error('extractConversation() must be implemented by subclass');
  }

  /**
   * Get a short preview/summary of the current conversation state.
   * @returns {{title: string, messageCount: number, url: string}}
   */
  getPreview() {
    return {
      title: document.title || 'Untitled',
      messageCount: 0,
      url: window.location.href
    };
  }

  /**
   * Return assistant identity metadata for the current platform.
   * Platforms can override this when they can detect a concrete model.
   * @returns {{provider: string|null, model: string|null, assistantLabel: string|null}}
   */
  getAssistantMetadata() {
    const platform = this.getPlatformName();
    const defaults = {
      claude_web: { provider: 'anthropic', model: null, assistantLabel: 'Claude' },
      claude_code: { provider: 'anthropic', model: null, assistantLabel: 'Claude Code' },
      chatgpt: { provider: 'openai', model: null, assistantLabel: 'ChatGPT' },
      gemini: { provider: 'google', model: null, assistantLabel: 'Gemini' },
      grok: { provider: 'xai', model: null, assistantLabel: 'Grok' },
      deepseek: { provider: 'deepseek', model: null, assistantLabel: 'DeepSeek' },
    };

    return defaults[platform] || { provider: null, model: null, assistantLabel: 'Assistant' };
  }

  /**
   * Determine the role (user or assistant) of a message element.
   * Checks common CSS class patterns across platforms.
   * @param {Element} element
   * @returns {string} 'user' or 'assistant'
   */
  _determineRole(element) {
    const classStr = (element.className || '').toLowerCase();
    const html = element.outerHTML.substring(0, 500).toLowerCase();

    // Check for user-side patterns
    const userPatterns = ['user', 'human', 'query', 'request', 'prompt'];
    for (const pattern of userPatterns) {
      if (classStr.includes(pattern) || html.includes(`role="${pattern}"`)) {
        return 'user';
      }
    }

    // Check for assistant-side patterns
    const assistantPatterns = ['assistant', 'bot', 'response', 'model', 'ai'];
    for (const pattern of assistantPatterns) {
      if (classStr.includes(pattern) || html.includes(`role="${pattern}"`)) {
        return 'assistant';
      }
    }

    return 'assistant';
  }

  /**
   * Extract text content from an element, preserving code blocks.
   * @param {Element} element
   * @returns {string}
   */
  _extractTextContent(element) {
    if (!element) return '';

    // Clone to avoid modifying the live DOM
    const clone = element.cloneNode(true);

    // Remove common non-content UI nodes that often duplicate accessible text.
    clone.querySelectorAll('script, style, svg, button, textarea, input, select').forEach(node => {
      node.remove();
    });
    // Replace code blocks with fenced markers
    const codeBlocks = clone.querySelectorAll('pre code, pre');
    codeBlocks.forEach(block => {
      const lang = block.className
        ? block.className.replace(/^language-/, '').split(/\s/)[0]
        : '';
      const code = block.textContent || '';
      const marker = document.createTextNode(
        '\n```' + lang + '\n' + code + '\n```\n'
      );
      block.parentNode.replaceChild(marker, block);
    });

    const text = (clone.textContent || '').replace(/\u200b/g, '');
    return text
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean)
      .join('\n')
      .trim();
  }
}

if (typeof module !== 'undefined') module.exports = { PlatformExtractor };
