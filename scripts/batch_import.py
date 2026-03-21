#!/usr/bin/env python3
"""
Claude Memory System - Batch Import Tool
批量导入 Claude.ai 导出的对话历史
"""

import json
import requests
from datetime import datetime
from pathlib import Path
import sys

MEMORY_HUB_URL = "http://localhost:8765"

def import_claude_export(export_file: str):
    """
    导入 Claude.ai 官方导出的 JSON 文件

    如果 Claude.ai 提供导出功能，格式可能是：
    {
      "conversations": [
        {
          "id": "...",
          "created_at": "...",
          "messages": [...]
        }
      ]
    }
    """
    path = Path(export_file)

    if not path.exists():
        print(f"❌ 文件不存在: {export_file}")
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 尝试不同的格式
        conversations = []

        if isinstance(data, list):
            # 直接是对话列表
            conversations = data
        elif 'conversations' in data:
            # 包含 conversations 字段
            conversations = data['conversations']
        elif 'messages' in data:
            # 单个对话
            conversations = [data]
        else:
            print("❌ 无法识别的 JSON 格式")
            return

        print(f"📦 找到 {len(conversations)} 个对话")

        success_count = 0
        for i, conv in enumerate(conversations, 1):
            print(f"\n处理对话 {i}/{len(conversations)}...")

            messages = conv.get('messages', [])
            if not messages:
                print("  ⚠️  跳过（无消息）")
                continue

            # 发送到 Memory Hub
            payload = {
                "platform": "claude_web_import",
                "timestamp": conv.get('created_at', datetime.now().isoformat()),
                "messages": messages,
                "project": conv.get('title') or conv.get('name')
            }

            try:
                response = requests.post(
                    f"{MEMORY_HUB_URL}/api/conversations",
                    json=payload,
                    timeout=10
                )

                if response.ok:
                    result = response.json()
                    print(f"  ✅ 成功导入 {len(messages)} 条消息")
                    success_count += 1
                else:
                    print(f"  ❌ 失败: {response.status_code}")

            except Exception as e:
                print(f"  ❌ 错误: {e}")

        print(f"\n{'='*60}")
        print(f"✅ 成功导入 {success_count}/{len(conversations)} 个对话")

    except json.JSONDecodeError:
        print("❌ JSON 格式错误")
    except Exception as e:
        print(f"❌ 错误: {e}")

def import_from_directory(directory: str):
    """
    从目录批量导入
    支持 .txt, .json, .md 文件
    """
    path = Path(directory)

    if not path.is_dir():
        print(f"❌ 不是有效的目录: {directory}")
        return

    # 查找所有支持的文件
    files = []
    for ext in ['*.txt', '*.json', '*.md']:
        files.extend(path.glob(ext))

    if not files:
        print(f"❌ 目录中没有找到支持的文件 (.txt, .json, .md)")
        return

    print(f"📁 找到 {len(files)} 个文件")

    success_count = 0
    for i, file in enumerate(files, 1):
        print(f"\n处理文件 {i}/{len(files)}: {file.name}")

        try:
            # 使用之前的导入工具
            from import_conversations import import_from_file
            if import_from_file(str(file)):
                success_count += 1
        except Exception as e:
            print(f"  ❌ 错误: {e}")

    print(f"\n{'='*60}")
    print(f"✅ 成功导入 {success_count}/{len(files)} 个文件")

def create_import_template():
    """创建导入模板文件"""
    template = {
        "messages": [
            {
                "role": "user",
                "content": "你的问题内容"
            },
            {
                "role": "assistant",
                "content": "Claude 的回复内容"
            }
        ],
        "project": "项目名称（可选）",
        "timestamp": datetime.now().isoformat()
    }

    template_path = Path("conversation_template.json")
    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    print(f"✅ 已创建模板文件: {template_path}")
    print("\n使用方法：")
    print("1. 编辑 conversation_template.json")
    print("2. 填入你的对话内容")
    print("3. 运行: python batch_import.py conversation_template.json")

def main():
    if len(sys.argv) < 2:
        print("=" * 60)
        print("Claude Memory System - 批量导入工具")
        print("=" * 60)
        print("\n使用方法：")
        print("  python batch_import.py <文件或目录>")
        print("  python batch_import.py --template  # 创建模板")
        print("\n示例：")
        print("  python batch_import.py conversations.json")
        print("  python batch_import.py ./my_conversations/")
        print()
        return

    arg = sys.argv[1]

    if arg == '--template':
        create_import_template()
        return

    path = Path(arg)

    if path.is_file():
        if path.suffix == '.json':
            import_claude_export(str(path))
        else:
            from import_conversations import import_from_file
            import_from_file(str(path))
    elif path.is_dir():
        import_from_directory(str(path))
    else:
        print(f"❌ 无效的路径: {arg}")

if __name__ == "__main__":
    main()
