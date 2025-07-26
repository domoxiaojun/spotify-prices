import json
import requests
import os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime  # 添加这一行
import re


# --- Configuration ---

# 尝试加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv 不是必需的依赖
    pass

# 从环境变量获取API密钥，如果没有则使用默认值（仅用于本地测试）
API_KEYS = []

# 读取API密钥
api_key = os.getenv('API_KEY')
if api_key:
    API_KEYS.append(api_key)

# 如果没有环境变量，使用默认密钥（仅用于本地开发测试）
if not API_KEYS:
    print("错误：未找到API密钥！")
    print("请设置环境变量 API_KEY 或在 .env 文件中配置")
    print("获取免费API密钥: https://openexchangerates.org/")
    exit(1)
API_URL_TEMPLATE = "https://openexchangerates.org/api/latest.json?app_id={}"
INPUT_JSON_PATH = 'spotify_prices_all_countries.json'
OUTPUT_JSON_PATH = 'spotify_prices_cny_sorted.json'


# 国家名称中英文对照表
COUNTRY_NAMES_CN = {
    'NG': '尼日利亚',
    'PK': '巴基斯坦', 
    'IN': '印度',
    'EG': '埃及',
    'TR': '土耳其',
    'BD': '孟加拉国',
    'GH': '加纳',
    'TZ': '坦桑尼亚',
    'PH': '菲律宾',
    'LK': '斯里兰卡',
    'KE': '肯尼亚',
    'VN': '越南',
    'UG': '乌干达',
    'TH': '泰国',
    'ZA': '南非',
    'MA': '摩洛哥',
    'ID': '印度尼西亚',
    'CO': '哥伦比亚',
    'TN': '突尼斯',
    'MX': '墨西哥',
    'RW': '卢旺达',
    'CL': '智利',
    'AR': '阿根廷',
    'MY': '马来西亚',
    'PE': '秘鲁',
    'BR': '巴西',
    'KR': '韩国',
    'TW': '台湾',
    'PL': '波兰',
    'CZ': '捷克',
    'HU': '匈牙利',
    'RO': '罗马尼亚',
    'TR': '土耳其',
    'HK': '香港',
    'SG': '新加坡',
    'IL': '以色列',
    'PT': '葡萄牙',
    'ES': '西班牙',
    'IT': '意大利',
    'DE': '德国',
    'FR': '法国',
    'AT': '奥地利',
    'BE': '比利时',
    'NL': '荷兰',
    'CH': '瑞士',
    'SE': '瑞典',
    'NO': '挪威',
    'DK': '丹麦',
    'FI': '芬兰',
    'IE': '爱尔兰',
    'GB': '英国',
    'CA': '加拿大',
    'US': '美国',
    'AU': '澳大利亚',
    'NZ': '新西兰',
    'JP': '日本'
}


# --- Functions ---

def extract_price_from_text(price_text, currency):
    """从价格文本中提取数字价格"""
    if not price_text or not isinstance(price_text, str):
        return None
    
    # 不同货币的符号
    currency_symbols = {
        'USD': r'\$',
        'EUR': r'€',
        'GBP': r'£',
        'CNY': r'¥|yuan',
        'JPY': r'¥',
    }
    
    # 获取当前货币的符号，如果没有找到则使用通用模式
    symbol = currency_symbols.get(currency, r'[¥$€£]')
    
    # 更精确的匹配模式
    patterns = [
        # 匹配 $6,49 格式（欧洲/拉美用逗号作小数点）
        rf'{symbol}\s*(\d+),(\d{{1,2}})',  # $6,49
        # 匹配 $6.49 格式（美国用点作小数点）  
        rf'{symbol}\s*(\d+)\.(\d{{1,2}})',  # $6.49
        # 匹配 $1,234.56 格式（千位分隔符+小数点）
        rf'{symbol}\s*(\d{{1,3}}(?:,\d{{3}})+)\.(\d{{1,2}})',  # $1,234.56
        # 匹配整数
        rf'{symbol}\s*(\d+)',  # $6
        # 后置符号格式
        rf'(\d+),(\d{{1,2}})\s*{symbol}',  # 6,49$
        rf'(\d+)\.(\d{{1,2}})\s*{symbol}',  # 6.49$
        rf'(\d+)\s*{symbol}',  # 6$
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, price_text)
        if match:
            try:
                if len(match.groups()) == 2:
                    # 有小数部分
                    integer_part = match.group(1)
                    decimal_part = match.group(2)
                    
                    # 如果是千位分隔符格式，移除逗号
                    if ',' in integer_part and i == 2:  # $1,234.56 格式
                        integer_part = integer_part.replace(',', '')
                    
                    price_str = f"{integer_part}.{decimal_part}"
                    return float(price_str)
                else:
                    # 只有整数部分
                    integer_part = match.group(1)
                    # 移除千位分隔符（如果有）
                    integer_part = integer_part.replace(',', '')
                    return float(integer_part)
            except (ValueError, AttributeError):
                continue
    
    print(f"无法从 '{price_text}' 中提取价格")
    return None

