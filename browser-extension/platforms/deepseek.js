/**
 * DeepSeekExtractor - Extracts conversations from chat.deepseek.com (experimental)
 */
class DeepSeekExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'deepseek';
  }

  isOnPlatform() {
    return window.location.hostname.includes('chat.deepseek.com');
  }

  extractConversation() {
    const context = this._extractContext();
    const messages = [];

    // Strategy 1: .ds-markdown elements (DeepSeek's markdown renderer)
    let elements = document.querySelectorAll('.ds-markdown');
    if (elements.length > 0) {
      return {
        title: context.title,
        url: window.location.href,
        conversationId: context.conversationId,
        messages: this._parseWithContext(elements)
      };
    }

    // Strategy 2: .markdown-body elements
    elements = document.querySelectorAll('.markdown-body');
    if (elements.length > 0) {
      return {
        title: context.title,
        url: window.location.href,
        conversationId: context.conversationId,
        messages: this._parseWithContext(elements)
      };
    }

    // Strategy 3: generic message/turn patterns
    const selectors = ['[class*="message"]', '[class*="turn"]', '[class*="chat-item"]'];
    for (const selector of selectors) {
      elements = document.querySelectorAll(selector);
      if (elements.length > 0) {
        elements.forEach(el => {
          const content = this._extractTextContent(el);
          if (!content) return;
          const role = this._determineRole(el);
          messages.push({ role, content });
        });
        if (messages.length > 0) {
          return {
            title: context.title,
            url: window.location.href,
            conversationId: context.conversationId,
            messages
          };
        }
      }
    }

    return {
      title: context.title,
      url: window.location.href,
      conversationId: context.conversationId,
      messages
    };
  }

  /**
   * Parse markdown-rendered elements, using parent container for role context.
   */
  _parseWithContext(elements) {
    const messages = [];
    elements.forEach(el => {
      const content = this._extractTextContent(el);
      if (!content) return;

      // Check parent/ancestor for role hints
      const container = el.closest('[class*="message"], [class*="turn"], [class*="chat"]');
      const role = container ? this._determineRole(container) : 'assistant';
      messages.push({ role, content });
    });
    return messages;
  }

  getPreview() {
    const conversation = this.extractConversation();
    return {
      title: conversation.title || 'DeepSeek Conversation',
      messageCount: conversation.messages.length,
      url: conversation.url
    };
  }

  _extractContext() {
    const match = window.location.pathname.match(/\/chat\/([a-zA-Z0-9-]+)/);
    return {
      title: (document.title || '').replace(/\s*-\s*DeepSeek.*$/, '').trim() || 'DeepSeek Conversation',
      conversationId: match ? match[1] : null
    };
  }
}

if (typeof module !== 'undefined') module.exports = { DeepSeekExtractor };
