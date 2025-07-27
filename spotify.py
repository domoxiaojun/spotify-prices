#!/usr/bin/env python3
"""
Spotify Premium Family 各国价格爬取脚本（Playwright版本）
使用 Playwright 自动化浏览器顺序获取各国 Spotify 订阅价格
优化的URL切换和重试机制，确保高成功率
参考 spotify.py 和 disney.py 的结构化解析方式
"""

import re
import asyncio
import json
import os
import shutil
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright, Browser, Page
import time
import random

def extract_year_from_timestamp(timestamp: str) -> str:
    """从时间戳中提取年份"""
    try:
        # 时间戳格式: YYYYMMDD_HHMMSS
        if len(timestamp) >= 4:
            return timestamp[:4]
        else:
            # 如果解析失败，返回当前年份
            return time.strftime('%Y')
    except:
        return time.strftime('%Y')

def create_archive_directory_structure(archive_dir: str, timestamp: str) -> str:
    """根据时间戳创建按年份组织的归档目录结构"""
    year = extract_year_from_timestamp(timestamp)
    year_dir = os.path.join(archive_dir, year)
    if not os.path.exists(year_dir):
        os.makedirs(year_dir)
        print(f"📁 创建年份目录: {year_dir}")
    return year_dir

def migrate_existing_archive_files(archive_dir: str):
    """将现有的归档文件迁移到按年份组织的目录结构中"""
    if not os.path.exists(archive_dir):
        return
    
    migrated_count = 0
    
    # 查找根目录下的归档文件
    for filename in os.listdir(archive_dir):
        if filename.startswith('spotify_prices_all_countries_') and filename.endswith('.json'):
            file_path = os.path.join(archive_dir, filename)
            
            # 确保是文件而不是目录
            if os.path.isfile(file_path):
                # 从文件名提取时间戳
                try:
                    # 文件名格式: spotify_prices_all_countries_YYYYMMDD_HHMMSS.json
                    timestamp_part = filename.replace('spotify_prices_all_countries_', '').replace('.json', '')
                    year = extract_year_from_timestamp(timestamp_part)
                    
                    # 创建年份目录
                    year_dir = create_archive_directory_structure(archive_dir, timestamp_part)
                    
                    # 移动文件
                    new_path = os.path.join(year_dir, filename)
                    if not os.path.exists(new_path):  # 避免重复移动
                        shutil.move(file_path, new_path)
                        print(f"📦 迁移文件: {filename} → {year}/")
                        migrated_count += 1
                except Exception as e:
                    print(f"⚠️  迁移文件失败 {filename}: {e}")
    
    if migrated_count > 0:
        print(f"✅ 成功迁移 {migrated_count} 个归档文件到年份目录")
    else:
        print("📂 没有需要迁移的归档文件")

def get_archive_statistics(archive_dir: str) -> dict:
    """获取归档文件统计信息"""
    if not os.path.exists(archive_dir):
        return {"total_files": 0, "years": {}}
    
    stats = {"total_files": 0, "years": {}}
    
    # 遍历所有年份目录
    for item in os.listdir(archive_dir):
        item_path = os.path.join(archive_dir, item)
        if os.path.isdir(item_path) and item.isdigit() and len(item) == 4:
            year = item
            year_files = []
            
            # 统计该年份的文件
            for filename in os.listdir(item_path):
                if filename.startswith('spotify_prices_all_countries_') and filename.endswith('.json'):
                    filepath = os.path.join(item_path, filename)
                    mtime = os.path.getmtime(filepath)
                    year_files.append((filepath, mtime, filename))
            
            # 按时间排序
            year_files.sort(key=lambda x: x[1], reverse=True)
            stats["years"][year] = {
                "count": len(year_files),
                "files": year_files
            }
            stats["total_files"] += len(year_files)
    
    return stats

