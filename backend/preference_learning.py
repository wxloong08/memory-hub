"""
Claude Memory System - Preference Learning
偏好学习：自动提取和学习用户偏好
"""

import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
import re

class PreferenceLearning:
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

    def extract_preferences_from_conversations(self) -> List[Dict]:
        """从对话中提取偏好"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, full_content, datetime(timestamp) as time
            FROM conversations
            ORDER BY timestamp DESC
            LIMIT 50
        """)

        conversations = [dict(row) for row in cursor.fetchall()]

        # Also query V2 archive_conversations if table exists
        if self._has_table(conn, 'archive_conversations'):
            cursor.execute("""
                SELECT id, datetime(started_at) as time
                FROM archive_conversations
                ORDER BY started_at DESC
                LIMIT 50
            """)
            for row in cursor.fetchall():
                v2_conv = dict(row)
                v2_conv['full_content'] = self._reconstruct_full_content(conn, v2_conv['id'])
                conversations.append(v2_conv)

        conn.close()

        preferences = []

        # 偏好关键词模式
        preference_patterns = [
            (r'我喜欢|我偏好|我倾向于', 'preference'),
            (r'我不喜欢|我不想|避免', 'dislike'),
            (r'我总是|我通常|我习惯', 'habit'),
            (r'最好|应该|建议', 'recommendation'),
        ]

        for conv in conversations:
            content = conv.get('full_content', '') or ''
            if not content:
                continue

            for pattern, pref_type in preference_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # 提取偏好语句（前后50个字符）
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 100)
                    statement = content[start:end].strip()

                    preferences.append({
                        'type': pref_type,
                        'statement': statement,
                        'conversation_id': conv['id'],
                        'timestamp': conv['time']
                    })

        return preferences

    def categorize_preferences(self, preferences: List[Dict]) -> Dict:
        """分类偏好"""
        categories = {
            'code_style': [],
            'framework': [],
            'workflow': [],
            'general': []
        }

        # 关键词映射
        category_keywords = {
            'code_style': ['代码', '风格', '格式', '命名', '注释', 'code', 'style'],
            'framework': ['框架', '库', '工具', 'framework', 'library', 'tool'],
            'workflow': ['流程', '工作', '习惯', 'workflow', 'process', 'habit'],
        }

        for pref in preferences:
            statement = pref['statement'].lower()
            categorized = False

            for category, keywords in category_keywords.items():
                if any(keyword in statement for keyword in keywords):
                    categories[category].append(pref)
                    categorized = True
                    break

            if not categorized:
                categories['general'].append(pref)

        return categories

    def save_preferences(self, preferences: List[Dict]):
        """保存偏好到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        preference_columns = {row[1] for row in conn.execute("PRAGMA table_info(preferences)").fetchall()}
        has_priority = "priority" in preference_columns
        has_client_rules = "client_rules" in preference_columns
        has_status = "status" in preference_columns
        seen: set[tuple] = set()

        for pref in preferences:
            # 确定分类
            statement = pref['statement'].lower()
            if any(kw in statement for kw in ['代码', 'code', '风格', 'style']):
                category = 'code_style'
            elif any(kw in statement for kw in ['框架', 'framework', '库', 'library']):
                category = 'framework'
            elif any(kw in statement for kw in ['流程', 'workflow', '习惯', 'habit']):
                category = 'workflow'
            else:
                category = 'general'

            key = pref['type']
            value = pref['statement'][:200]
            confidence = 0.7
            priority = 0
            client_rules = "{}"
            status = "active"
            dedupe_key = (category, key, value)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            where_clauses = [
                "COALESCE(category, '') = COALESCE(?, '')",
                "COALESCE(key, '') = COALESCE(?, '')",
                "COALESCE(value, '') = COALESCE(?, '')",
            ]
            where_params: list = [category, key, value]

            existing = cursor.execute(
                f"SELECT id FROM preferences WHERE {' AND '.join(where_clauses)} LIMIT 1",
                tuple(where_params),
            ).fetchone()
            if existing:
                continue

            if has_priority and has_client_rules and has_status:
                cursor.execute(
                    """
                    INSERT INTO preferences
                    (category, key, value, confidence, priority, client_rules, status, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        category,
                        key,
                        value,
                        confidence,
                        priority,
                        client_rules,
                        status,
                        datetime.now().isoformat(),
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO preferences
                    (category, key, value, confidence, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        category,
                        key,
                        value,
                        confidence,
                        datetime.now().isoformat(),
                    ),
                )

        conn.commit()
        conn.close()

    def get_user_profile(self) -> Dict:
        """获取用户画像"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 获取所有偏好
        cursor.execute("""
            SELECT category, key, value, confidence, datetime(last_updated) as updated
            FROM preferences
            ORDER BY confidence DESC, last_updated DESC
        """)

        preferences = [dict(row) for row in cursor.fetchall()]

        # 获取对话统计 (V1 + V2 if available)
        has_v2 = self._has_table(conn, 'archive_conversations')
        if has_v2:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_conversations,
                    COUNT(DISTINCT platform) as platforms_used,
                    AVG(importance) as avg_importance,
                    MIN(ts) as first_conversation,
                    MAX(ts) as last_conversation
                FROM (
                    SELECT platform, importance, datetime(timestamp) as ts FROM conversations
                    UNION ALL
                    SELECT platform, importance, datetime(started_at) as ts FROM archive_conversations
                )
            """)
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_conversations,
                    COUNT(DISTINCT platform) as platforms_used,
                    AVG(importance) as avg_importance,
                    MIN(datetime(timestamp)) as first_conversation,
                    MAX(datetime(timestamp)) as last_conversation
                FROM conversations
            """)

        stats = dict(cursor.fetchone())

        # 获取常用平台 (V1 + V2 if available)
        if has_v2:
            cursor.execute("""
                SELECT platform, COUNT(*) as count
                FROM (
                    SELECT platform FROM conversations
                    UNION ALL
                    SELECT platform FROM archive_conversations
                )
                GROUP BY platform
                ORDER BY count DESC
            """)
        else:
            cursor.execute("""
                SELECT platform, COUNT(*) as count
                FROM conversations
                GROUP BY platform
                ORDER BY count DESC
            """)

        platforms = [dict(row) for row in cursor.fetchall()]

        conn.close()

        # 构建用户画像
        profile = {
            "statistics": stats,
            "platforms": platforms,
            "preferences": {
                "code_style": [p for p in preferences if p['category'] == 'code_style'],
                "framework": [p for p in preferences if p['category'] == 'framework'],
                "workflow": [p for p in preferences if p['category'] == 'workflow'],
                "general": [p for p in preferences if p['category'] == 'general']
            },
            "generated_at": datetime.now().isoformat()
        }

        return profile

    def learn_preferences(self) -> Dict:
        """执行偏好学习"""
        print("🎓 开始偏好学习...")

        # 1. 从对话中提取偏好
        preferences = self.extract_preferences_from_conversations()
        print(f"📊 提取到 {len(preferences)} 个偏好语句")

        # 2. 分类偏好
        categorized = self.categorize_preferences(preferences)
        print(f"📂 偏好分类完成:")
        for category, prefs in categorized.items():
            print(f"   - {category}: {len(prefs)} 个")

        # 3. 保存偏好
        if preferences:
            self.save_preferences(preferences)
            print(f"💾 偏好已保存到数据库")

        # 4. 生成用户画像
        profile = self.get_user_profile()
        print(f"👤 用户画像生成完成")

        return {
            "extracted_preferences": len(preferences),
            "categorized_preferences": {k: len(v) for k, v in categorized.items()},
            "user_profile": profile
        }

if __name__ == "__main__":
    # 测试代码
    learning = PreferenceLearning("data/memory.db")

    # 执行偏好学习
    result = learning.learn_preferences()

    print("\n" + "="*60)
    print("偏好学习结果:")
    print("="*60)
    print(f"提取偏好: {result['extracted_preferences']} 个")
    print(f"分类统计: {result['categorized_preferences']}")
    print("="*60)
