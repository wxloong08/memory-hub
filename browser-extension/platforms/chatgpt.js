/**
 * ChatGPTExtractor - Extracts conversations from chatgpt.com / chat.openai.com
 */
class ChatGPTExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'chatgpt';
  }

  isOnPlatform() {
    const host = window.location.hostname;
    return host.includes('chatgpt.com') || host.includes('chat.openai.com');
  }

  extractConversation() {
    const context = this._extractContext();
    const messages = [];

    // Primary selector: article elements with conversation-turn test IDs
    let turns = document.querySelectorAll('article[data-testid^="conversation-turn"]');

    if (turns.length === 0) {
      // Fallback: generic turn-based selectors
      turns = document.querySelectorAll('[data-testid^="conversation-turn"], [class*="ConversationItem"]');
    }

    turns.forEach(turn => {
      const content = this._extractTextContent(turn);
      if (!content) return;

      // ChatGPT uses data-message-author-role attribute
      const authorEl = turn.querySelector('[data-message-author-role]');
      let role = 'assistant';

      if (authorEl) {
        const authorRole = authorEl.getAttribute('data-message-author-role');
        role = (authorRole === 'user') ? 'user' : 'assistant';
      } else {
        role = this._determineRole(turn);
      }

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
      title: conversation.title || 'ChatGPT Conversation',
      messageCount: conversation.messages.length,
      url: conversation.url
    };
  }

  _determineRole(element) {
    const classStr = (element.className || '').toLowerCase();
    // ChatGPT sometimes uses 'user-turn' or similar patterns
    if (classStr.includes('user')) return 'user';
    if (classStr.includes('assistant')) return 'assistant';
    return super._determineRole(element);
  }

  _extractContext() {
    const match = window.location.pathname.match(/\/c\/([a-zA-Z0-9-]+)/);
    return {
      title: (document.title || '').replace(/\s*\|\s*ChatGPT.*$/, '').trim() || 'ChatGPT Conversation',
      conversationId: match ? match[1] : null
    };
  }
}

if (typeof module !== 'undefined') module.exports = { ChatGPTExtractor };
