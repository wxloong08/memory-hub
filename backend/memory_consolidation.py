"""
Claude Memory System - Memory Consolidation
记忆巩固：模拟人类睡眠时的记忆整理过程
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

class MemoryConsolidation:
    def __init__(self, db_path: str = "data/memory.db", db_v2=None):
        self.db_path = db_path
        self.db_v2 = db_v2

    def _has_table(self, conn, table_name: str) -> bool:
        """Check if a table exists in the database."""
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def _reconstruct_full_content(self, conn, conversation_id: str) -> str:
        """Reconstruct full_content from archive_messages for a V2 conversation."""
        if self.db_v2 is not None:
            return self.db_v2.reconstruct_full_content(conversation_id)
        cursor = conn.execute(
            "SELECT role, content FROM archive_messages WHERE conversation_id = ? ORDER BY ordinal",
            (conversation_id,),
        )
        return "\n\n".join(f"{r['role']}: {r['content']}" for r in [dict(row) for row in cursor.fetchall()])

    def get_recent_conversations(self, hours: int = 24) -> List[Dict]:
        """获取最近的对话"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, platform, summary, full_content, importance,
                   datetime(timestamp) as time
            FROM conversations
            WHERE datetime(timestamp) > datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp DESC
        """, (hours,))

        conversations = [dict(row) for row in cursor.fetchall()]

        # Also query V2 archive_conversations if table exists
        if self._has_table(conn, 'archive_conversations'):
            cursor.execute("""
                SELECT id, platform, summary, importance,
                       datetime(started_at) as time
                FROM archive_conversations
                WHERE datetime(started_at) > datetime('now', '-' || ? || ' hours')
                ORDER BY started_at DESC
            """, (hours,))
            for row in cursor.fetchall():
                v2_conv = dict(row)
                v2_conv['full_content'] = self._reconstruct_full_content(conn, v2_conv['id'])
                conversations.append(v2_conv)

        conn.close()

        return conversations

    def extract_key_information(self, conversations: List[Dict]) -> Dict:
        """提取关键信息"""
        key_info = {
            "total_conversations": len(conversations),
            "platforms": {},
            "topics": [],
            "important_conversations": [],
            "avg_importance": 0
        }

        if not conversations:
            return key_info

        # 统计平台
        for conv in conversations:
            platform = conv['platform']
            key_info['platforms'][platform] = key_info['platforms'].get(platform, 0) + 1

        # 提取重要对话（importance >= 7）
        important = [c for c in conversations if c['importance'] >= 7]
        key_info['important_conversations'] = [
            {
                "id": c['id'],
                "summary": c['summary'],
                "importance": c['importance'],
                "time": c['time']
            }
            for c in important
        ]

        # 计算平均重要性
        if conversations:
            key_info['avg_importance'] = sum(c['importance'] for c in conversations) / len(conversations)

        return key_info

    def generate_daily_summary(self, date: Optional[str] = None) -> Dict:
        """生成每日摘要"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # 获取当天的对话
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, platform, summary, importance,
                   datetime(timestamp) as time
            FROM conversations
            WHERE date(timestamp) = ?
            ORDER BY importance DESC, timestamp DESC
        """, (date,))

        conversations = [dict(row) for row in cursor.fetchall()]

        # Also query V2 archive_conversations if table exists
        if self._has_table(conn, 'archive_conversations'):
            cursor.execute("""
                SELECT id, platform, summary, importance,
                       datetime(started_at) as time
                FROM archive_conversations
                WHERE date(started_at) = ?
                ORDER BY importance DESC, started_at DESC
            """, (date,))
            conversations.extend([dict(row) for row in cursor.fetchall()])

        conn.close()

        if not conversations:
            return {
                "date": date,
                "summary": "No conversations on this day",
                "conversations": []
            }

        # 生成摘要
        summary = {
            "date": date,
            "total_conversations": len(conversations),
            "platforms": {},
            "top_conversations": [],
            "avg_importance": 0
        }

        # 统计平台
        for conv in conversations:
            platform = conv['platform']
            summary['platforms'][platform] = summary['platforms'].get(platform, 0) + 1

        # 前5个重要对话
        summary['top_conversations'] = [
            {
                "id": c['id'],
                "summary": c['summary'],
                "importance": c['importance'],
                "time": c['time']
            }
            for c in conversations[:5]
        ]

        # 平均重要性
        summary['avg_importance'] = sum(c['importance'] for c in conversations) / len(conversations)

        return summary

    def apply_memory_decay(self, days_threshold: int = 30):
        """应用记忆衰减（遗忘曲线）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 计算衰减后的重要性
        # 使用 Ebbinghaus 遗忘曲线：retention = e^(-days/7)
        # 重要性高的记忆衰减更慢（除以30而不是7）
        cursor.execute("""
            UPDATE conversations
            SET importance = CAST(
                importance *
                CASE
                    WHEN importance >= 8 THEN exp(-(julianday('now') - julianday(timestamp)) / 30.0)
                    ELSE exp(-(julianday('now') - julianday(timestamp)) / 7.0)
                END
                AS INTEGER
            )
            WHERE julianday('now') - julianday(timestamp) > ?
            AND importance > 1
        """, (days_threshold,))

        affected_rows = cursor.rowcount

        # Also apply decay to V2 archive_conversations if table exists
        if self._has_table(conn, 'archive_conversations'):
            cursor.execute("""
                UPDATE archive_conversations
                SET importance = CAST(
                    importance *
                    CASE
                        WHEN importance >= 8 THEN exp(-(julianday('now') - julianday(started_at)) / 30.0)
                        ELSE exp(-(julianday('now') - julianday(started_at)) / 7.0)
                    END
                    AS INTEGER
                )
                WHERE julianday('now') - julianday(started_at) > ?
                AND importance > 1
            """, (days_threshold,))
            affected_rows += cursor.rowcount

        conn.commit()
        conn.close()

        return affected_rows

    def consolidate_memories(self) -> Dict:
        """执行记忆巩固"""
        print("🧠 开始记忆巩固...")

        # 1. 获取最近24小时的对话
        recent_conversations = self.get_recent_conversations(24)
        print(f"📊 找到 {len(recent_conversations)} 条最近对话")

        # 2. 提取关键信息
        key_info = self.extract_key_information(recent_conversations)
        print(f"💡 提取关键信息完成")

        # 3. 生成每日摘要
        daily_summary = self.generate_daily_summary()
        print(f"📝 生成每日摘要完成")

        # 4. 应用记忆衰减
        decayed_count = self.apply_memory_decay(30)
        print(f"⏳ 应用记忆衰减：{decayed_count} 条记录受影响")

        # 5. 保存巩固结果
        result = {
            "timestamp": datetime.now().isoformat(),
            "recent_conversations": len(recent_conversations),
            "key_information": key_info,
            "daily_summary": daily_summary,
            "memory_decay_applied": decayed_count
        }

        # 保存到文件
        consolidation_file = f"data/consolidation_{datetime.now().strftime('%Y%m%d')}.json"
        with open(consolidation_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"✅ 记忆巩固完成，结果保存到: {consolidation_file}")

        return result

if __name__ == "__main__":
    # 测试代码
    consolidation = MemoryConsolidation("data/memory.db")

    # 执行记忆巩固
    result = consolidation.consolidate_memories()

    print("\n" + "="*60)
    print("记忆巩固结果:")
    print("="*60)
    print(f"最近对话数: {result['recent_conversations']}")
    print(f"每日摘要: {result['daily_summary']['total_conversations']} 条对话")
    print(f"记忆衰减: {result['memory_decay_applied']} 条记录")
    print("="*60)
