/**
 * GeminiExtractor - Extracts conversations from gemini.google.com (experimental)
 */
class GeminiExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'gemini';
  }

  isOnPlatform() {
    return window.location.hostname.includes('gemini.google.com');
  }

  extractConversation() {
    const context = this._extractContext();
    const messages = [];

    // Strategy 1: message-content elements
    let elements = document.querySelectorAll('message-content');
    if (elements.length > 0) {
      return {
        title: context.title,
        url: window.location.href,
        conversationId: context.conversationId,
        messages: this._parseMessageContent(elements)
      };
    }

    // Strategy 2: conversation-turn class
    elements = document.querySelectorAll('.conversation-turn');
    if (elements.length > 0) {
      elements.forEach(el => {
        const content = this._extractTextContent(el);
        if (!content) return;
        const role = this._determineRole(el);
        messages.push({ role, content });
      });
      return {
        title: context.title,
        url: window.location.href,
        conversationId: context.conversationId,
        messages
      };
    }

    // Strategy 3: query/response pattern
    const queries = document.querySelectorAll('[class*="query"], [class*="request"]');
    const responses = document.querySelectorAll('[class*="response"], [class*="model"]');

    queries.forEach(el => {
      const content = this._extractTextContent(el);
      if (content) messages.push({ role: 'user', content });
    });
    responses.forEach(el => {
      const content = this._extractTextContent(el);
      if (content) messages.push({ role: 'assistant', content });
    });

    return {
      title: context.title,
      url: window.location.href,
      conversationId: context.conversationId,
      messages
    };
  }

  _parseMessageContent(elements) {
    const messages = [];
    elements.forEach(el => {
      const content = this._extractTextContent(el);
      if (!content) return;
      // Use base class role detection
      const role = this._determineRole(el);
      messages.push({ role, content });
    });
    return messages;
  }

  getPreview() {
    const conversation = this.extractConversation();
    return {
      title: conversation.title || 'Gemini Conversation',
      messageCount: conversation.messages.length,
      url: conversation.url
    };
  }

  _extractContext() {
    return {
      title: (document.title || '').replace(/\s*-\s*Gemini.*$/, '').trim() || 'Gemini Conversation',
      conversationId: null
    };
  }
}

if (typeof module !== 'undefined') module.exports = { GeminiExtractor };