def extract_price_number(price_str: str) -> float:
    """从价格字符串中提取数值"""
    if not price_str:
        return 0.0
    
    # 首先尝试提取货币符号后面的数字部分
    # 匹配货币符号(如USD, $, €等)后跟数字的模式
    currency_pattern = r'([$]|US[$]|CA[$]|A[$]|S[$]|HK[$]|MX[$]|NZ[$]|NT[$]|R[$]|C[$]|USD|EUR|GBP|CAD|AUD|SGD|HKD|MXN|BRL|JPY|CNY|KRW|INR|THB|MYR|IDR|PHP|VND|TWD|CHF|SEK|NOK|DKK|PLN|CZK|HUF|RON|BGN|HRK|RSD|BAM|MKD|ALL|MDL|UAH|BYN|RUB|GEL|AMD|AZN|KGS|KZT|UZS|TJS|TMT|AFN|PKR|LKR|BDT|BTN|NPR|MVR|IRR|IQD|JOD|KWD|BHD|QAR|SAR|AED|OMR|YER|EGP|LBP|SYP|TND|DZD|MAD|LYD|SDG|SOS|ETB|ERN|DJF|KMF|SCR|MUR|MGA|MWK|ZMW|BWP|SZL|LSL|ZAR|NAD|AOA|XAF|XOF|XPF|NZD|FJD|TOP|WST|VUV|SBD|PGK|NCF|TVD|KID|MHD|PWD|FMD|GHS|NGN|LRD|SLL|GMD|GNF|CIV|BFA|MLI|NER|TCD|CMR|GAB|GNQ|COG|CAF|TZS|KES|UGX|RWF|BIF|MZN|ZWL|€|£|¥|￥|₹|₱|₪|₨|₦|₵|₡|₩|₴|₽|₺|zł|Kč|Ft|kr)\s+([\d,\.]+)'
    
    currency_match = re.search(currency_pattern, price_str, re.IGNORECASE)
    if currency_match:
        number_part = currency_match.group(2)
    else:
        # 如果没找到货币符号，尝试提取纯数字部分
        # 查找数字、逗号、点的连续组合
        number_pattern = r'([\d,\.]+)'
        number_matches = re.findall(number_pattern, price_str)
        
        if number_matches:
            # 找到最长的数字串（通常是价格）
            number_part = max(number_matches, key=len)
        else:
            return 0.0

    # 如果没有数字，返回0                                                                              
    if not re.search(r'\d', number_part):                                                                  
        return 0.0 
    
    # 处理不同的数字格式
    cleaned = number_part
    if ',' in cleaned and '.' in cleaned:
        # 判断是欧式格式还是美式格式
        comma_pos = cleaned.rindex(',')
        dot_pos = cleaned.rindex('.')
        if comma_pos > dot_pos:
            # 欧式格式 (1.234,56) - 点是千位分隔符，逗号是小数点
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            # 美式格式 (1,234.56) - 逗号是千位分隔符，点是小数点
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        # 只有逗号的情况
        parts = cleaned.split(',')
        if len(parts) == 2:
            # 检查小数部分长度来判断是小数点还是千位分隔符
            decimal_part = parts[-1]
            if len(decimal_part) <= 2:
                # 小数部分是1-2位数，很可能是小数点 (例如: 5,99)
                cleaned = cleaned.replace(',', '.')
            else:
                # 小数部分超过2位，很可能是千位分隔符 (例如: 2,499)
                cleaned = cleaned.replace(',', '')
        else:
            # 多个逗号，都是千位分隔符
            cleaned = cleaned.replace(',', '')
    elif '.' in cleaned:
        # 只有点的情况
        parts = cleaned.split('.')
        if len(parts) == 2:
            # 检查小数部分长度
            decimal_part = parts[-1]
            if len(decimal_part) <= 2:
                # 小数部分是1-2位数，保持为小数点 (例如: 5.99)
                pass  # 保持不变
            else:
                # 小数部分超过2位，很可能是千位分隔符 (例如: 2.499)
                cleaned = cleaned.replace('.', '')
        else:
            # 多个点，都是千位分隔符
            cleaned = cleaned.replace('.', '')
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def detect_currency(price_str: str, country_code: str = None) -> str:
    """检测价格字符串中的货币"""

    # 1. 优先使用静态映射表
    if country_code and country_code in SPOTIFY_REAL_CURRENCY_MAP:
        expected_currency = SPOTIFY_REAL_CURRENCY_MAP[country_code]["currency"]
        print(f"    💱 {country_code}: 使用映射表货币 {expected_currency}")
        return expected_currency
    
    currency_symbols = {
        # 优先检查带前缀的美元符号
        'US$': 'USD', 'USD': 'USD',
        # 其他特殊美元符号
        'C$': 'CAD', 'CA$': 'CAD', 'A$': 'AUD', 'S$': 'SGD', 'HK$': 'HKD',
        'MX$': 'MXN', 'NZ$': 'NZD', 'NT$': 'TWD',
        # 其他货币符号
        'R$': 'BRL', '€': 'EUR', '£': 'GBP', '¥': 'JPY', '￥': 'JPY',
        '₹': 'INR', '₱': 'PHP', '₪': 'ILS', '₨': 'PKR',
        '₦': 'NGN', '₵': 'GHS', '₡': 'CRC',
        '₩': 'KRW', '₴': 'UAH', '₽': 'RUB',
        '₺': 'TRY', 'zł': 'PLN', 'Kč': 'CZK', 'Ft': 'HUF',
        'CHF': 'CHF', 'NOK': 'NOK', 'SEK': 'SEK', 'DKK': 'DKK',
        'SGD': 'SGD', 'MYR': 'MYR', 'THB': 'THB', 'IDR': 'IDR', 
        'PKR': 'PKR', 'LKR': 'LKR', 'BDT': 'BDT', 'NGN': 'NGN', 
        'GHS': 'GHS', 'KES': 'KES', 'TZS': 'TZS', 'UGX': 'UGX', 
        'ZAR': 'ZAR', 'EGP': 'EGP', 'SAR': 'SAR', 'AED': 'AED', 
        'QAR': 'QAR', 'IQD': 'IQD', 'COP': 'COP', 'TRY': 'TRY', 
        'RON': 'RON', 'BGN': 'BGN', 'kr': 'SEK',
        # 最后检查通用美元符号
        '$': 'USD'
    }
    
    # 按符号长度从长到短排序，优先匹配更具体的符号
    sorted_symbols = sorted(currency_symbols.items(), key=lambda x: len(x[0]), reverse=True)
    
    for symbol, currency in sorted_symbols:
        if symbol in price_str:
            return currency
    
    # 默认返回美元
    return 'USD'

