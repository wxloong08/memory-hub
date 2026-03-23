/**
 * GrokExtractor - Extracts conversations from grok.com / x.com/i/grok (experimental)
 */
class GrokExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'grok';
  }

  isOnPlatform() {
    const host = window.location.hostname;
    const path = window.location.pathname;
    return host.includes('grok.com') ||
      (host.includes('x.com') && path.startsWith('/i/grok'));
  }

  extractConversation() {
    const context = this._extractContext();
    const messages = [];

    // Strategy 1: elements with "message" in class name
    let elements = document.querySelectorAll('[class*="message"]');
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

    // Strategy 2: elements with "turn" in class name
    elements = document.querySelectorAll('[class*="turn"]');
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

  getPreview() {
    const conversation = this.extractConversation();
    return {
      title: conversation.title || 'Grok Conversation',
      messageCount: conversation.messages.length,
      url: conversation.url
    };
  }

  _extractContext() {
    const match = window.location.pathname.match(/\/i\/grok\/([a-zA-Z0-9-]+)/);
    return {
      title: (document.title || '').replace(/\s*-\s*Grok.*$/, '').trim() || 'Grok Conversation',
      conversationId: match ? match[1] : null
    };
  }
}

if (typeof module !== 'undefined') module.exports = { GrokExtractor };
