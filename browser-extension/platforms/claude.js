/**
 * ClaudeExtractor - Extracts conversations from claude.ai
 */
class ClaudeExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'claude_web';
  }

  isOnPlatform() {
    return window.location.hostname.includes('claude.ai');
  }

  extractConversation() {
    const context = this._extractContext();
    const structured = this._extractStructuredConversation(context.conversationId);
    const messages = structured?.messages?.length
      ? structured.messages
      : this._extractMessages();
    return {
      title: structured?.title || context.title,
      url: window.location.href,
      conversationId: structured?.conversationId || context.conversationId,
      summary: structured?.summary || null,
      messages
    };
  }

  _extractMessages() {
    // Strategy 1: mixed user/assistant candidates in DOM order
    let messages = this._parseMixedCandidates();
    if (messages.length > 0) {
      return this._dedupeMessages(messages);
    }

    // Strategy 2: data-test-render-count attribute
    let elements = document.querySelectorAll('[data-test-render-count]');
    if (elements.length > 0) {
      return this._dedupeMessages(this._parseElements(elements));
    }

    // Strategy 3: font-claude-message class (with DOM-order fix)
    elements = document.querySelectorAll('.font-claude-message');
    if (elements.length > 0) {
      return this._dedupeMessages(this._parseFontClaudeMessages());
    }

    // Strategy 4: generic message element patterns
    const selectors = [
      '[class*="message"]',
      '[role="article"]',
      '[class*="conversation"]'
    ];
    for (const selector of selectors) {
      elements = document.querySelectorAll(selector);
      if (elements.length > 0) {
        return this._dedupeMessages(this._parseElements(elements));
      }
    }

    return [];
  }

  getPreview() {
    const conversation = this.extractConversation();
    return {
      title: conversation.title || 'Claude Conversation',
      messageCount: conversation.messages.length,
      url: conversation.url
    };
  }

  _parseMixedCandidates() {
    const candidateSelector = [
      '[data-is-user-message="true"]',
      '[data-testid*="user"]',
      '[class*="user"]',
      '[class*="human"]',
      '.font-claude-message',
      '[data-testid*="assistant"]',
      '[class*="assistant"]',
      '[data-test-render-count]'
    ].join(', ');

    const rawCandidates = Array.from(document.querySelectorAll(candidateSelector));
    if (rawCandidates.length === 0) {
      return [];
    }

    const filtered = rawCandidates.filter(el => !this._hasNestedCandidate(el, rawCandidates));
    const sorted = filtered.sort((a, b) => {
      const pos = a.compareDocumentPosition(b);
      if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
      if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
      return 0;
    });

    return sorted
      .map(el => {
        const role = this._determineRole(el);
        const content = this._extractMessageContent(el, role);
        if (!content) {
          return null;
        }
        return {
          role,
          content
        };
      })
      .filter(Boolean);
  }

  /**
   * Strategy 2 parser: font-claude-message elements may not reflect
   * visual DOM order. Use compareDocumentPosition to sort.
   */
  _parseFontClaudeMessages() {
    const allCandidates = document.querySelectorAll(
      '.font-claude-message, [data-is-user-message="true"], [class*="human"], [class*="user"]'
    );
    const sorted = Array.from(allCandidates).sort((a, b) => {
      const pos = a.compareDocumentPosition(b);
      if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
      if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
      return 0;
    });

    const messages = [];
    sorted.forEach(el => {
      const role = this._determineRole(el);
      const content = this._extractMessageContent(el, role);
      if (!content) return;
      messages.push({ role, content });
    });

    return messages;
  }

  /**
   * Generic element parser used by strategies 1 and 3.
   */
  _parseElements(elements) {
    const messages = [];
    elements.forEach(el => {
      const role = this._determineRole(el);
      const content = this._extractMessageContent(el, role);
      if (!content) return;
      messages.push({ role, content });
    });
    return messages;
  }

  _extractMessageContent(element, role) {
    const content = this._extractTextContent(element);
    if (!content) {
      return '';
    }

    if (role !== 'assistant') {
      return content;
    }

    const normalized = this._normalizeAssistantDomContent(content);
    return normalized || content;
  }

  /**
   * Override: Claude-specific role detection.
   */
  _determineRole(element) {
    const signals = this._collectRoleSignals(element);
    const combined = signals.join(' ');

    if (
      combined.includes('data-is-user-message="true"') ||
      combined.includes('data-is-user-message=true') ||
      combined.includes('user-message') ||
      combined.includes('human') ||
      combined.includes('sender-user') ||
      combined.includes('data-testid=user') ||
      combined.includes('data-testid=chat-message-user') ||
      combined.includes('role="user"')
    ) {
      return 'user';
    }

    // Claude uses 'font-claude-message' for assistant replies
    if (
      combined.includes('font-claude-message') ||
      combined.includes('assistant') ||
      combined.includes('data-testid=assistant') ||
      combined.includes('data-testid=chat-message-assistant') ||
      combined.includes('role="assistant"')
    ) {
      return 'assistant';
    }

    // Fall back to base class
    return super._determineRole(element);
  }

  _collectRoleSignals(element) {
    const signals = [];
    let current = element;
    let depth = 0;

    while (current && depth < 5) {
      const classStr = (current.className || '').toString().toLowerCase();
      const idStr = (current.id || '').toLowerCase();
      const attrs = Array.from(current.attributes || [])
        .map(attr => `${attr.name}=${String(attr.value).toLowerCase()}`)
        .join(' ');

      signals.push(classStr, idStr, attrs);
      current = current.parentElement;
      depth += 1;
    }

    return signals;
  }

  _hasNestedCandidate(element, candidates) {
    return candidates.some(other => other !== element && element.contains(other));
  }

  _extractStructuredConversation(conversationId) {
    const jsonDocuments = this._extractInlineJsonDocuments(conversationId);
    for (const doc of jsonDocuments) {
      const conversation = this._findConversationInJson(doc, conversationId);
      if (conversation) {
        return conversation;
      }
    }
    return null;
  }

  _extractInlineJsonDocuments(conversationId) {
    const scripts = Array.from(document.querySelectorAll('script:not([src])'));
    const documents = [];

    for (const script of scripts) {
      const text = (script.textContent || '').trim();
      if (!text || text.length < 2) {
        continue;
      }

      const looksLikeJson =
        script.type === 'application/json' ||
        script.type === 'application/ld+json' ||
        text.startsWith('{') ||
        text.startsWith('[');

      if (!looksLikeJson) {
        continue;
      }

      const needsConversationHint =
        /chat_messages|sender|thinking|artifacts|conversation/i.test(text) ||
        (conversationId && text.includes(conversationId));
      if (!needsConversationHint) {
        continue;
      }

      try {
        documents.push(JSON.parse(text));
      } catch (_) {
        // Ignore non-JSON inline scripts.
      }
    }

    return documents;
  }

  _findConversationInJson(root, conversationId) {
    const stack = [root];
    let visited = 0;

    while (stack.length > 0 && visited < 20000) {
      const node = stack.pop();
      visited += 1;

      if (!node || typeof node !== 'object') {
        continue;
      }

      const normalized = this._normalizeStructuredConversation(node, conversationId);
      if (normalized) {
        return normalized;
      }

      if (Array.isArray(node)) {
        for (const item of node) {
          stack.push(item);
        }
        continue;
      }

      for (const value of Object.values(node)) {
        stack.push(value);
      }
    }

    return null;
  }

  _normalizeStructuredConversation(node, conversationId) {
    if (!node || typeof node !== 'object' || Array.isArray(node)) {
      return null;
    }

    const rawMessages = Array.isArray(node.chat_messages)
      ? node.chat_messages
      : Array.isArray(node.messages)
        ? node.messages
        : null;
    if (!rawMessages || rawMessages.length === 0) {
      return null;
    }

    if (!rawMessages.some(message => this._looksLikeStructuredMessage(message))) {
      return null;
    }

    const nodeId = String(
      node.uuid || node.id || node.conversation_uuid || node.conversationId || ''
    ).trim();
    if (conversationId && nodeId && nodeId !== conversationId) {
      return null;
    }

    const messages = rawMessages
      .map(message => this._normalizeStructuredMessage(message))
      .filter(Boolean);
    if (messages.length === 0) {
      return null;
    }

    return {
      conversationId: nodeId || conversationId || null,
      title: this._pickStructuredTitle(node),
      summary: this._normalizeSummaryText(node.summary || node.description || ''),
      messages: this._dedupeMessages(messages)
    };
  }

  _looksLikeStructuredMessage(message) {
    if (!message || typeof message !== 'object') {
      return false;
    }

    return Boolean(
      message.sender ||
      message.role ||
      message.text ||
      Array.isArray(message.content) ||
      typeof message.content === 'string'
    );
  }

  _normalizeStructuredMessage(message) {
    if (!this._looksLikeStructuredMessage(message)) {
      return null;
    }

    const role = this._normalizeStructuredRole(
      message.sender || message.role || message.author || ''
    );

    let content = '';
    if (Array.isArray(message.content) && message.content.length > 0) {
      content = this._renderStructuredBlocks(message.content);
    } else {
      content = this._normalizeMessageContent(message.text || message.content || '');
    }

    const attachments = this._renderStructuredAttachments(message);
    const combined = [content, attachments].filter(Boolean).join('\n\n').trim();
    if (!combined) {
      return null;
    }

    return { role, content: combined };
  }

  _normalizeStructuredRole(roleValue) {
    const lowered = String(roleValue || '').toLowerCase();
    if (lowered === 'human' || lowered === 'user') {
      return 'user';
    }
    return 'assistant';
  }

  _renderStructuredBlocks(blocks) {
    return blocks
      .map(block => this._renderStructuredBlock(block))
      .filter(Boolean)
      .join('\n\n')
      .trim();
  }

  _renderStructuredBlock(block) {
    if (!block || typeof block !== 'object') {
      return '';
    }

    const blockType = block.type || '';

    if (blockType === 'text') {
      return this._normalizeMessageContent(block.text || '');
    }

    if (blockType === 'thinking') {
      const thinking = this._normalizeMessageContent(block.thinking || '');
      const summaries = Array.isArray(block.summaries) ? block.summaries : [];
      const summaryText = summaries
        .map(item => this._normalizeMessageContent(item?.summary || ''))
        .filter(Boolean)
        .join(' | ');

      const parts = [];
      if (summaryText) {
        parts.push(`> Thought Summary: ${summaryText}`);
      }
      if (thinking) {
        parts.push('<details>');
        parts.push('<summary>Full Thinking</summary>');
        parts.push('');
        parts.push(thinking);
        parts.push('');
        parts.push('</details>');
      }
      return parts.join('\n').trim();
    }

    if (blockType === 'tool_use') {
      return this._renderToolUseBlock(block);
    }

    if (blockType === 'tool_result') {
      const resultText = this._extractToolResultText(block);
      if (!resultText) {
        return '';
      }
      const label = block.name ? `Result from ${block.name}` : 'Tool Result';
      return `> ${label}: ${resultText}`;
    }

    if (typeof block.text === 'string') {
      return this._normalizeMessageContent(block.text);
    }

    return '';
  }

  _renderToolUseBlock(block) {
    const name = block.name || 'tool';
    const input = block.input && typeof block.input === 'object' ? block.input : {};

    if (name === 'artifacts') {
      const title = this._normalizeMessageContent(input.title || 'Untitled Artifact');
      const type = this._normalizeMessageContent(input.type || '');
      const content = this._normalizeMessageContent(input.content || '');
      const lines = [`### Artifact: ${title}`];
      if (type) {
        lines.push(`Type: ${type}`);
      }
      if (content) {
        lines.push('');
        lines.push(content);
      }
      return lines.join('\n').trim();
    }

    const serializedInput = JSON.stringify(input, null, 2) || '{}';
    const trimmedInput = serializedInput.length > 1200
      ? `${serializedInput.slice(0, 1200)}\n... (truncated)`
      : serializedInput;
    return `Tool: ${name}\n\`\`\`json\n${trimmedInput}\n\`\`\``;
  }

  _extractToolResultText(block) {
    const content = Array.isArray(block.content) ? block.content : [];
    const text = content
      .map(item => {
        if (!item || typeof item !== 'object') {
          return '';
        }
        if (item.type === 'text') {
          return item.text || '';
        }
        return '';
      })
      .filter(Boolean)
      .join('\n');

    return this._normalizeMessageContent(text);
  }

  _renderStructuredAttachments(message) {
    const parts = [];

    if (Array.isArray(message.attachments) && message.attachments.length > 0) {
      parts.push(`Attachments: ${message.attachments.map(item => String(item)).join(', ')}`);
    }

    if (Array.isArray(message.files) && message.files.length > 0) {
      parts.push(`Files: ${message.files.map(item => this._stringifyFileLike(item)).join(', ')}`);
    }

    return parts.join('\n');
  }

  _stringifyFileLike(fileLike) {
    if (!fileLike || typeof fileLike !== 'object') {
      return String(fileLike);
    }
    return fileLike.file_name || fileLike.name || JSON.stringify(fileLike);
  }

  _pickStructuredTitle(node) {
    const candidates = [
      node.name,
      node.title,
      node.project,
      node.chat_name
    ];

    for (const candidate of candidates) {
      const cleaned = this._cleanTitleCandidate(candidate);
      if (cleaned) {
        return cleaned;
      }
    }

    return '';
  }

  _dedupeMessages(messages) {
    const deduped = [];

    for (const message of messages) {
      const content = this._normalizeMessageContent(message.content);
      if (!content) {
        continue;
      }

      const previous = deduped[deduped.length - 1];
      if (previous && previous.role === message.role && previous.content === content) {
        continue;
      }

      deduped.push({
        role: message.role,
        content
      });
    }

    return deduped;
  }

  _normalizeMessageContent(content) {
    if (!content) {
      return '';
    }

    const normalizedLines = content
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean);

    const uniqueLines = [];
    for (const line of normalizedLines) {
      if (uniqueLines[uniqueLines.length - 1] !== line) {
        uniqueLines.push(line);
      }
    }

    return uniqueLines.join('\n').trim();
  }

  _normalizeSummaryText(content) {
    if (!content) {
      return '';
    }

    const normalized = String(content)
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();

    return normalized;
  }

  _normalizeAssistantDomContent(content) {
    if (!content) {
      return '';
    }

    const text = content
      .replace(/思考过程/g, 'Thinking')
      .replace(/思考摘要/g, 'Thought Summary')
      .replace(/展开完整思考过程/g, 'Full Thinking')
      .replace(/\n{3,}/g, '\n\n');

    return this._normalizeMessageContent(text);
  }

  _extractContext() {
    const match = window.location.pathname.match(/\/chat\/([a-zA-Z0-9-]+)/);
    const titleCandidates = [
      document.querySelector('main h1')?.textContent,
      document.querySelector('[data-testid*="chat-title"]')?.textContent,
      document.querySelector('[aria-current="page"]')?.textContent,
      document.querySelector('meta[property="og:title"]')?.getAttribute('content'),
      document.title
    ];

    let title = 'Claude Conversation';
    for (const candidate of titleCandidates) {
      const cleaned = this._cleanTitleCandidate(candidate);
      if (cleaned) {
        title = cleaned;
        break;
      }
    }

    return {
      title,
      conversationId: match ? match[1] : null
    };
  }

  _cleanTitleCandidate(value) {
    const cleaned = String(value || '')
      .replace(/\s*-\s*Claude.*$/, '')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleaned) {
      return '';
    }

    const lowered = cleaned.toLowerCase();
    if (lowered === 'claude' || lowered === 'new chat') {
      return '';
    }

    return cleaned;
  }
}

if (typeof module !== 'undefined') module.exports = { ClaudeExtractor };
