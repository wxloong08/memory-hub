#!/usr/bin/env python3
"""
Claude Memory System - Manual Import Tool
手动导入历史对话到 Memory Hub
"""

import sys
import json
import requests
from datetime import datetime
from pathlib import Path

MEMORY_HUB_URL = "http://localhost:8765"

def import_from_text(text_content: str, platform: str = "claude_web"):
    """
    从纯文本导入对话
    格式：
    User: 消息内容
    Assistant: 回复内容
    """
    messages = []
    lines = text_content.strip().split('\n')

    current_role = None
    current_content = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检测角色标记
        if line.lower().startswith('user:') or line.lower().startswith('你:'):
            # 保存上一条消息
            if current_role and current_content:
                messages.append({
                    'role': current_role,
                    'content': '\n'.join(current_content).strip()
                })
            current_role = 'user'
            current_content = [line.split(':', 1)[1].strip()]
        elif line.lower().startswith('assistant:') or line.lower().startswith('claude:'):
            # 保存上一条消息
            if current_role and current_content:
                messages.append({
                    'role': current_role,
                    'content': '\n'.join(current_content).strip()
                })
            current_role = 'assistant'
            current_content = [line.split(':', 1)[1].strip()]
        else:
            # 继续当前消息
            if current_role:
                current_content.append(line)

    # 保存最后一条消息
    if current_role and current_content:
        messages.append({
            'role': current_role,
            'content': '\n'.join(current_content).strip()
        })

    return messages

def import_from_json(json_content: str):
    """
    从 JSON 格式导入对话
    格式：
    {
      "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
      ]
    }
    """
    data = json.loads(json_content)
    return data.get('messages', [])

def send_to_memory_hub(messages: list, platform: str = "manual_import",
                       project: str = None, working_dir: str = None):
    """发送到 Memory Hub"""

    if not messages:
        print("❌ 没有找到有效的消息")
        return False

    payload = {
        "platform": platform,
        "timestamp": datetime.now().isoformat(),
        "messages": messages,
        "project": project,
        "working_dir": working_dir
    }

    try:
        response = requests.post(
            f"{MEMORY_HUB_URL}/api/conversations",
            json=payload,
            timeout=10
        )

        if response.ok:
            result = response.json()
            print(f"✅ 成功导入 {len(messages)} 条消息")
            print(f"   对话ID: {result['conversation_id']}")
            return True
        else:
            print(f"❌ 导入失败: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 Memory Hub")
        print("   请确保 Memory Hub 正在运行: uvicorn main:app --port 8765")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def import_from_file(file_path: str):
    """从文件导入"""
    path = Path(file_path)

    if not path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False

    content = path.read_text(encoding='utf-8')

    # 尝试 JSON 格式
    if file_path.endswith('.json'):
        try:
            messages = import_from_json(content)
            print(f"📄 从 JSON 文件解析到 {len(messages)} 条消息")
        except json.JSONDecodeError:
            print("❌ JSON 格式错误")
            return False
    else:
        # 纯文本格式
        messages = import_from_text(content)
        print(f"📄 从文本文件解析到 {len(messages)} 条消息")

    # 发送到 Memory Hub
    return send_to_memory_hub(messages, project=path.stem)

def interactive_import():
    """交互式导入"""
    print("=" * 60)
    print("Claude Memory System - 手动导入工具")
    print("=" * 60)
    print()
    print("请选择导入方式：")
    print("1. 从文件导入 (支持 .txt 和 .json)")
    print("2. 直接粘贴文本")
    print("3. 退出")
    print()

    choice = input("请选择 (1-3): ").strip()

    if choice == '1':
        file_path = input("请输入文件路径: ").strip()
        import_from_file(file_path)

    elif choice == '2':
        print()
        print("请粘贴对话内容（格式：User: ... / Assistant: ...）")
        print("输入完成后，单独一行输入 'END' 结束：")
        print()

        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)

        content = '\n'.join(lines)
        messages = import_from_text(content)

        if messages:
            print(f"\n📝 解析到 {len(messages)} 条消息")
            print("\n预览：")
            for i, msg in enumerate(messages[:3], 1):
                preview = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
                print(f"  {i}. [{msg['role']}] {preview}")

            if len(messages) > 3:
                print(f"  ... 还有 {len(messages) - 3} 条消息")

            confirm = input("\n确认导入？(y/n): ").strip().lower()
            if confirm == 'y':
                send_to_memory_hub(messages)
        else:
            print("❌ 未能解析出有效消息")

    elif choice == '3':
        print("👋 再见！")
        return

    else:
        print("❌ 无效选择")

def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 命令行模式
        file_path = sys.argv[1]
        import_from_file(file_path)
    else:
        # 交互模式
        interactive_import()

if __name__ == "__main__":
    main()
