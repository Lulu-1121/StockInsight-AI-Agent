import json
from zhipuai import ZhipuAI
from config import ZHIPU_API_KEY

def search_news(stock_name: str, industry_name: str):
    """
    搜索指定股票名称的近期新闻（搜狐网站，近1个月），以及所属行业的新闻。
    对每条新闻使用大模型生成摘要和情绪判断。
    返回三个值：stock_summaries（股票新闻摘要列表）、industry_summaries（行业新闻摘要列表）、markdown_str（用于展示的Markdown字符串）。
    """
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    # 搜索股票相关新闻（限定搜狐网，最近一个月，最多10条）
    stock_response = client.web_search.web_search(
        search_engine="search_pro",
        search_query=f"{stock_name} 股票 新闻",
        count=10,
        search_domain_filter="finance.sina.com.cn",
        search_recency_filter="oneMonth",
        content_size="high"
    )
    # 搜索行业相关新闻（限定搜狐网，最近一个月，最多5条）
    industry_response = client.web_search.web_search(
        search_engine="search_pro",
        search_query=f"{industry_name} 行业 新闻",
        count=5,
        search_domain_filter="finance.sina.com.cn",
        search_recency_filter="oneMonth",
        content_size="high"
    )
    # 提取搜索结果列表
    stock_data = stock_response.__dict__
    industry_data = industry_response.__dict__
    stock_results = stock_data.get('search_result', [])
    industry_results = industry_data.get('search_result', [])
    # 初始化返回结果和Markdown列表
    stock_summaries = []
    industry_summaries = []
    stock_md_lines = []
    industry_md_lines = []
    # ChatGLM 模型用于摘要和情感分析
    glm_client = ZhipuAI(api_key=ZHIPU_API_KEY)
    system_prompt = (
        "你是一个智能助手，请阅读新闻内容并用不超过30字总结其主要内容，"
        "并判断该新闻的情绪是乐观、悲观或中性。"
        "回答格式为：摘要（情绪）。"
    )
    # 处理股票新闻列表
    for res in stock_results[:10]:
        title = ""
        content = ""
        link = ""
        # 提取标题、内容、链接（SearchResultResp对象可能以属性或dict形式呈现）
        if hasattr(res, 'title'):
            title = res.title or ""
            content = getattr(res, 'content', "") or ""
            link = getattr(res, 'link', "") or ""
        elif isinstance(res, dict):
            title = res.get('title', "")
            content = res.get('content', "")
            link = res.get('link', "")
        # 将标题和内容合并供模型总结（提高准确性）
        text_to_summarize = content if not title else f"标题：{title}\n{content}"
        # 调用 ChatGLM 模型生成摘要和情绪
        response = glm_client.chat.completions.create(
            model="glm-4-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_to_summarize}
            ],
            temperature=0.2,
            top_p=0.8
        )
        summary = response.choices[0].message.content.strip()
        # 去除可能的格式符号
        summary = summary.strip('`').strip()
        stock_summaries.append(summary)
        # 组装 Markdown 链接行
        stock_md_lines.append(f"- {summary} [🔗原文链接]({link})")
    # 处理行业新闻列表（过程类似）
    for res in industry_results[:5]:
        title = ""
        content = ""
        link = ""
        if hasattr(res, 'title'):
            title = res.title or ""
            content = getattr(res, 'content', "") or ""
            link = getattr(res, 'link', "") or ""
        elif isinstance(res, dict):
            title = res.get('title', "")
            content = res.get('content', "")
            link = res.get('link', "")
        text_to_summarize = content if not title else f"标题：{title}\n{content}"
        response = glm_client.chat.completions.create(
            model="glm-4-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_to_summarize}
            ],
            temperature=0.2,
            top_p=0.8
        )
        summary = response.choices[0].message.content.strip()
        summary = summary.strip('`').strip()
        industry_summaries.append(summary)
        industry_md_lines.append(f"- {summary} [🔗原文链接]({link})")
    # 组装最终的 Markdown 字符串
    markdown_str = "### 股票新闻\n" + "\n".join(stock_md_lines) + "\n\n### 行业新闻\n" + "\n".join(industry_md_lines)
    return stock_summaries, industry_summaries, markdown_str