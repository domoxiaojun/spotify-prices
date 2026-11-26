#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spotify价格变化检测器
检测最新价格与上次价格的变化，生成changelog
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import glob

class PriceChangeDetector:
    def __init__(self):
        self.current_file = "spotify_prices_cny_sorted.json"
        self.changelog_file = "CHANGELOG.md"
        
    def find_latest_archive_file(self) -> Optional[str]:
        """查找最新的归档价格文件"""
        # 查找archive目录下的所有cny_sorted文件
        pattern = "archive/**/spotify_prices_cny_sorted_*.json"
        archive_files = glob.glob(pattern, recursive=True)
        
        if not archive_files:
            print("没有找到历史归档文件")
            return None
            
        # 按文件名中的时间戳排序，获取最新的
        archive_files.sort(key=lambda x: os.path.basename(x))
        latest_file = archive_files[-1]
        print(f"找到最新归档文件: {latest_file}")
        return latest_file
    
    def load_price_data(self, file_path: str) -> Dict:
        """加载价格数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"文件不存在: {file_path}")
            return {}
        except json.JSONDecodeError:
            print(f"JSON格式错误: {file_path}")
            return {}
    
    def compare_prices(self, old_data: Dict, new_data: Dict) -> List[Dict]:
        """对比价格变化"""
        changes = []
        
        def indexed(data):
            prices = {}
            for country, entry in data.items():
                for plan in entry.get("plans", []):
                    name, cny = plan.get("plan"), plan.get("price_cny")
                    if not name or not isinstance(cny, (int, float)) or not (0 < cny < float("inf")):
                        continue
                    prices.setdefault((country, name), {
                        "country": country, "plan": name, "price_cny": cny,
                        "price_original": plan.get("price", "N/A"),
                        "price_number": plan.get("price_number"),
                        "currency": plan.get("currency", "N/A"),
                    })
            return prices

        old_prices = indexed(old_data)
        new_prices = indexed(new_data)

        # 对比价格变化
        for key, new_price in new_prices.items():
            if key in old_prices:
                old_price = old_prices[key]
                if new_price['currency'] != old_price['currency']:
                    continue  # Do not label unlike currencies an increase/decrease.
                try:
                    old_local = float(str(old_price['price_number']).replace(',', ''))
                    new_local = float(str(new_price['price_number']).replace(',', ''))
                except (TypeError, ValueError):
                    continue
                if old_local > 0 and new_local > 0 and abs(old_local - new_local) > 1e-8:
                    new_cny = float(new_price['price_cny'])
                    old_cny = round(new_cny * old_local / new_local, 2)
                    change_amount = round(new_cny - old_cny, 2)
                    change_percent = (new_local / old_local - 1) * 100

                    changes.append({
                        'country': new_price['country'],
                        'plan': new_price['plan'],
                        'old_price_cny': old_cny,
                        'new_price_cny': new_cny,
                        'change_amount': change_amount,
                        'change_percent': change_percent,
                        'price_original': new_price['price_original'],
                        'currency': new_price['currency'],
                        'type': 'price_change'
                    })
            else:
                # 本次新增观测的套餐
                changes.append({
                    'country': new_price['country'],
                    'plan': new_price['plan'],
                    'new_price_cny': float(new_price['price_cny']),
                    'price_original': new_price['price_original'],
                    'currency': new_price['currency'],
                    'type': 'new_plan'
                })
        
        # 检查本次未抓到的套餐
        for key, old_price in old_prices.items():
            if key not in new_prices:
                changes.append({
                    'country': old_price['country'],
                    'plan': old_price['plan'],
                    'old_price_cny': float(old_price['price_cny']),
                    'price_original': old_price['price_original'],
                    'currency': old_price['currency'],
                    'type': 'removed_plan'
                })
        
        return changes
    
    def generate_changelog_content(self, changes: List[Dict], date: str) -> str:
        """生成changelog内容"""
        if not changes:
            return f"## {date}\n\n✅ **无价格变化** - 所有套餐价格保持稳定\n\n"
        
        content = f"## {date}\n\n"
        
        # 统计变化
        price_increases = [c for c in changes if c['type'] == 'price_change' and c['change_amount'] > 0]
        price_decreases = [c for c in changes if c['type'] == 'price_change' and c['change_amount'] < 0]
        new_plans = [c for c in changes if c['type'] == 'new_plan']
        removed_plans = [c for c in changes if c['type'] == 'removed_plan']
        
        content += f"📊 **变化概览**: {len(changes)} 项变化\n"
        if price_increases:
            content += f"- 📈 涨价: {len(price_increases)} 个套餐\n"
        if price_decreases:
            content += f"- 📉 降价: {len(price_decreases)} 个套餐\n"
        if new_plans:
            content += f"- 🆕 本次新增观测: {len(new_plans)} 个套餐\n"
        if removed_plans:
            content += f"- ❌ 本次未抓到: {len(removed_plans)} 个套餐\n"
        content += "\n"
        
        # 涨价详情
        if price_increases:
            content += "### 📈 价格上涨\n\n"
            price_increases.sort(key=lambda x: x['change_percent'], reverse=True)
            for change in price_increases:
                content += f"- **{change['country']} - {change['plan']}**\n"
                content += f"  - 原价: ¥{change['old_price_cny']:.2f} | 现价: ¥{change['new_price_cny']:.2f}\n"
                content += f"  - 涨幅: ¥{change['change_amount']:.2f} (+{change['change_percent']:.1f}%)\n"
                content += f"  - 当地价格: {change['price_original']} {change['currency']}\n\n"
        
        # 降价详情
        if price_decreases:
            content += "### 📉 价格下降\n\n"
            price_decreases.sort(key=lambda x: x['change_percent'])
            for change in price_decreases:
                content += f"- **{change['country']} - {change['plan']}**\n"
                content += f"  - 原价: ¥{change['old_price_cny']:.2f} | 现价: ¥{change['new_price_cny']:.2f}\n"
                content += f"  - 降幅: ¥{abs(change['change_amount']):.2f} ({change['change_percent']:.1f}%)\n"
                content += f"  - 当地价格: {change['price_original']} {change['currency']}\n\n"
        
        # 新增套餐
        if new_plans:
            content += "### 🆕 新增套餐\n\n"
            for change in new_plans:
                content += f"- **{change['country']} - {change['plan']}**\n"
                content += f"  - 价格: ¥{change['new_price_cny']:.2f}\n"
                content += f"  - 当地价格: {change['price_original']} {change['currency']}\n\n"
        
        # 移除套餐
        if removed_plans:
            content += "### ❌ 移除套餐\n\n"
            for change in removed_plans:
                content += f"- **{change['country']} - {change['plan']}**\n"
                content += f"  - 原价格: ¥{change['old_price_cny']:.2f}\n"
                content += f"  - 当地价格: {change['price_original']} {change['currency']}\n\n"
        
        return content
    
    def update_changelog(self, new_content: str):
        """更新changelog文件"""
        if not os.path.exists(self.changelog_file):
            # 如果文件不存在，创建初始模板
            initial_content = """# Spotify 价格变化记录