# 基于 Spotify 实际显示货币的静态映射表
SPOTIFY_REAL_CURRENCY_MAP = {
    "AE": {"currency": "AED", "symbol": "AED"},  # United Arab Emirates
    "AG": {"currency": "USD", "symbol": "US$"},  # Antigua and Barbuda
    "AL": {"currency": "EUR", "symbol": "€"},  # Albania
    "AM": {"currency": "USD", "symbol": "US$"},  # Armenia
    "AR": {"currency": "ARS", "symbol": "$"},  # Argentina
    "AO": {"currency": "USD", "symbol": "US$"},  # Angola
    "AT": {"currency": "EUR", "symbol": "€"},  # Austria
    "AU": {"currency": "AUD", "symbol": "A$"},  # Australia
    "AZ": {"currency": "USD", "symbol": "US$"},  # Azerbaijan
    "BA": {"currency": "EUR", "symbol": "€"},  # Bosnia and Herzegovina
    "BB": {"currency": "USD", "symbol": "US$"},  # Barbados
    "BD": {"currency": "BDT", "symbol": "BDT"},  # Bangladesh
    "BE": {"currency": "EUR", "symbol": "€"},  # Belgium
    "BF": {"currency": "USD", "symbol": "US$"},  # Burkina Faso
    "BG": {"currency": "BGN", "symbol": "BGN"},  # Bulgaria
    "BH": {"currency": "USD", "symbol": "US$"},  # Bahrain
    "BI": {"currency": "USD", "symbol": "US$"},  # Burundi
    "BJ": {"currency": "USD", "symbol": "US$"},  # Benin
    "BN": {"currency": "USD", "symbol": "US$"},  # Brunei Darussalam
    "BR": {"currency": "BRL", "symbol": "R$"},  # Brazil
    "BS": {"currency": "USD", "symbol": "US$"},  # The Bahamas
    "BT": {"currency": "USD", "symbol": "US$"},  # Bhutan
    "BW": {"currency": "USD", "symbol": "US$"},  # Botswana
    "BY": {"currency": "USD", "symbol": "US$"},  # Belarus
    "BZ": {"currency": "USD", "symbol": "US$"},  # Belize
    "CA": {"currency": "CAD", "symbol": "CA$"},  # Canada
    "CH": {"currency": "CHF", "symbol": "CHF"},  # Switzerland
    "CI": {"currency": "USD", "symbol": "US$"},  # Côte d'Ivoire
    "CL": {"currency": "CLP", "symbol": "CLP"},  # Chile
    "CM": {"currency": "USD", "symbol": "US$"},  # Cameroon
    "CO": {"currency": "COP", "symbol": "COP"},  # Colombia
    "CV": {"currency": "USD", "symbol": "US$"},  # Cabo Verde
    "CW": {"currency": "USD", "symbol": "US$"},  # Curacao
    "CY": {"currency": "EUR", "symbol": "€"},  # Cyprus
    "CZ": {"currency": "CZK", "symbol": "Kč"},  # Czech Republic
    "DE": {"currency": "EUR", "symbol": "€"},  # Germany
    "DJ": {"currency": "USD", "symbol": "US$"},  # Djibouti
    "DK": {"currency": "DKK", "symbol": "DKK"},  # Denmark
    "DM": {"currency": "USD", "symbol": "US$"},  # Dominica
    "EE": {"currency": "EUR", "symbol": "€"},  # Estonia
    "EG": {"currency": "EGP", "symbol": "EGP"},  # Egypt
    "ET": {"currency": "USD", "symbol": "US$"},  # Ethiopia
    "FJ": {"currency": "USD", "symbol": "US$"},  # Fiji
    "FM": {"currency": "USD", "symbol": "US$"},  # Micronesia
    "GA": {"currency": "USD", "symbol": "US$"},  # Gabon
    "GB": {"currency": "GBP", "symbol": "£"},  # United Kingdom
    "GD": {"currency": "USD", "symbol": "US$"},  # Grenada
    "GE": {"currency": "USD", "symbol": "US$"},  # Georgia
    "GH": {"currency": "GHS", "symbol": "GHS"},  # Ghana
    "GM": {"currency": "USD", "symbol": "US$"},  # The Gambia
    "GN": {"currency": "USD", "symbol": "US$"},  # Guinea
    "GQ": {"currency": "USD", "symbol": "US$"},  # Equatorial Guinea
    "GR": {"currency": "EUR", "symbol": "€"},  # Greece
    "GW": {"currency": "USD", "symbol": "US$"},  # Guinea-Bissau
    "GY": {"currency": "USD", "symbol": "US$"},  # Guyana
    "HK": {"currency": "HKD", "symbol": "HK$"},  # Hong Kong
    "HR": {"currency": "EUR", "symbol": "€"},  # Croatia
    "HT": {"currency": "USD", "symbol": "US$"},  # Haiti
    "ID": {"currency": "IDR", "symbol": "IDR"},  # Indonesia
    "IE": {"currency": "EUR", "symbol": "€"},  # Ireland
    "IL": {"currency": "ILS", "symbol": "₪"},  # Israel
    "IN": {"currency": "INR", "symbol": "₹"},  # India
    "IQ": {"currency": "IQD", "symbol": "IQD"},  # Iraq
    "IS": {"currency": "EUR", "symbol": "€"},  # Iceland
    "IT": {"currency": "EUR", "symbol": "€"},  # Italy
    "JM": {"currency": "USD", "symbol": "US$"},  # Jamaica
    "JO": {"currency": "USD", "symbol": "US$"},  # Jordan
    "JP": {"currency": "JPY", "symbol": "￥"},  # Japan
    "KE": {"currency": "KES", "symbol": "KES"},  # Kenya
    "KG": {"currency": "USD", "symbol": "US$"},  # Kyrgyz Republic
    "KH": {"currency": "USD", "symbol": "US$"},  # Cambodia
    "KI": {"currency": "AUD", "symbol": "A$"},  # Kiribati
    "KM": {"currency": "USD", "symbol": "US$"},  # Comoros
    "KN": {"currency": "USD", "symbol": "US$"},  # St. Kitts and Nevis
    "KW": {"currency": "USD", "symbol": "US$"},  # Kuwait
    "KZ": {"currency": "USD", "symbol": "US$"},  # Kazakhstan
    "LA": {"currency": "USD", "symbol": "US$"},  # Laos
    "LB": {"currency": "USD", "symbol": "US$"},  # Lebanon
    "LC": {"currency": "USD", "symbol": "US$"},  # St. Lucia
    "LI": {"currency": "CHF", "symbol": "CHF"},  # Liechtenstein
    "LK": {"currency": "LKR", "symbol": "LKR"},  # Sri Lanka
    "LR": {"currency": "USD", "symbol": "US$"},  # Liberia
    "LS": {"currency": "USD", "symbol": "US$"},  # Lesotho
    "LT": {"currency": "EUR", "symbol": "€"},  # Lithuania
    "LV": {"currency": "EUR", "symbol": "€"},  # Latvia
    "MA": {"currency": "MAD", "symbol": "MAD"},  # Morocco
    "MD": {"currency": "USD", "symbol": "US$"},  # Moldova
    "ME": {"currency": "EUR", "symbol": "€"},  # Montenegro
    "MG": {"currency": "USD", "symbol": "US$"},  # Madagascar
    "MH": {"currency": "USD", "symbol": "$"},  # Marshall Islands
    "MK": {"currency": "EUR", "symbol": "€"},  # North Macedonia
    "ML": {"currency": "USD", "symbol": "US$"},  # Mali
    "MN": {"currency": "USD", "symbol": "US$"},  # Mongolia
    "MO": {"currency": "USD", "symbol": "US$"},  # Macao
    "MR": {"currency": "USD", "symbol": "US$"},  # Mauritania
    "MT": {"currency": "EUR", "symbol": "€"},  # Malta
    "MU": {"currency": "USD", "symbol": "US$"},  # Mauritius
    "MV": {"currency": "USD", "symbol": "US$"},  # Maldives
    "MW": {"currency": "USD", "symbol": "US$"},  # Malawi
    "MX": {"currency": "MXN", "symbol": "MX$"},  # Mexico
    "MY": {"currency": "MYR", "symbol": "MYR"},  # Malaysia
    "MZ": {"currency": "USD", "symbol": "US$"},  # Mozambique
    "NA": {"currency": "USD", "symbol": "US$"},  # Namibia
    "NE": {"currency": "USD", "symbol": "US$"},  # Niger
    "NG": {"currency": "NGN", "symbol": "NGN"},  # Nigeria
    "NL": {"currency": "EUR", "symbol": "€"},  # Netherlands
    "NO": {"currency": "NOK", "symbol": "NOK"},  # Norway
    "NP": {"currency": "USD", "symbol": "US$"},  # Nepal
    "NR": {"currency": "AUD", "symbol": "A$"},  # Nauru
    "NZ": {"currency": "NZD", "symbol": "NZ$"},  # New Zealand
    "OM": {"currency": "USD", "symbol": "US$"},  # Oman
    "PE": {"currency": "PEN", "symbol": "S/"},  # Peru
    "PG": {"currency": "USD", "symbol": "US$"},  # Papua New Guinea
    "PH": {"currency": "PHP", "symbol": "₱"},  # Philippines
    "PK": {"currency": "PKR", "symbol": "PKR"},  # Pakistan
    "PL": {"currency": "PLN", "symbol": "zł"},  # Poland
    "PS": {"currency": "USD", "symbol": "US$"},  # Palestine
    "PT": {"currency": "EUR", "symbol": "€"},  # Portugal
    "PW": {"currency": "USD", "symbol": "US$"},  # Palau
    "QA": {"currency": "QAR", "symbol": "QAR"},  # Qatar
    "RO": {"currency": "RON", "symbol": "RON"},  # Romania
    "RS": {"currency": "EUR", "symbol": "€"},  # Serbia
    "RW": {"currency": "USD", "symbol": "US$"},  # Rwanda
    "SA": {"currency": "SAR", "symbol": "SAR"},  # Saudi Arabia
    "SB": {"currency": "USD", "symbol": "US$"},  # Solomon Islands
    "SC": {"currency": "USD", "symbol": "US$"},  # Seychelles
    "SE": {"currency": "SEK", "symbol": "kr"},  # Sweden
    "SG": {"currency": "SGD", "symbol": "SGD"},  # Singapore
    "SI": {"currency": "EUR", "symbol": "€"},  # Slovenia
    "SK": {"currency": "EUR", "symbol": "€"},  # Slovakia
    "SL": {"currency": "USD", "symbol": "US$"},  # Sierra Leone
    "SM": {"currency": "EUR", "symbol": "€"},  # San Marino
    "SN": {"currency": "USD", "symbol": "US$"},  # Senegal
    "SR": {"currency": "USD", "symbol": "US$"},  # Suriname
    "ST": {"currency": "USD", "symbol": "US$"},  # Sao Tome and Principe
    "SZ": {"currency": "USD", "symbol": "US$"},  # Eswatini
    "TD": {"currency": "USD", "symbol": "US$"},  # Chad
    "TG": {"currency": "USD", "symbol": "US$"},  # Togo
    "TH": {"currency": "THB", "symbol": "THB"},  # Thailand
    "TL": {"currency": "USD", "symbol": "US$"},  # Timor-Leste
    "TN": {"currency": "TND", "symbol": "DT"},  # Tunisia
    "TO": {"currency": "USD", "symbol": "US$"},  # Tonga
    "TR": {"currency": "TRY", "symbol": "TRY"},  # Turkey
    "TT": {"currency": "USD", "symbol": "US$"},  # Trinidad and Tobago
    "TV": {"currency": "AUD", "symbol": "A$"},  # Tuvalu
    "TW": {"currency": "TWD", "symbol": "$"},  # Taiwan
    "TZ": {"currency": "TZS", "symbol": "TZS"},  # Tanzania
    "UA": {"currency": "USD", "symbol": "US$"},  # Ukraine
    "UG": {"currency": "UGX", "symbol": "UGX"},  # Uganda
    "US": {"currency": "USD", "symbol": "$"},  # USA
    "UZ": {"currency": "USD", "symbol": "US$"},  # Uzbekistan
    "VC": {"currency": "USD", "symbol": "US$"},  # St. Vincent and the Grenadines
    "VE": {"currency": "USD", "symbol": "US$"},  # Venezuela
    "VN": {"currency": "VND", "symbol": "₫"},  # Vietnam
    "VU": {"currency": "USD", "symbol": "US$"},  # Vanuatu
    "WS": {"currency": "USD", "symbol": "US$"},  # Samoa
    "XK": {"currency": "EUR", "symbol": "€"},  # Kosovo
    "ZA": {"currency": "ZAR", "symbol": "ZAR"},  # South Africa
    "ZM": {"currency": "USD", "symbol": "US$"},  # Zambia
    "ZW": {"currency": "USD", "symbol": "US$"},  # Zimbabwe
}

