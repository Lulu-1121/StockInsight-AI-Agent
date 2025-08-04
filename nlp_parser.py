import re
import datetime
from zhipuai import ZhipuAI
from config import ZHIPU_API_KEY

def parse_user_query(query: str) -> dict:
    """
    解析用户的自然语言查询，提取股票代码、名称、查询模式（数据或分析）、起止日期等信息。
    返回字典包含: mode, stock_code, stock_name, start_date, end_date。
    """
    result = {
        "mode": "analysis",
        "stock_code": "",
        "stock_name": "",
        "start_date": "",
        "end_date": ""
    }
    q = query.strip()
    # 判断查询模式：包含"行情"或"数据"等关键词则认为是请求数据，否则默认为分析
    data_keywords = ["行情", "数据"]
    for kw in data_keywords:
        if kw in q:
            result["mode"] = "data"
            break
    # 提取显式日期范围，如YYYYMMDD到YYYYMMDD
    date_pattern = re.findall(r'\d{4}-?\d{2}-?\d{2}', q)
    if len(date_pattern) >= 2:
        # 提取开始和结束日期
        start_str = date_pattern[0].replace('-', '')
        end_str = date_pattern[1].replace('-', '')
        result["start_date"] = start_str
        result["end_date"] = end_str
    elif len(date_pattern) == 1:
        # 只有一个日期出现，则视为开始日期，结束日期设为今天
        start_str = date_pattern[0].replace('-', '')
        result["start_date"] = start_str
        result["end_date"] = datetime.datetime.now().strftime("%Y%m%d")
    # 处理相对时间描述 "最近N年/月/日"
    rel_match = re.search(r'(\d+)\s*年', q)
    if rel_match:
        years = int(rel_match.group(1))
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=365 * years)
        result["start_date"] = start_date.strftime("%Y%m%d")
        result["end_date"] = end_date.strftime("%Y%m%d")
    rel_match = re.search(r'(\d+)\s*月', q)
    if rel_match:
        months = int(rel_match.group(1))
        end_date = datetime.datetime.now()
        # 计算月差
        year = end_date.year
        month = end_date.month - months
        if month <= 0:
            year -= (abs(month) // 12 + 1)
            month = 12 - (abs(end_date.month - months) % 12)
        day = end_date.day
        try:
            start_date = end_date.replace(year=year, month=month, day=day)
        except ValueError:
            # 若日期不合法，比如2月30日，调整为月末
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            start_date = end_date.replace(year=year, month=month, day=last_day)
        result["start_date"] = start_date.strftime("%Y%m%d")
        result["end_date"] = end_date.strftime("%Y%m%d")
    rel_match = re.search(r'(\d+)\s*(天|日)', q)
    if rel_match:
        days = int(rel_match.group(1))
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days)
        result["start_date"] = start_date.strftime("%Y%m%d")
        result["end_date"] = end_date.strftime("%Y%m%d")
    # 如果未提及日期范围，则默认近一年
    if result["start_date"] == "" and result["end_date"] == "":
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=365)
        result["start_date"] = start_date.strftime("%Y%m%d")
        result["end_date"] = end_date.strftime("%Y%m%d")
    # 提取股票代码或名称
    stock_code = ""
    stock_name = ""
    # 检查是否包含形如 000001.SZ 或 600000.SH 的代码
    code_match = re.search(r'\d{6}\.[SsZz][HhZz]', q)
    if code_match:
        stock_code = code_match.group(0).upper()
    else:
        # 检查6位数字（可能缺少交易所后缀）
        code_match = re.search(r'\d{6}', q)
        if code_match:
            code_digits = code_match.group(0)
            # 根据代码判断交易所
            if code_digits[0] in ['5', '6', '9']:
                stock_code = code_digits + ".SH"
            else:
                stock_code = code_digits + ".SZ"
    # 提取中文股票名称（去除常见无关词后取最长的中文串）
    temp_q = q
    for kw in ["最近", "过去", "情况", "如何", "怎么样", "的", "股票"]:
        temp_q = temp_q.replace(kw, " ")
    name_candidates = re.findall(r'[\u4e00-\u9fff]{2,}', temp_q)
    if name_candidates:
        # 取最长的中文片段作为股票名称
        name_candidates.sort(key=len, reverse=True)
        stock_name_candidate = name_candidates[0]
        # 如果候选名称中不包含明显的非公司字样，则采用
        if stock_name_candidate not in ["行情", "数据", "情况"]:
            stock_name = stock_name_candidate
    # 如果同时得到了股票代码和名称，则优先使用代码查询；若只有名称则需要通过名称查代码
    result["stock_code"] = stock_code
    result["stock_name"] = stock_name
    # 若没有代码，尝试通过名称获取代码和标准名称
    if stock_code == "" and stock_name:
        try:
            # 使用 Tushare 获取匹配的股票代码和行业（需配置 TUSHARE_TOKEN）
            from config import TUSHARE_TOKEN
            if TUSHARE_TOKEN:
                import tushare as ts
                ts.set_token(TUSHARE_TOKEN)
                pro = ts.pro_api()
                df_basic = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,industry')
                # 精确匹配名称
                match = df_basic[df_basic['name'] == stock_name]
                if match.empty:
                    # 尝试模糊匹配（名称包含）
                    match = df_basic[df_basic['name'].str.contains(stock_name)]
                if not match.empty:
                    stock_code = match.iloc[0]['ts_code']
                    stock_name_official = match.iloc[0]['name']
                    industry_name = match.iloc[0]['industry']
                    result["stock_code"] = stock_code
                    result["stock_name"] = stock_name_official
                    result["industry_name"] = industry_name
        except Exception:
            pass
    # 若通过名称未找到，则结果中可能只有名称，这种情况下在后续步骤处理
    return result

