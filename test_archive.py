#!/usr/bin/env python3
"""
归档功能测试脚本
演示智能归档功能的工作原理
"""

import os
import shutil
import json
from spotify import (
    create_archive_directory_structure,
    migrate_existing_archive_files,
    get_archive_statistics,
    extract_year_from_timestamp
)

def test_archive_functionality():
    """测试归档功能"""
    print("🧪 测试归档功能")
    print("=" * 50)
    
    # 1. 测试时间戳解析
    print("\n1. 测试时间戳解析功能：")
    test_timestamps = [
        "20250630_134002",
        "20240315_091530",
        "20230101_000000",
        "invalid_timestamp"
    ]
    
    for ts in test_timestamps:
        year = extract_year_from_timestamp(ts)
        print(f"   时间戳: {ts} → 年份: {year}")
    
    # 2. 创建测试归档目录结构
    print("\n2. 创建归档目录结构：")
    archive_dir = "archive"
    
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
        print(f"   ✅ 创建归档目录: {archive_dir}")
    
    # 创建年份子目录
    for timestamp in ["20250630_134002", "20240315_091530"]:
        year_dir = create_archive_directory_structure(archive_dir, timestamp)
        print(f"   ✅ 创建年份目录: {year_dir}")
    
    # 3. 模拟创建一些归档文件
    print("\n3. 创建测试归档文件：")
    
    # 在 2025 目录创建文件
    test_file_2025 = os.path.join(archive_dir, "2025", "spotify_prices_all_countries_20250630_134002.json")
    test_data = {"test": "data", "year": 2025}
    
    with open(test_file_2025, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 创建测试文件: {test_file_2025}")
    
    # 在 2024 目录创建文件
    test_file_2024 = os.path.join(archive_dir, "2024", "spotify_prices_all_countries_20240315_091530.json")
    test_data = {"test": "data", "year": 2024}
    
    with open(test_file_2024, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 创建测试文件: {test_file_2024}")
    
    # 4. 测试归档统计功能
    print("\n4. 归档统计信息：")
    stats = get_archive_statistics(archive_dir)
    print(f"   📊 总文件数: {stats['total_files']}")
    print(f"   📊 年份数量: {len(stats['years'])}")
    
    for year, data in sorted(stats['years'].items(), reverse=True):
        print(f"   📁 {year}: {data['count']} 个文件")
        for file_path, mtime, filename in data['files'][:3]:  # 只显示前3个
            print(f"      - {filename}")
    
    # 5. 测试迁移功能（创建一些根目录文件然后迁移）
    print("\n5. 测试文件迁移功能：")
    
    # 在根目录创建一个测试文件
    root_test_file = os.path.join(archive_dir, "spotify_prices_all_countries_20230101_000000.json")
    test_data = {"test": "migration", "year": 2023}
    
    with open(root_test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 创建待迁移文件: {root_test_file}")
    
    # 执行迁移
    print("\n   开始执行迁移...")
    migrate_existing_archive_files(archive_dir)
    
    # 检查迁移后的统计
    print("\n6. 迁移后的统计信息：")
    stats = get_archive_statistics(archive_dir)
    print(f"   📊 总文件数: {stats['total_files']}")
    print(f"   📊 年份数量: {len(stats['years'])}")
    
    for year, data in sorted(stats['years'].items(), reverse=True):
        print(f"   📁 {year}: {data['count']} 个文件")
    
    print("\n✅ 归档功能测试完成！")
    print("\n💡 归档功能说明：")
    print("   - 所有历史数据文件会自动按年份组织在 archive/ 目录下")
    print("   - 每次运行爬虫时会自动创建对应年份的子目录")
    print("   - 现有的归档文件会自动迁移到正确的年份目录")
    print("   - 最新的数据会同时保存为带时间戳的归档版本和latest版本")

if __name__ == "__main__":
    test_archive_functionality()