此文件记录 Spotify 各国套餐价格的变化历史。

> 📊 **说明**：价格变化自动检测功能已启用，每次爬虫运行后都会对比上次的价格数据，生成详细的变化报告。

## 📁 历史归档

| 年月 | 归档文件 | 变化次数 |
|------|----------|----------|
| - | 暂无归档 | - |

---

## 📅 当前月份记录

### """ + datetime.now().strftime('%Y年%m月') + """

"""
            with open(self.changelog_file, 'w', encoding='utf-8') as f:
                f.write(initial_content + new_content + "\n")
            print(f"✅ 创建新的 Changelog: {self.changelog_file}")
            return
        
        # 读取现有内容
        with open(self.changelog_file, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        
        # 查找当前月份记录的位置
        current_month = datetime.now().strftime('%Y年%m月')
        month_header_pattern = f"### {current_month}"
        
        if month_header_pattern in existing_content:
            # 在当前月份标题后插入新内容
            parts = existing_content.split(month_header_pattern, 1)
            if len(parts) == 2:
                # 查找下一个月份标题或文件结束
                after_header = parts[1]
                next_month_match = re.search(r'\n### \d{4}年\d{2}月', after_header)
                
                if next_month_match:
                    # 在下一个月份标题前插入
                    insert_pos = next_month_match.start()
                    before_next = after_header[:insert_pos]
                    after_next = after_header[insert_pos:]
                    updated_content = parts[0] + month_header_pattern + "\n\n" + new_content + before_next + after_next
                else:
                    # 在文件末尾插入
                    # 清理现有的"暂无记录"文本
                    cleaned_after = re.sub(r'\n\*本月暂无价格变化记录\*\s*', '\n', after_header)
                    updated_content = parts[0] + month_header_pattern + "\n\n" + new_content + cleaned_after
            else:
                updated_content = existing_content + "\n" + new_content
        else:
            # 添加新月份标题和内容
            updated_content = existing_content + f"\n### {current_month}\n\n" + new_content
        
        with open(self.changelog_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"✅ Changelog已更新: {self.changelog_file}")
    
    def generate_summary_json(self, changes: List[Dict], date: str):
        """生成变化摘要JSON文件"""
        summary = {
            'date': date,
            'timestamp': datetime.now().isoformat(),
            'total_changes': len(changes),
            'price_increases': len([c for c in changes if c['type'] == 'price_change' and c['change_amount'] > 0]),
            'price_decreases': len([c for c in changes if c['type'] == 'price_change' and c['change_amount'] < 0]),
            'new_plans': len([c for c in changes if c['type'] == 'new_plan']),
            'removed_plans': len([c for c in changes if c['type'] == 'removed_plan']),
            'changes': changes
        }
        
        summary_file = f"price_changes_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 变化摘要已生成: {summary_file}")
        return summary_file
    
    def detect_and_report_changes(self) -> Tuple[int, str]:
        """主函数：检测价格变化并生成报告"""
        print("🔍 开始检测价格变化...")
        
        # 检查当前价格文件是否存在
        if not os.path.exists(self.current_file):
            print(f"❌ 当前价格文件不存在: {self.current_file}")
            return 0, ""
        
        # 查找最新的归档文件
        latest_archive = os.environ.get("SPOTIFY_PREVIOUS_EXPORT") or self.find_latest_archive_file()
        if not latest_archive:
            print("⚠️ 没有历史数据，跳过价格对比")
            # 即使没有历史数据，也生成一个空的摘要文件
            date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            summary = {
                'date': date,
                'timestamp': datetime.now().isoformat(),
                'total_changes': 0,
                'price_increases': 0,
                'price_decreases': 0,
                'new_plans': 0,
                'removed_plans': 0,
                'changes': [],
                'note': '首次运行或无历史数据，跳过价格对比'
            }
            summary_file = f"price_changes_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"✅ 生成初始摘要文件: {summary_file}")
            return 0, summary_file
        
        # 加载数据
        old_data = self.load_price_data(latest_archive)
        new_data = self.load_price_data(self.current_file)
        
        if not old_data or not new_data:
            raise ValueError("Unable to load the prior or candidate Spotify export")
        
        # 对比价格
        changes = self.compare_prices(old_data, new_data)
        
        # 生成报告
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        changelog_content = self.generate_changelog_content(changes, date)
        
        # 更新changelog
        self.update_changelog(changelog_content)
        
        # 生成摘要JSON
        summary_file = self.generate_summary_json(changes, date)
        
        print(f"✅ 价格变化检测完成，发现 {len(changes)} 项变化")
        return len(changes), summary_file


if __name__ == "__main__":
    detector = PriceChangeDetector()
    changes_count, summary_file = detector.detect_and_report_changes()
    
    # 检查是否需要执行 CHANGELOG 归档
    from datetime import datetime
    now = datetime.now()
    if now.day <= 3:  # 每月前3天检查归档
        print("\n🗂️ 检查 CHANGELOG 归档需求...")
        try:
            import subprocess
            result = subprocess.run(['python', 'changelog_archiver.py'], 
                                  capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0:
                print("✅ CHANGELOG 归档检查完成")
                if result.stdout:
                    print(result.stdout)
            else:
                print(f"⚠️ CHANGELOG 归档失败: {result.stderr}")
        except Exception as e:
            print(f"⚠️ 执行 CHANGELOG 归档时出错: {e}")
    
    # 输出结果供GitHub Actions使用
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output and github_output != '/dev/stdout':
        with open(github_output, 'a') as f:
            f.write(f"changes_count={changes_count}\n")
            f.write(f"summary_file={summary_file}\n")
    else:
        # 如果不在 GitHub Actions 环境中，输出到标准输出
        print(f"changes_count={changes_count}")
        print(f"summary_file={summary_file}")