def standardize_plan_name(plan_name):
    """标准化套餐名称为英文统一格式"""
    if not plan_name:
        return plan_name
    
    # 转换为小写用于匹配
    plan_lower = plan_name.lower()
    
    # 定义标准化映射规则
    standardization_map = {
        # Individual/Personal plans
        'premium individual': 'Premium Individual',
        'premium personal': 'Premium Individual', 
        'premium個人': 'Premium Individual',
        'premium 個人': 'Premium Individual',
        'premium个人': 'Premium Individual',
        'premium 个人': 'Premium Individual',
        # 法语
        'premium personnel': 'Premium Individual',
        # 芬兰语
        'yksilö-premium': 'Premium Individual',
        # 匈牙利语
        'egyéni premium csomag': 'Premium Individual',
        # 韩语/日语
        'premium standard': 'Premium Individual',
        # 斯瓦希里语
        'premium ya binafsi': 'Premium Individual',
        
        # Student plans
        'premium para estudiantes': 'Premium Student',
        'premium student': 'Premium Student',
        'premium estudiantil': 'Premium Student',
        'premium universitário': 'Premium Student',
        'premium étudiant': 'Premium Student',
        'premium studenten': 'Premium Student',
        'premium学生': 'Premium Student',
        'premium 学生': 'Premium Student',
        'premium大学生': 'Premium Student',
        'premium 大学生': 'Premium Student',
        'premium 學生': 'Premium Student',
        'premium學生': 'Premium Student',
        # 法语
        'premium étudiants': 'Premium Student',
        # 芬兰语
        'opiskelija‑premium': 'Premium Student',
        # 匈牙利语
        'hallgatói premium csomag': 'Premium Student',
        # 摩洛哥法语
        'premium étudiants': 'Premium Student',
        
        # Duo plans
        'premium duo': 'Premium Duo',
        'premium para dois': 'Premium Duo',
        'premium couple': 'Premium Duo',
        'premium雙人': 'Premium Duo',
        'premium 雙人': 'Premium Duo',
        'premium双人': 'Premium Duo',
        'premium 双人': 'Premium Duo',
        # 芬兰语
        'duo‑premium': 'Premium Duo',
        # 匈牙利语
        'premium duo csomag': 'Premium Duo',
        
        # Family plans
        'premium familiar': 'Premium Family',
        'premium family': 'Premium Family',
        'premium família': 'Premium Family',
        'premium famille': 'Premium Family',
        'premium familie': 'Premium Family',
        'premium家庭': 'Premium Family',
        'premium 家庭': 'Premium Family',
        'premium家族': 'Premium Family',
        'premium 家族': 'Premium Family',
        # 芬兰语
        'perhe‑premium': 'Premium Family',
        # 匈牙利语
        'családi premium csomag': 'Premium Family',
        # 斯瓦希里语
        'premium ya familia': 'Premium Family',
        
        # Special/Other plans
        'premium basic': 'Premium Basic',  # 韩国特殊套餐
        'premium lite': 'Premium Lite',    # 哥伦比亚等
        
        # Free plans
        'spotify free': 'Spotify Free',
        'free': 'Spotify Free',
        'gratuito': 'Spotify Free',
        'gratuit': 'Spotify Free',
        '免費': 'Spotify Free',
        '免费': 'Spotify Free',
    }
    
    # 直接匹配
    if plan_lower in standardization_map:
        return standardization_map[plan_lower]
    
    # 模糊匹配（包含关键词）
    if any(keyword in plan_lower for keyword in ['individual', 'personal', 'personnel', 'yksilö', 'egyéni', 'binafsi']):
        if 'premium' in plan_lower:
            return 'Premium Individual'
    
    if any(keyword in plan_lower for keyword in ['estudiante', 'student', 'étudiant', 'studenten', 'opiskelija', 'hallgatói', '学生', '學生', '大学生']):
        if 'premium' in plan_lower:
            return 'Premium Student'
    
    if any(keyword in plan_lower for keyword in ['duo', 'couple', '双人', '雙人']):
        if 'premium' in plan_lower:
            return 'Premium Duo'
    
    if any(keyword in plan_lower for keyword in ['familiar', 'family', 'família', 'famille', 'familie', 'perhe', 'családi', 'familia', '家庭', '家族']):
        if 'premium' in plan_lower:
            return 'Premium Family'
    
    if any(keyword in plan_lower for keyword in ['free', 'gratuito', 'gratuit', '免費', '免费']):
        return 'Spotify Free'
    
    # 特殊处理
    if 'basic' in plan_lower and 'premium' in plan_lower:
        return 'Premium Basic'
    
    if 'lite' in plan_lower and 'premium' in plan_lower:
        return 'Premium Lite'
    
    # 如果没有匹配到，保持原名称但首字母大写
    return plan_name.title()
    
