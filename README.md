# Spotify 价格爬虫与汇率转换器

这个项目自动抓取各国Spotify订阅价格，并转换为人民币进行比较分析。支持GitHub Actions自动化运行，每周更新数据。

## 🌟 功能特性

- 🌍 **全球价格抓取**: 自动抓取全球多个国家的Spotify Premium价格
- 💰 **实时汇率转换**: 实时汇率转换，将所有价格转换为人民币
- 📊 **智能排序**: 按Premium Family价格排序，找出最便宜的订阅地区
- 🤖 **自动化运行**: GitHub Actions每周自动运行
- 🔐 **安全管理**: 使用GitHub Secrets安全管理API密钥
- 📁 **详细报告**: 生成详细的JSON报告和统计信息
- 🗂️ **历史归档**: 自动归档历史数据，按年份组织，保留所有运行结果

## 📂 项目结构

```
├── spotify.py                          # 主爬虫脚本
├── spotify_rate_converter.py           # 汇率转换器
├── requirements.txt                     # Python依赖
├── .env.example                        # 环境变量示例
├── .gitignore                          # Git忽略文件
├── archive/                            # 历史数据归档目录
│   ├── 2025/                          # 2025年数据
│   ├── 2026/                          # 2026年数据
│   └── README.md                      # 归档说明
├── .github/workflows/
│   ├── weekly-spotify-scraper.yml      # 主自动化工作流
│   └── manual-test.yml                 # 手动测试工作流
└── README.md                           # 项目文档
```

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone <your-repo-url>
cd spotify-price-scraper
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
playwright install
```

### 3. 配置API密钥（必需！）
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，添加你的API密钥
API_KEY=你的API密钥
```

**重要**: 现在必须设置API密钥才能运行。获取免费API密钥：
1. 访问 [OpenExchangeRates](https://openexchangerates.org/)
2. 注册免费账户（每月1000次请求）
3. 获取你的API密钥

### 4. 运行测试
```bash
# 运行基础测试（如果有test_setup.py）
python test_setup.py
```

### 5. 手动运行
```bash
# 运行爬虫
python spotify.py

# 转换汇率
python spotify_rate_converter.py
```

## 🤖 GitHub Actions 自动化

### 自动化工作流

项目包含两个GitHub Actions工作流：

#### 1. **Weekly Spotify Scraper** (每周自动运行)
- **时间**: 每周日UTC时间0点（北京时间周日上午8点）
- **功能**: 自动爬取价格、转换汇率、提交数据
- **支持**: 手动触发运行

#### 2. **Manual Test Run** (手动测试)
- **功能**: 测试项目基本功能
- **模式**: 基础测试和完整测试

### 🔐 GitHub Secrets 配置（重要！）

为了安全使用汇率API，需要在GitHub仓库中设置secrets：

#### 设置步骤：
1. 进入GitHub仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret** 添加以下密钥：

| Secret Name | Description |
|-------------|-------------|
| `API_KEY` | 你的OpenExchangeRates API密钥 |

#### 获取自己的API密钥：
1. 访问 [OpenExchangeRates](https://openexchangerates.org/)
2. 注册免费账户
3. 获取API密钥
4. 在GitHub Secrets中添加为 `API_KEY`

### 手动触发工作流

1. 进入GitHub仓库的 **Actions** 页面
2. 选择对应的工作流
3. 点击 **Run workflow** 按钮
4. 查看执行结果和日志

## 📁 输出文件

- **`spotify_prices_all_countries.json`**: 原始爬取数据
- **`spotify_prices_cny_sorted.json`**: 转换为人民币并排序的数据
- **包含最便宜的10个Premium Family套餐排行**

## 📊 数据文件说明

项目运行后会生成以下数据文件：

### 主要数据文件
- `spotify_prices_all_countries.json` - 最新的价格数据（供转换器使用）
- `spotify_prices_cny_sorted.json` - 按人民币价格排序的结果

### 历史归档
- `archive/YYYY/spotify_prices_all_countries_YYYYMMDD_HHMMSS.json` - 按年份组织的历史数据
- **智能归档**: 自动解析文件名中的时间戳，归档到正确的年份目录
- 自动迁移现有根目录下的归档文件到对应年份目录
- 保留所有历史记录，便于长期趋势分析
- 目录结构示例：
  ```
  archive/
  ├── 2025/
  │   ├── spotify_prices_all_countries_20250630_143025.json
  │   ├── spotify_prices_all_countries_20250707_140000.json
  │   └── ...
  ├── 2026/
  │   └── spotify_prices_all_countries_20260101_080000.json
  └── ...
  ```

#### 归档功能特性
- **按年份自动分类**: 根据时间戳年份创建子目录
- **自动迁移**: 检测并迁移现有的归档文件到正确位置
- **统计信息**: 显示各年份的文件数量和总体统计
- **数据用途**: 跨年价格变化趋势分析、历史数据对比、价格波动研究

## ⚙️ 技术特性

- **异步爬虫**: 使用Playwright进行高效的并发爬取
- **浏览器自动化**: 支持Chromium/Firefox/WebKit (当前使用Chromium)
- **GitHub Actions支持**: 完全支持Playwright在云端运行
- **重试机制**: 内置错误处理和重试逻辑
- **汇率精度**: 使用Decimal确保价格计算精度
- **多语言支持**: 中英文国家名称对照
- **缓存优化**: GitHub Actions使用依赖缓存加速构建

## 🔧 故障排除

### 常见问题

1. **Playwright浏览器下载失败**
   ```bash
   # 强制重新安装
   playwright install --force
   
   # 在GitHub Actions中查看浏览器安装日志
   # 通常自动安装系统依赖就能解决
   ```

2. **本地Playwright测试**
   ```bash
   # 检查Playwright安装
   playwright --version
   
   # 测试浏览器
   python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright正常')"
   ```

3. **API密钥限制**
   - 检查API密钥是否有效
   - 确认没有超出请求限制
   - 尝试申请新的API密钥

4. **GitHub Actions失败**
   - 检查GitHub Secrets是否正确设置
   - 查看Actions日志确定具体错误
   - 手动触发测试工作流

5. **数据文件为空**
   - 确认爬虫成功运行
   - 检查网络连接
   - 查看错误日志

## 📋 依赖包

- `requests`: HTTP请求
- `beautifulsoup4`: HTML解析
- `playwright`: 浏览器自动化
- `lxml`: XML/HTML解析器
- `python-dotenv`: 环境变量管理

## ⚠️ 注意事项

- **合规使用**: 仅用于学习和研究目的，请遵守网站使用条款
- **频率限制**: 爬虫包含延迟机制，避免对服务器造成压力
- **数据准确性**: 价格数据仅供参考，请以官方价格为准
- **API限制**: OpenExchangeRates免费版有请求次数限制

## 📈 更新日志

- **v2.0** - 添加GitHub Actions自动化
- **v1.5** - 增加安全的API密钥管理
- **v1.0** - 初始版本，基础爬虫功能

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目！

## 📄 许可证

本项目仅用于学习和研究目的。

---

🎵 **开始享受全球最优惠的Spotify订阅价格分析吧！**