def get_stock_news(stock_name: str, count: int = 10) -> list:
    """
    使用 ZhipuAI 的网络搜索功能获取股票相关新闻标题或摘要。返回最多 count 条相关新闻摘要列表。
    """
    summaries = []
    if not stock_name:
        return summaries
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    try:
        search_query = f"{stock_name} 股票 新闻"
        resp = client.web_search.web_search(search_engine="search_pro", search_query=search_query,
                                            page=1, count=count, search_result=True, content_summary=True)
        documents = resp.get("data", {}).get("documents", [])
        for doc in documents[:count]:
            # 尝试使用content_summary或content作为新闻摘要，没有则用标题
            summary_text = ""
            if 'content' in doc and doc['content']:
                summary_text = doc['content']
            elif 'content_summary' in doc and doc['content_summary']:
                summary_text = doc['content_summary']
            elif 'snippet' in doc and doc['snippet']:
                summary_text = doc['snippet']
            else:
                summary_text = doc.get('title', '')
            summary_text = summary_text.strip()
            if summary_text:
                # 截取前120字以内的一段
                if len(summary_text) > 120:
                    summary_text = summary_text[:120] + "..."
                summaries.append(summary_text)
    except Exception:
        # 如果搜索 API 调用失败，返回空列表
        summaries = []
    return summaries

def get_industry_news(industry_name: str, count: int = 5) -> list:
    """
    使用 ZhipuAI 网络搜索获取行业相关新闻摘要列表。返回最多 count 条相关行业新闻摘要。
    """
    summaries = []
    if not industry_name:
        return summaries
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    try:
        search_query = f"{industry_name} 行业 新闻"
        resp = client.web_search.web_search(search_engine="search_pro", search_query=search_query,
                                            page=1, count=count, search_result=True, content_summary=True)
        documents = resp.get("data", {}).get("documents", [])
        for doc in documents[:count]:
            summary_text = ""
            if 'content' in doc and doc['content']:
                summary_text = doc['content']
            elif 'content_summary' in doc and doc['content_summary']:
                summary_text = doc['content_summary']
            elif 'snippet' in doc and doc['snippet']:
                summary_text = doc['snippet']
            else:
                summary_text = doc.get('title', '')
            summary_text = summary_text.strip()
            if summary_text:
                if len(summary_text) > 120:
                    summary_text = summary_text[:120] + "..."
                summaries.append(summary_text)
    except Exception:
        summaries = []
    return summaries