def get_current_date():
    """获取当前日期"""
    return datetime.now().strftime('%Y-%m-%d')
        
def get_exchange_rates(api_keys, url_template):
    """获取最新汇率，如果API失败则返回None"""
    rates = None
    for key in api_keys:
        url = url_template.format(key)
        try:
            print(f"正在尝试使用API密钥 ...{key[-4:]} 获取汇率...")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if 'rates' in data:
                print(f"成功使用 API 密钥 ...{key[-4:]} 获取汇率")
                rates = data['rates']
                if 'USD' not in rates:
                    rates['USD'] = 1.0
                return rates
            else:
                print(f"API 密钥 ...{key[-4:]} 可能无效或受限: {data.get('description')}")
        except requests.exceptions.RequestException as e:
            print(f"使用密钥 ...{key[-4:]} 获取汇率时出错: {e}")
        except json.JSONDecodeError:
            print(f"使用密钥 ...{key[-4:]} 解码 JSON 响应时出错")
    
    print("无法使用所有提供的 API 密钥获取汇率")
    return None


def convert_to_cny(amount, currency_code, rates):
    """将金额从指定货币转换为人民币"""
    if not isinstance(amount, (int, float, Decimal)):
        return None
    
    if not rates or not currency_code:
        return None
    
    # Convert amount to Decimal for precision
    amount = Decimal(str(amount))
    
    try:
        if currency_code == 'CNY':
            return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        if 'CNY' not in rates:
            print(f"警告：汇率表中未找到 CNY")
            return None
        
        if currency_code not in rates:
            print(f"警告：汇率表中未找到 {currency_code}")
            return None
        
        cny_rate = Decimal(str(rates['CNY']))
        
        if currency_code == 'USD':
            cny_amount = amount * cny_rate
        else:
            original_rate = Decimal(str(rates[currency_code]))
            if original_rate == 0:
                print(f"警告：{currency_code} 的汇率为零")
                return None
            usd_amount = amount / original_rate
            cny_amount = usd_amount * cny_rate
        
        return cny_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    except Exception as e:
        print(f"转换 {amount} {currency_code} 到 CNY 时出错: {e}")
        return None


