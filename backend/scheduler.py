"""
Claude Memory System - Scheduler
定时任务调度器：自动执行记忆巩固和偏好学习
"""

import schedule
import time
from datetime import datetime
from memory_consolidation import MemoryConsolidation
from preference_learning import PreferenceLearning
import json
import os

class MemoryScheduler:
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self.consolidation = MemoryConsolidation(db_path)
        self.learning = PreferenceLearning(db_path)
        self.log_file = "data/scheduler.log"

    def log(self, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        print(log_message)

        # 写入日志文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

    def daily_consolidation_job(self):
        """每日记忆巩固任务"""
        self.log("🧠 开始执行每日记忆巩固...")

        try:
            result = self.consolidation.consolidate_memories()
            self.log(f"✅ 记忆巩固完成: {result['recent_conversations']} 条对话")
        except Exception as e:
            self.log(f"❌ 记忆巩固失败: {e}")

    def weekly_preference_learning_job(self):
        """每周偏好学习任务"""
        self.log("🎓 开始执行每周偏好学习...")

        try:
            result = self.learning.learn_preferences()
            self.log(f"✅ 偏好学习完成: {result['extracted_preferences']} 个偏好")
        except Exception as e:
            self.log(f"❌ 偏好学习失败: {e}")

    def hourly_memory_decay_job(self):
        """每小时记忆衰减任务"""
        self.log("⏳ 开始执行记忆衰减...")

        try:
            affected = self.consolidation.apply_memory_decay(30)
            if affected > 0:
                self.log(f"✅ 记忆衰减完成: {affected} 条记录")
        except Exception as e:
            self.log(f"❌ 记忆衰减失败: {e}")

    def setup_schedule(self):
        """设置定时任务"""
        # 每天凌晨2点执行记忆巩固
        schedule.every().day.at("02:00").do(self.daily_consolidation_job)

        # 每周日凌晨3点执行偏好学习
        schedule.every().sunday.at("03:00").do(self.weekly_preference_learning_job)

        # 每小时执行记忆衰减
        schedule.every().hour.do(self.hourly_memory_decay_job)

        self.log("📅 定时任务已设置:")
        self.log("   - 每日记忆巩固: 每天 02:00")
        self.log("   - 每周偏好学习: 每周日 03:00")
        self.log("   - 每小时记忆衰减: 每小时")

    def run(self):
        """运行调度器"""
        self.log("🚀 Memory Scheduler 启动")
        self.setup_schedule()

        # 立即执行一次（测试）
        self.log("🧪 执行初始化任务...")
        self.daily_consolidation_job()

        # 持续运行
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    scheduler = MemoryScheduler("data/memory.db")
    scheduler.run()