# 完整的国家代码列表（按大洲分组）
COUNTRY_CODES = {
    # Africa
    "AO": "Angola", "BJ": "Benin", "BW": "Botswana", "BF": "Burkina Faso", "BI": "Burundi",
    "CV": "Cabo Verde", "CM": "Cameroon", "TD": "Chad", "KM": "Comoros", "CI": "Côte d'Ivoire",
    "CD": "Democratic Republic of the Congo", "DJ": "Djibouti", "EG": "Egypt", "GQ": "Equatorial Guinea",
    "SZ": "Eswatini", "ET": "Ethiopia", "GA": "Gabon", "GM": "The Gambia", "GH": "Ghana",
    "GN": "Guinea", "GW": "Guinea-Bissau", "KE": "Kenya", "LS": "Lesotho", "LR": "Liberia",
    "LY": "Libya", "MG": "Madagascar", "MW": "Malawi", "ML": "Mali", "MR": "Mauritania",
    "MU": "Mauritius", "MA": "Morocco", "MZ": "Mozambique", "NA": "Namibia", "NE": "Niger",
    "NG": "Nigeria", "CG": "Republic of the Congo", "RW": "Rwanda", "ST": "Sao Tome and Principe",
    "SN": "Senegal", "SC": "Seychelles", "SL": "Sierra Leone", "ZA": "South Africa", "TZ": "Tanzania",
    "TG": "Togo", "TN": "Tunisia", "UG": "Uganda", "ZM": "Zambia", "ZW": "Zimbabwe",
    
    # Asia
    "AM": "Armenia", "AZ": "Azerbaijan", "BH": "Bahrain", "BD": "Bangladesh", "BT": "Bhutan",
    "BN": "Brunei Darussalam", "KH": "Cambodia", "CY": "Cyprus", "GE": "Georgia", "HK": "Hong Kong",
    "IN": "India", "ID": "Indonesia", "IQ": "Iraq", "IL": "Israel", "JP": "Japan", "JO": "Jordan",
    "KZ": "Kazakhstan", "KW": "Kuwait", "KG": "Kyrgyz Republic", "LA": "Laos", "LB": "Lebanon",
    "MO": "Macao", "MY": "Malaysia", "MV": "Maldives", "MN": "Mongolia", "NP": "Nepal",
    "OM": "Oman", "PK": "Pakistan", "PS": "Palestine", "PH": "Philippines", "QA": "Qatar",
    "SA": "Saudi Arabia", "SG": "Singapore", "KR": "South Korea", "LK": "Sri Lanka", "TW": "Taiwan",
    "TJ": "Tajikistan", "TH": "Thailand", "TL": "Timor-Leste", "TR": "Turkey", "AE": "United Arab Emirates",
    "UZ": "Uzbekistan", "VN": "Vietnam",
    
    # Europe
    "AL": "Albania", "AD": "Andorra", "AT": "Austria", "BY": "Belarus", "BE": "Belgium",
    "BA": "Bosnia and Herzegovina", "BG": "Bulgaria", "HR": "Croatia", "CZ": "Czech Republic",
    "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France", "DE": "Germany",
    "GR": "Greece", "HU": "Hungary", "IS": "Iceland", "IE": "Ireland", "IT": "Italy",
    "XK": "Kosovo", "LV": "Latvia", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg",
    "MT": "Malta", "MD": "Moldova", "MC": "Monaco", "ME": "Montenegro", "NL": "Netherlands",
    "MK": "North Macedonia", "NO": "Norway", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SM": "San Marino", "RS": "Serbia", "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain",
    "SE": "Sweden", "CH": "Switzerland", "UA": "Ukraine", "GB": "United Kingdom",
    
    # Latin America and the Caribbean
    "AG": "Antigua and Barbuda", "AR": "Argentina", "BS": "The Bahamas", "BB": "Barbados",
    "BZ": "Belize", "BO": "Bolivia", "BR": "Brazil", "CL": "Chile", "CO": "Colombia",
    "CR": "Costa Rica", "CW": "Curacao", "DM": "Dominica", "DO": "Dominican Republic",
    "EC": "Ecuador", "SV": "El Salvador", "GD": "Grenada", "GT": "Guatemala", "GY": "Guyana",
    "HT": "Haiti", "HN": "Honduras", "JM": "Jamaica", "MX": "Mexico", "NI": "Nicaragua",
    "PA": "Panama", "PY": "Paraguay", "PE": "Peru", "KN": "St. Kitts and Nevis",
    "LC": "St. Lucia", "VC": "St. Vincent and the Grenadines", "SR": "Suriname",
    "TT": "Trinidad and Tobago", "UY": "Uruguay", "VE": "Venezuela",
    
    # Northern America
    "CA": "Canada", "US": "USA",
    
    # Oceania
    "AU": "Australia", "FJ": "Fiji", "KI": "Kiribati", "MH": "Marshall Islands",
    "FM": "Micronesia", "NR": "Nauru", "NZ": "New Zealand", "PW": "Palau",
    "PG": "Papua New Guinea", "WS": "Samoa", "SB": "Solomon Islands", "TO": "Tonga",
    "TV": "Tuvalu", "VU": "Vanuatu"
}

