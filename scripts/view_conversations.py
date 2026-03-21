#!/usr/bin/env python3
"""
Claude Memory System - View Conversations
查看同步到数据库的对话内容
"""

import sqlite3
import sys
from datetime import datetime

DB_PATH = "D:\\python project\\claude-memory-system\\backend\\data\\memory.db"

def view_conversations(limit=10, platform=None):
    """查看对话列表"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT id, platform, summary, importance,
               datetime(timestamp) as time,
               substr(full_content, 1, 100) as preview
        FROM conversations
    """

    params = []
    if platform:
        query += " WHERE platform = ?"
        params.append(platform)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    conversations = cursor.fetchall()

    if not conversations:
        print("📭 没有找到对话记录")
        return

    print(f"\n{'='*80}")
    print(f"📚 最近的 {len(conversations)} 条对话")
    print(f"{'='*80}\n")

    for i, conv in enumerate(conversations, 1):
        print(f"[{i}] ID: {conv['id'][:8]}...")
        print(f"    平台: {conv['platform']}")
        print(f"    时间: {conv['time']}")
        print(f"    摘要: {conv['summary']}")
        print(f"    重要性: {conv['importance']}/10")
        print(f"    预览: {conv['preview']}...")
        print()

    conn.close()

    # 提示用户可以查看详情
    print("💡 查看完整对话内容，请运行：")
    print(f"   python view_conversations.py <conversation_id>")
    print()

def view_conversation_detail(conversation_id):
    """查看单个对话的完整内容"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 支持部分ID匹配
    cursor.execute("""
        SELECT id, platform, summary, importance,
               datetime(timestamp) as time, full_content
        FROM conversations
        WHERE id LIKE ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (f"{conversation_id}%",))

    conv = cursor.fetchone()

    if not conv:
        print(f"❌ 未找到ID为 {conversation_id} 的对话")
        conn.close()
        return

    print(f"\n{'='*80}")
    print(f"📄 对话详情")
    print(f"{'='*80}\n")
    print(f"ID: {conv['id']}")
    print(f"平台: {conv['platform']}")
    print(f"时间: {conv['time']}")
    print(f"摘要: {conv['summary']}")
    print(f"重要性: {conv['importance']}/10")
    print(f"\n{'='*80}")
    print(f"完整内容:")
    print(f"{'='*80}\n")
    print(conv['full_content'])
    print(f"\n{'='*80}\n")

    conn.close()

def search_conversations(keyword):
    """搜索对话"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, platform, summary, importance,
               datetime(timestamp) as time
        FROM conversations
        WHERE full_content LIKE ? OR summary LIKE ?
        ORDER BY timestamp DESC
    """, (f"%{keyword}%", f"%{keyword}%"))

    results = cursor.fetchall()

    if not results:
        print(f"📭 没有找到包含 '{keyword}' 的对话")
        conn.close()
        return

    print(f"\n{'='*80}")
    print(f"🔍 搜索结果: '{keyword}' ({len(results)} 条)")
    print(f"{'='*80}\n")

    for i, conv in enumerate(results, 1):
        print(f"[{i}] ID: {conv['id'][:8]}...")
        print(f"    平台: {conv['platform']}")
        print(f"    时间: {conv['time']}")
        print(f"    摘要: {conv['summary']}")
        print()

    conn.close()

def show_stats():
    """显示统计信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 总数
    cursor.execute("SELECT COUNT(*) FROM conversations")
    total = cursor.fetchone()[0]

    # 按平台统计
    cursor.execute("""
        SELECT platform, COUNT(*) as count, AVG(importance) as avg_importance
        FROM conversations
        GROUP BY platform
    """)
    by_platform = cursor.fetchall()

    # 最新和最旧
    cursor.execute("""
        SELECT MIN(datetime(timestamp)) as oldest, MAX(datetime(timestamp)) as newest
        FROM conversations
    """)
    time_range = cursor.fetchone()

    print(f"\n{'='*80}")
    print(f"📊 数据库统计")
    print(f"{'='*80}\n")
    print(f"总对话数: {total}")
    print(f"时间范围: {time_range[0]} 到 {time_range[1]}")
    print(f"\n按平台统计:")
    for platform, count, avg_imp in by_platform:
        print(f"  - {platform}: {count} 条 (平均重要性: {avg_imp:.1f}/10)")
    print()

    conn.close()

def main():
    if len(sys.argv) == 1:
        # 默认显示最近10条
        view_conversations(10)
        show_stats()
    elif sys.argv[1] == '--stats':
        show_stats()
    elif sys.argv[1] == '--search':
        if len(sys.argv) < 3:
            print("用法: python view_conversations.py --search <关键词>")
            return
        search_conversations(sys.argv[2])
    elif sys.argv[1] == '--all':
        view_conversations(100)
    elif sys.argv[1] == '--platform':
        if len(sys.argv) < 3:
            print("用法: python view_conversations.py --platform <平台名>")
            return
        view_conversations(50, sys.argv[2])
    else:
        # 查看详情
        view_conversation_detail(sys.argv[1])

if __name__ == "__main__":
    main()