def process_spotify_data(data, rates):
    """处理Spotify价格数据，添加CNY汇率转换"""
    processed_data = {}
    
    for country_code, country_info in data.items():
        print(f"正在处理 {country_info.get('country_name', country_code)} ({country_code})...")
        
        processed_plans = []
        
        for plan in country_info.get('plans', []):
            plan_name = plan.get('plan', '')
            currency = plan.get('currency', '')
            
            # 标准化套餐名称
            standardized_plan_name = standardize_plan_name(plan_name)
            
            # Create processed plan object
            processed_plan = {
                'plan': standardized_plan_name,  # 使用标准化名称
                'original_plan_name': plan_name,  # 保留原始名称以备参考
                'currency': currency
            }
            
            # Process primary_price and secondary_price
            primary_price = plan.get('primary_price', '')
            secondary_price = plan.get('secondary_price', '')
            price_number = plan.get('price_number')
            
            # 优先使用 secondary_price
            if secondary_price and secondary_price.strip():
                processed_plan['price'] = secondary_price
                
                # 尝试从 price_number 获取价格，如果为0或None则从文本提取
                if price_number is not None and price_number > 0:
                    processed_plan['price_number'] = format_price_number(price_number)
                    cny_price = convert_to_cny(price_number, currency, rates)
                    if cny_price is not None:
                        processed_plan['price_cny'] = float(cny_price)
                    else:
                        processed_plan['price_cny'] = None
                else:
                    # 从 secondary_price 文本中提取价格
                    extracted_price = extract_price_from_text(secondary_price, currency)
                    if extracted_price is not None:
                        processed_plan['price_number'] = format_price_number(extracted_price)
                        cny_price = convert_to_cny(extracted_price, currency, rates)
                        if cny_price is not None:
                            processed_plan['price_cny'] = float(cny_price)
                        else:
                            processed_plan['price_cny'] = None
                    else:
                        processed_plan['price_number'] = None
                        processed_plan['price_cny'] = None
                        
            elif primary_price and primary_price.strip():
                processed_plan['price'] = primary_price
                
                # 尝试从 price_number 获取价格，如果为0或None则从文本提取
                if price_number is not None and price_number > 0:
                    processed_plan['price_number'] = format_price_number(price_number)
                    cny_price = convert_to_cny(price_number, currency, rates)
                    if cny_price is not None:
                        processed_plan['price_cny'] = float(cny_price)
                    else:
                        processed_plan['price_cny'] = None
                else:
                    # 从 primary_price 文本中提取价格
                    extracted_price = extract_price_from_text(primary_price, currency)
                    if extracted_price is not None:
                        processed_plan['price_number'] = format_price_number(extracted_price)
                        cny_price = convert_to_cny(extracted_price, currency, rates)
                        if cny_price is not None:
                            processed_plan['price_cny'] = float(cny_price)
                        else:
                            processed_plan['price_cny'] = None
                    else:
                        processed_plan['price_number'] = None
                        processed_plan['price_cny'] = None
            else:
                # No valid price found
                processed_plan['price'] = ''
                processed_plan['price_number'] = None
                processed_plan['price_cny'] = None
            
            # Copy other fields if needed
            processed_plan['source'] = plan.get('source', '')
            
            processed_plans.append(processed_plan)
        
        processed_data[country_code] = {
            'country_code': country_code,
            'country_name': country_info.get('country_name', ''),
            'plans': processed_plans,
            'scraped_at': country_info.get('scraped_at', ''),
            'source_url': country_info.get('source_url', ''),
            'attempt': country_info.get('attempt', 1)
        }
    
    return processed_data

def sort_by_family_plan_cny(processed_data, original_data):
    """按Premium Family的CNY价格从低到高排序国家，并在JSON前面添加最便宜的10个"""
    countries_with_family_price = []
    countries_without_family_price = []
    
    for country_code, country_info in processed_data.items():
        family_plan = None
        
        # Find Premium Family plan (支持多语言)
        for plan in country_info.get('plans', []):
            plan_name = plan.get('plan', '')
            if ('Premium Family' in plan_name or 'Premium Familiar' in plan_name or 
                'Premium Famille' in plan_name or 'Premium Familie' in plan_name):
                family_plan = plan
                break
        
        if family_plan and family_plan.get('price_cny') is not None:
            countries_with_family_price.append((country_code, family_plan['price_cny'], country_info, family_plan))
        else:
            countries_without_family_price.append((country_code, country_info))
    
    # Sort countries with family plan by CNY price
    countries_with_family_price.sort(key=lambda x: x[1])
    
    # Create sorted result with top 10 cheapest Premium Family plans first
    sorted_data = {}
    
    # Add top 10 cheapest Premium Family summary
    top_10_cheapest = []
    for i, (country_code, price_cny, country_info, family_plan) in enumerate(countries_with_family_price[:10]):
        country_name_cn = COUNTRY_NAMES_CN.get(country_code, country_info.get('country_name', country_code))
        # 获取原始 price_number 数值进行格式化
        original_price_number = None
        for original_plan in original_data.get(country_code, {}).get('plans', []):
            plan_name = original_plan.get('plan', '')
            # 支持多语言的家庭套餐名称
            if ('Premium Family' in plan_name or 'Premium Familiar' in plan_name or 
                'Premium Famille' in plan_name or 'Premium Familie' in plan_name):
                original_price_number = original_plan.get('price_number')
                break
        
        formatted_price_number = format_price_number(original_price_number)
        
        top_10_cheapest.append({
            'rank': i + 1,
            'country_code': country_code,
            'country_name': country_info.get('country_name', ''),
            'country_name_cn': country_name_cn,
            'original_price': family_plan.get('price', ''),
            'currency': family_plan.get('currency', ''),
            'price_number': formatted_price_number,
            'price_cny': family_plan.get('price_cny')
        })
    
    sorted_data['_top_10_cheapest_premium_family'] = {
        'description': '最便宜的10个Premium Family套餐',
        'updated_at': get_current_date(), 
        'data': top_10_cheapest
    }
    
    # Add countries with Premium Family plan (sorted by price)
    for country_code, price_cny, country_info, family_plan in countries_with_family_price:
        sorted_data[country_code] = country_info
    
    # Add countries without Premium Family plan at the end
    for country_code, country_info in countries_without_family_price:
        sorted_data[country_code] = country_info
    
    return sorted_data