def extract_spotify_prices(html: str) -> List[Dict[str, Any]]:
    """从 Spotify 页面 HTML 中提取价格信息，参考 spotify.py 的结构化解析"""
    soup = BeautifulSoup(html, 'html.parser')
    plans = []
    
    try:
        # 首先尝试从 __NEXT_DATA__ 脚本中提取结构化数据（类似 spotify.py）
        json_script = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})
        if json_script:
            try:
                data = json.loads(json_script.get_text())
                # 尝试从结构化数据中提取套餐信息
                structured_plans = (data.get('props', {})
                                  .get('pageProps', {})
                                  .get('components', {})
                                  .get('storefront', {})
                                  .get('plans', []))
                
                if structured_plans:
                    print(f"    📊 找到结构化数据中的 {len(structured_plans)} 个套餐")
                    for plan in structured_plans:
                        plan_header = (plan.get('header') or "未知套餐").strip()
                        primary_price = (plan.get('primaryPriceDescription') or "").strip()
                        secondary_price = (plan.get('secondaryPriceDescription') or "").strip()
                        
                        # 提取所有套餐
                        plan_data = {
                            'plan': plan_header,
                            'primary_price': primary_price,
                            'secondary_price': secondary_price,
                            'source': 'structured_data'
                        }
                        
                        # 确定最终价格显示
                        if secondary_price:
                            plan_data['price'] = secondary_price
                            plan_data['original_price'] = primary_price
                        else:
                            plan_data['price'] = primary_price
                            
                        plans.append(plan_data)
                        print(f"    ✓ 提取套餐: {plan_header} - {plan_data['price']}")
                    
                    if plans:
                        return plans
                        
            except json.JSONDecodeError as e:
                print(f"    ⚠️ JSON 解析失败: {e}")
            except Exception as e:
                print(f"    ⚠️ 结构化数据提取失败: {e}")
        
        # 如果结构化数据失败，回退到 HTML 解析（参考 disney.py 的表格解析方式）
        print("    🔄 回退到 HTML 解析模式")
        
        # 1. 查找价格表格
        price_tables = soup.find_all('table')
        for table in price_tables:
            try:
                if isinstance(table, Tag):  # 确保是 Tag 对象
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # 跳过表头
                        if isinstance(row, Tag):  # 确保是 Tag 对象
                            cols = row.find_all(['td', 'th'])
                            if len(cols) >= 2:
                                plan_text = cols[0].get_text(strip=True)
                                price_text = ' '.join(cols[-1].get_text(separator=' ', strip=True).split())
                                
                                if any(c in price_text for c in '€$£¥₹₱₪₨₦₵₡0123456789'):
                                    plans.append({
                                        'plan': plan_text,
                                        'price': price_text,
                                        'source': 'table_parsing'
                                    })
                                    print(f"    ✓ 表格提取套餐: {plan_text} - {price_text}")
            except Exception as e:
                print(f"    ⚠️ 表格解析错误: {e}")
                continue
        
        # 2. 查找价格卡片/容器（更精确的选择器）
        if not plans:
            price_containers = soup.find_all(['div', 'section', 'article'], 
                                           class_=re.compile(r'plan|price|subscription|premium|family', re.I))
            
            for container in price_containers:
                if isinstance(container, Tag):  # 确保是 Tag 对象
                    container_text = container.get_text(' ', strip=True).lower()
                    
                    # 在此容器内查找价格信息
                    price_elements = container.find_all(['span', 'div', 'p'], 
                                                      class_=re.compile(r'price|cost|amount', re.I))
                    
                    for price_elem in price_elements:
                        if isinstance(price_elem, Tag):  # 确保是 Tag 对象
                            price_text = price_elem.get_text(strip=True)
                            
                            # 验证是否包含价格信息
                            if re.search(r'[€$£¥₹₱₪₨₦₵₡]\s*[\d,.]|\d+[\d,.]*\s*[€$£¥₹₱₪₨₦₵₡]', price_text):
                                # 尝试从附近找到套餐名称
                                plan_name = "Premium Plan"
                                
                                # 查找附近的标题元素
                                for tag in ['h1', 'h2', 'h3', 'h4', 'span']:
                                    nearby = container.find(tag)
                                    if nearby:
                                        nearby_text = nearby.get_text(strip=True)
                                        if any(keyword in nearby_text.lower() for keyword in ['premium', 'family', 'individual', 'student', 'duo']):
                                            plan_name = nearby_text
                                            break
                                
                                plans.append({
                                    'plan': plan_name,
                                    'price': price_text,
                                    'source': 'container_parsing'
                                })
                                print(f"    ✓ 容器提取套餐: {plan_name} - {price_text}")
        
        # 3. 最后的正则表达式匹配（更精确的模式）
        if not plans:
            all_text = soup.get_text()
            
            # 更全面的正则模式，匹配所有套餐类型
            plan_patterns = [
                r'(Premium\s+(?:Family|Individual|Student|Duo)|(?:Family|Individual|Student|Duo)\s+Premium|Premium)\s*[:\-]?\s*([€$£¥₹₱₪₨₦₵₡]\s*[\d,.]+|[\d,.]+\s*[€$£¥₹₱₪₨₦₵₡])',
                r'(Premium\s+(?:Family|Individual|Student|Duo)|(?:Family|Individual|Student|Duo)).*?([€$£¥₹₱₪₨₦₵₡]\s*[\d,.][\d,.\s]*)',
                r'([€$£¥₹₱₪₨₦₵₡]\s*[\d,.][\d,.\s]*)\s*.*?(Premium\s+(?:Family|Individual|Student|Duo)|(?:Family|Individual|Student|Duo))',
                r'([€$£¥₹₱₪₨₦₵₡]\s*[\d,.][\d,.\s]*)\s*/?\s*month'
            ]
            
            for pattern in plan_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    if isinstance(match, tuple):
                        if len(match) == 2:
                            # 判断哪个是套餐名，哪个是价格
                            first, second = match
                            if re.search(r'[€$£¥₹₱₪₨₦₵₡]', first):
                                # 第一个是价格，第二个是套餐名
                                plan_name, price = second, first
                            else:
                                # 第一个是套餐名，第二个是价格
                                plan_name, price = first, second
                                
                            plans.append({
                                'plan': plan_name.strip() if plan_name else 'Premium Plan',
                                'price': price.strip(),
                                'source': 'regex_parsing'
                            })
                        else:
                            plans.append({
                                'plan': 'Premium Plan',
                                'price': match[0].strip(),
                                'source': 'regex_parsing'
                            })
                    else:
                        plans.append({
                            'plan': 'Premium Plan',
                            'price': match.strip(),
                            'source': 'regex_parsing'
                        })
                    
                    print(f"    ✓ 正则提取套餐: {plans[-1]['plan']} - {plans[-1]['price']}")
                    
                if plans:  # 找到就停止
                    break
        
        # 去重和清理
        seen_prices = set()
        clean_plans = []
        for plan in plans:
            price_key = (plan['plan'], plan['price'])
            if price_key not in seen_prices:
                # 清理异常价格（如 $0. 等）
                price = plan['price'].strip()
                if re.search(r'[\d]', price) and not re.match(r'[€$£¥₹₱₪₨₦₵₡]*\s*0[\.,]?\s*[€$£¥₹₱₪₨₦₵₡]*$', price):
                    seen_prices.add(price_key)
                    clean_plans.append(plan)
        
        print(f"    📊 清理后获得 {len(clean_plans)} 个有效套餐")
        return clean_plans
        
    except Exception as e:
        print(f"    ❌ 解析价格时出错: {e}")
        return []

