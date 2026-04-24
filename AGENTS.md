- - \---
    name: ai-wechat-daily
    description: Fetches daily AI news from RSS sources, summarizes and categorizes the content with LLM, rewrites it into WeChat Official Account article style, converts it into WeChat-compatible HTML, uploads required media, and creates a draft article for daily publishing. Use when building an automated AI news to WeChat content pipeline.

  - 

    # AI WeChat Daily Publisher

    一个**独立运行**的 AI 资讯日报生成与微信公众号草稿发布项目。

    它**不依赖 Claude Code**，而是一个普通的 Python 自动化内容生产流水线，完成以下工作：

    1. 从 AI 资讯 RSS 源抓取每日新闻
    2. 清洗、去重、筛选当天内容
    3. 使用 LLM 做摘要、分类、关键词提取与公众号风格改写
    4. 生成微信公众号兼容的 HTML 正文
    5. 生成封面图 / 摘要图（可选）
    6. 上传素材到微信公众号
    7. 创建公众号草稿，供人工审核或后续发布
  
    ---
  
    ## Project Goal
  
    构建一个可独立部署的“AI 资讯 -> 微信公众号日报”自动化系统，适合以下场景：
  
    - 每日 AI 行业资讯汇总
    - 公众号日更/周更内容生产
    - AI 资讯内容运营
    - 自动草稿箱生成
    - 后续扩展为多平台分发（公众号 / 小红书 / 博客 / 网站）
  
    ---
  
    ## Core Requirements
  
    ### Functional Requirements
  
    - 支持从一个或多个 RSS 源抓取资讯
    - 支持按日期获取指定日内容
    - 支持去重与相似内容合并
    - 支持按主题分类：
      - 模型发布
      - 产品动态
      - 研究进展
      - 工具框架
      - 融资并购
      - 行业事件
    - 支持生成公众号文章标题、导语、正文、结尾
    - 支持生成公众号摘要（digest）
    - 支持输出微信公众号兼容 HTML
    - 支持上传封面图和正文图片
    - 支持创建微信公众号草稿
    - 支持定时任务每日自动运行
    - 支持失败重试与日志记录
  
    ### Non-Functional Requirements
  
    - 项目必须可独立运行，不依赖 Claude Code
    - 模块解耦，便于替换 LLM、RSS 源、发布平台
    - 配置通过 `.env` 管理
    - 输出内容可追踪、可复用、可归档
    - 代码结构清晰，适合后续扩展为内容平台
  
    ---
  
    ## Suggested Tech Stack
  
    ### Language
    - Python 3.11+
  
    ### Data Fetching
    - requests
    - feedparser
  
    ### LLM Layer
    - OpenAI-compatible API / Anthropic-compatible API / DashScope / OpenRouter 均可
    - 通过统一 `llm_client.py` 封装，避免写死供应商
  
    ### Content Processing
    - markdown
    - jinja2（可选，用于模板渲染）
    - beautifulsoup4（可选，用于 HTML 清洗）
  
    ### Scheduler
    - cron / GitHub Actions / APScheduler 均可
  
    ### WeChat Publishing
    - 微信公众号素材上传接口
    - 微信公众号草稿创建接口
    - 后续可扩展发布接口
  
    ### Logging
    - logging
    - 可选 structlog
  
    
  
    uv的工程化管理虚拟环境
  
    ---
    
    ## Suggested Project Structure
    
    ```text
    ai-wechat-daily/
    ├── README.md
    ├── requirements.txt
    ├── .env.example
    ├── configs/
    │   ├── sources.yaml                # RSS 源配置
    │   ├── categories.yaml             # 分类标签配置
    │   └── prompt_templates.yaml       # 提示词模板
    ├── data/
    │   ├── raw/                        # 原始 RSS 内容缓存
    │   ├── processed/                  # 清洗后的结构化数据
    │   └── output/                     # 最终生成内容归档
    ├── docs/
    │   ├── articles/                   # HTML/Markdown 成品
    │   └── images/                     # 生成图片
    ├── src/
    │   ├── main.py                     # 主入口
    │   ├── config.py                   # 配置加载
    │   ├── scheduler.py                # 定时调度入口（可选）
    │   ├── logger.py                   # 日志封装
    │   ├── models/
    │   │   └── schemas.py              # 数据结构定义
    │   ├── fetchers/
    │   │   ├── rss_fetcher.py          # RSS 抓取
    │   │   └── source_manager.py       # 多源管理
    │   ├── processors/
    │   │   ├── cleaner.py              # 文本清洗
    │   │   ├── deduplicator.py         # 去重与相似合并
    │   │   ├── classifier.py           # 分类处理
    │   │   └── keyword_extractor.py    # 关键词提取
    │   ├── llm/
    │   │   ├── llm_client.py           # 统一大模型调用层
    │   │   ├── summarizer.py           # 摘要生成
    │   │   ├── rewriter.py             # 公众号风格改写
    │   │   └── title_generator.py      # 标题/摘要生成
    │   ├── renderers/
    │   │   ├── markdown_renderer.py    # Markdown 输出
    │   │   ├── wechat_renderer.py      # 微信兼容 HTML 输出
    │   │   └── image_renderer.py       # 封面图/摘要图生成（可选）
    │   ├── publishers/
    │   │   ├── wechat_client.py        # 微信 API 封装
    │   │   └── draft_publisher.py      # 草稿创建
    │   └── utils/
    │       ├── date_utils.py
    │       ├── file_utils.py
    │       └── retry.py
    └── tests/
        ├── test_fetcher.py
        ├── test_llm.py
        ├── test_renderer.py
        └── test_wechat.py