def format_price_number(price_number):
    """格式化价格数字，添加千位分隔符，如果是整数则不显示小数点"""
    if price_number is None:
        return None
    
    # 如果是整数（包括像 1300.0 这样的浮点数），格式化为整数并添加千位分隔符
    if isinstance(price_number, float) and price_number.is_integer():
        return f"{int(price_number):,}"
    elif isinstance(price_number, int):
        return f"{price_number:,}"
    else:
        # 对于有小数的数字，保留小数位并添加千位分隔符
        return f"{price_number:,}"


# --- Main Script ---

def main():
    print("Spotify价格汇率转换器")
    print("=" * 50)
    
    # 1. Get exchange rates
    print("1. 获取汇率...")
    exchange_rates = get_exchange_rates(API_KEYS, API_URL_TEMPLATE)
    if exchange_rates:
        print(f"成功获取汇率。基础货币: USD，找到 {len(exchange_rates)} 个汇率")
        if 'CNY' in exchange_rates:
            print(f"USD 到 CNY 汇率: {exchange_rates['CNY']:.4f}")
        else:
            print("警告：汇率表中未找到 CNY!")
    else:
        print("错误：无法获取汇率")
        return
    
    # 2. Load Spotify data
    print(f"\n2. 从 {INPUT_JSON_PATH} 加载Spotify价格数据...")
    try:
        with open(INPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            spotify_data = json.load(f)
        print(f"成功加载数据，包含 {len(spotify_data)} 个国家")
    except FileNotFoundError:
        print(f"错误：输入文件未找到: {INPUT_JSON_PATH}")
        return
    except json.JSONDecodeError as e:
        print(f"错误：JSON解码失败: {e}")
        return
    except Exception as e:
        print(f"加载文件时发生错误: {e}")
        return
    
    # 3. Process data (add CNY conversion)
    print("\n3. 处理价格数据并转换为人民币...")
    processed_data = process_spotify_data(spotify_data, exchange_rates)
    
    # 4. Sort by Premium Family CNY price
    print("\n4. 按Premium Family的CNY价格排序...")
    sorted_data = sort_by_family_plan_cny(processed_data, spotify_data)
    
    # 5. Save processed data
    print(f"\n5. 保存处理后的数据到 {OUTPUT_JSON_PATH}...")
    try:
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        print("处理完成！")
        
        # Show top 10 cheapest Premium Family plans
        print("\n最便宜的10个Premium Family套餐:")
        print("-" * 60)
        if '_top_10_cheapest_premium_family' in sorted_data:
            for item in sorted_data['_top_10_cheapest_premium_family']['data']:
                print(f"{item['rank']:2d}. {item['country_name_cn']:15s} ({item['country_code']}): "
                      f"¥{item['price_cny']:7.2f} ({item['currency']} {item['price_number']})")
        else:
            count = 0
            for country_code, country_info in sorted_data.items():
                if country_code.startswith('_'):
                    continue
                for plan in country_info.get('plans', []):
                    plan_name = plan.get('plan', '')
                    if (('Premium Family' in plan_name or 'Premium Familiar' in plan_name or 
                         'Premium Famille' in plan_name or 'Premium Familie' in plan_name) and 
                        plan.get('price_cny') is not None):
                        country_name_cn = COUNTRY_NAMES_CN.get(country_code, country_info['country_name'])
                        print(f"{count+1:2d}. {country_name_cn:15s} ({country_code}): "
                              f"¥{plan['price_cny']:7.2f} ({plan['currency']} {plan.get('price_number', 'N/A')})")
                        count += 1
                        if count >= 10:
                            break
                if count >= 10:
                    break
        
    except Exception as e:
        print(f"保存文件时出错: {e}")


if __name__ == "__main__":
    main()