async def get_spotify_prices_for_country(browser: Browser, country_code: str, country_name: str, max_retries: int = 2) -> Optional[Dict[str, Any]]:
    """获取指定国家的 Spotify 价格，支持重试机制（并发优化版）"""
    
    for attempt in range(max_retries):
        page = None
        try:
            page = await browser.new_page()
            
            # 设置用户代理
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            })
            
            # 构建 Spotify URL - 按照要求优先使用 -en 版本
            urls_to_try = [
                f"https://www.spotify.com/{country_code.lower()}-en/premium",  # 优先使用英文版
                f"https://www.spotify.com/{country_code.lower()}/premium",     # 备用本地版
            ]
            
            success = False
            page_content = ""
            successful_url = ""
            
            for url in urls_to_try:
                try:
                    print(f"    🔗 {country_code}: {url}")
                    
                    # 导航到页面 - 并发优化：缩短超时时间
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    
                    # 检查状态码
                    if response:
                        status = response.status
                        print(f"    📊 {country_code}: 状态码 {status}")
                        
                        # 如果是重定向或404，尝试下一个URL
                        if status in [302, 404]:
                            print(f"    ↻ {country_code}: {status} 响应，尝试下一个URL")
                            continue
                        elif status == 429:
                            print(f"    ⚠️  {country_code}: 频率限制 (429)")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(random.uniform(3, 6))  # 减少等待时间
                                break  # 跳出URL循环，重试整个国家
                            else:
                                return None
                        elif status == 200:
                            # 并发优化：减少等待时间，让其他任务有机会执行
                            await page.wait_for_timeout(random.randint(1000, 2000))
                            
                            # 尝试等待价格元素加载 - 减少超时时间
                            try:
                                await page.wait_for_selector('[class*="price"], [class*="plan"], [class*="subscription"]', 
                                                           timeout=5000)
                            except:
                                pass  # 如果找不到这些选择器也继续
                            
                            page_content = await page.content()
                            
                            # 检查页面是否包含价格信息
                            if any(keyword in page_content.lower() for keyword in ['premium', 'family', 'price', 'subscription']):
                                print(f"    ✓ {country_code}: 找到价格信息，开始解析...")
                                
                                # 立即尝试解析价格
                                temp_plans = extract_spotify_prices(page_content)
                                if temp_plans:
                                    print(f"    ✓ {country_code}: 成功解析到 {len(temp_plans)} 个套餐")
                                    success = True
                                    successful_url = url
                                    break
                                else:
                                    print(f"    ↻ {country_code}: 页面有价格关键词但解析失败，尝试下一个URL")
                                    continue
                            else:
                                print(f"    ↻ {country_code}: 页面无价格信息，尝试下一个URL")
                                continue
                        else:
                            # 其他状态码也尝试下一个URL
                            print(f"    ↻ {country_code}: 状态码 {status}，尝试下一个URL")
                            continue
                    else:
                        print(f"    ❌ {country_code}: 无响应，尝试下一个URL")
                        continue
                        
                except Exception as e:
                    print(f"    ❌ {country_code}: 访问 {url} 失败: {e}")
                    continue
            
            # 解析价格 - 只有在成功找到页面内容时才执行
            if success:
                plans = extract_spotify_prices(page_content)
                
                if plans:
                    print(f"    🎯 {country_code}: 最终确认获取到 {len(plans)} 个套餐")
                    
                    # 为每个套餐添加基本信息
                    enhanced_plans = []
                    for plan in plans:
                        enhanced_plan = plan.copy()
                        
                        # 提取价格数值和货币
                        price_str = plan.get('price', '')
                        if price_str:
                            price_number = extract_price_number(price_str)
                            detected_currency = detect_currency(price_str, country_code)
                            
                            enhanced_plan['price_number'] = price_number
                            enhanced_plan['currency'] = detected_currency
                            
                            # 显示检测到的货币信息
                            print(f"    💰 {plan.get('plan', 'Unknown')}: {price_str} ({detected_currency})")
                        
                        enhanced_plans.append(enhanced_plan)
                    
                    return {
                        'country_code': country_code,
                        'country_name': country_name,
                        'plans': enhanced_plans,
                        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'source_url': successful_url,
                        'attempt': attempt + 1
                    }
                else:
                    print(f"    ❌ {country_code}: 最终解析失败，这不应该发生")
                    if attempt < max_retries - 1:
                        print(f"    🔄 {country_code}: 重试整个流程")
                        await asyncio.sleep(random.uniform(0.5, 1.5))  # 减少重试等待时间
                        continue
                    else:
                        return None
            else:
                # 没有成功的URL，进入重试逻辑
                if attempt < max_retries - 1:
                    print(f"    🔄 {country_code}: 所有URL都失败，重试 (尝试 {attempt + 2}/{max_retries})")
                    await asyncio.sleep(random.uniform(1, 2))  # 减少重试等待时间
                    continue
                else:
                    print(f"    ⏹️ {country_code}: 达到最大重试次数，放弃")
                    return None
                
        except Exception as e:
            print(f"    ❌ {country_code}: 获取失败 - {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(random.uniform(1, 2))  # 减少重试等待时间
                continue
            else:
                return None
            
        finally:
            if page:
                await page.close()
    
    return None

async def main():
    """主函数：并发获取各国 Spotify 价格"""
    print("🎵 开始获取 Spotify Premium Family 各国价格...")
    print("🚀 使用并发模式，同时处理多个国家")
    
    results = {}
    failed_countries = []
    
    total_countries = len(COUNTRY_CODES)
    max_concurrent = 5  # 最大并发数，避免过多请求
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(
            headless=True,  # 设置为 False 可以看到浏览器操作
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        try:
            # 创建信号量来限制并发数
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def process_country_with_semaphore(country_code: str, country_name: str, index: int):
                """使用信号量控制并发的国家处理函数"""
                async with semaphore:
                    print(f"\n🌍 开始处理: {index+1}/{total_countries} - {country_code} ({country_name})")
                    
                    # 获取该国家的价格
                    country_data = await get_spotify_prices_for_country(browser, country_code, country_name)
                    
                    if country_data:
                        results[country_code] = country_data
                        print(f"✅ {country_code}: 成功获取 {len(country_data['plans'])} 个套餐")
                        
                        # 显示获取到的套餐简要信息
                        for plan in country_data['plans']:
                            print(f"    📦 {plan.get('plan', 'Unknown')}: {plan.get('price', 'N/A')}")
                        
                        return True, country_code, country_name
                    else:
                        failed_countries.append(f"{country_code} ({country_name})")
                        print(f"❌ {country_code}: 获取失败")
                        return False, country_code, country_name
            
            # 创建所有任务
            tasks = []
            for i, (country_code, country_name) in enumerate(COUNTRY_CODES.items()):
                task = process_country_with_semaphore(country_code, country_name, i)
                tasks.append(task)
            
            # 使用 asyncio.gather 并发执行所有任务
            print(f"🚀 开始并发处理 {total_countries} 个国家（最大并发数: {max_concurrent}）...")
            
            # 可以选择性地分批处理以避免过载
            batch_size = 20  # 每批处理20个国家
            
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i+batch_size]
                batch_start = i + 1
                batch_end = min(i + batch_size, len(tasks))
                
                print(f"\n📦 处理批次 {batch_start}-{batch_end}/{total_countries}")
                
                # 并发执行当前批次
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                
                # 处理批次结果
                for result in batch_results:
                    if isinstance(result, Exception):
                        print(f"❌ 批次中发生异常: {result}")
                    elif isinstance(result, tuple) and len(result) == 3:
                        success, country_code, country_name = result
                        if success:
                            print(f"📊 批次完成: {country_code} ✅")
                        else:
                            print(f"📊 批次完成: {country_code} ❌")
                
                # 批次间添加短暂延迟
                if i + batch_size < len(tasks):
                    delay = random.uniform(2, 5)
                    print(f"⏱️  批次间等待 {delay:.1f} 秒...")
                    await asyncio.sleep(delay)
                
        finally:
            await browser.close()
    
    # 保存结果
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    output_file = f'spotify_prices_all_countries_{timestamp}.json'
    output_file_latest = 'spotify_prices_all_countries.json'
    
    # 确保归档目录结构存在
    archive_dir = 'archive'
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
    
    # 检查并迁移现有的归档文件到年份目录
    migrate_existing_archive_files(archive_dir)
    
    # 根据时间戳创建年份子目录
    year_archive_dir = create_archive_directory_structure(archive_dir, timestamp)
    
    # 保存带时间戳的版本到对应年份归档目录
    archive_file = os.path.join(year_archive_dir, output_file)
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 保存最新版本（供转换器使用）
    with open(output_file_latest, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 获取归档统计信息
    archive_stats = get_archive_statistics(archive_dir)
    
    # 打印统计信息
    print(f"\n" + "="*60)
    print(f"🎉 并发爬取完成！")
    print(f"✅ 成功: {len(results)} 个国家")
    print(f"❌ 失败: {len(failed_countries)} 个国家")
    print(f"📁 历史版本已保存到: {archive_file}")
    print(f"📁 最新版本已保存到: {output_file_latest}")
    print(f"🗂️  归档统计: 共 {archive_stats['total_files']} 个文件，分布在 {len(archive_stats['years'])} 个年份")
    
    # 显示每年的文件数量
    for year_key, year_data in sorted(archive_stats['years'].items(), reverse=True):
        print(f"    {year_key}: {year_data['count']} 个文件")
    
    if failed_countries:
        print(f"\n❌ 失败的国家: {', '.join(failed_countries)}")
    
    return results

if __name__ == '__main__':
    # 运行爬虫
    results = asyncio.run(main())
    
    # 可选：显示一些样本数据
    if results:
        print(f"\n📋 样本数据:")
        for country_code, data in list(results.items())[:3]:
            print(f"\n{country_code} - {data.get('country_name', 'Unknown')}:")
            for plan in data.get('plans', []):
                print(f"  📦 {plan.get('plan', 'Unknown')}: {plan.get('price', 'N/A')}")
                
        # 显示成功率统计
        success_rate = len(results) / len(COUNTRY_CODES) * 100
        total_countries = len(COUNTRY_CODES)
        successful_countries = len(results)
        failed_count = total_countries - successful_countries
        
        print(f"\n📊 统计信息:")
        print(f"  总国家数: {total_countries}")
        print(f"  成功获取: {successful_countries} 个国家")
        print(f"  失败数量: {failed_count} 个国家")
        print(f"  成功率: {success_rate:.1f}%")
        
        # 显示按地区分组的成功情况
        regions = {
            "非洲": ["AO", "BJ", "BW", "BF", "BI", "CV", "CM", "TD", "KM", "CI", "CD", "DJ", "EG", "GQ", "SZ", "ET", "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "CG", "RW", "ST", "SN", "SC", "SL", "ZA", "TZ", "TG", "TN", "UG", "ZM", "ZW"],
            "亚洲": ["AM", "AZ", "BH", "BD", "BT", "BN", "KH", "CY", "GE", "HK", "IN", "ID", "IQ", "IL", "JP", "JO", "KZ", "KW", "KG", "LA", "LB", "MO", "MY", "MV", "MN", "NP", "OM", "PK", "PS", "PH", "QA", "SA", "SG", "KR", "LK", "TW", "TJ", "TH", "TL", "TR", "AE", "UZ", "VN"],
            "欧洲": ["AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IT", "XK", "LV", "LI", "LT", "LU", "MT", "MD", "MC", "ME", "NL", "MK", "NO", "PL", "PT", "RO", "SM", "RS", "SK", "SI", "ES", "SE", "CH", "UA", "GB"],
            "美洲": ["AG", "AR", "BS", "BB", "BZ", "BO", "BR", "CL", "CO", "CR", "CW", "DM", "DO", "EC", "SV", "GD", "GT", "GY", "HT", "HN", "JM", "MX", "NI", "PA", "PY", "PE", "KN", "LC", "VC", "SR", "TT", "UY", "VE", "CA", "US"],
            "大洋洲": ["AU", "FJ", "KI", "MH", "FM", "NR", "NZ", "PW", "PG", "WS", "SB", "TO", "TV", "VU"]
        }
        
        print(f"\n🌍 按地区统计:")
        for region, countries in regions.items():
            successful_in_region = sum(1 for code in countries if code in results)
            total_in_region = len(countries)
            region_success_rate = successful_in_region / total_in_region * 100 if total_in_region > 0 else 0
            print(f"  {region}: {successful_in_region}/{total_in_region} ({region_success_rate:.1f}%)")
