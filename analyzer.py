import base64
from zhipuai import ZhipuAI
from config import ZHIPU_API_KEY

def analyze_fund_ind_tech(stock_name: str, stock_summaries: list, industry_summaries: list,
                          price_chart_path: str, volume_chart_path: str) -> str:
    """
    调用 GLM-4.1V-Thinking 多模态模型，对给定的新闻摘要和图表图像进行综合分析。
    返回股票的基本面分析、行业分析、技术面分析（不含评分）。
    """
    # 初始化多模态模型客户端
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    # 读取并编码图表图像为 Base64 Data URI
    images_content = []
    for img_path in [price_chart_path, volume_chart_path]:
        with open(img_path, "rb") as f:
            img_data = f.read()
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            images_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}"}
            })
    # 准备新闻摘要文本（股票新闻和行业新闻）
    news_text = "股票相关新闻摘要：\n"
    for summary in stock_summaries:
        news_text += f"- {summary}\n"
    news_text += "行业相关新闻摘要：\n"
    for summary in industry_summaries:
        news_text += f"- {summary}\n"
    # 准备提示语文本（不要求模型输出评分，只输出分析内容）
    prompt_text = (
        f"下面是关于股票「{stock_name}」的近期股票新闻摘要和行业新闻摘要，以及该股票的收盘价与成交量图表。\n"
        f"请综合以上图像和文本信息，从基本面、行业面、技术面三个方面对「{stock_name}」进行详细分析。\n"
        "请用中文回答，格式如下：\n"
        "基本面分析：<分析内容>\n"
        "行业分析：<分析内容>\n"
        "技术面分析：<分析内容>"
    )
    # 组装多模态消息内容（文本 + 图像）
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text + "\n" + news_text},
                *images_content
            ]
        }
    ]
    # 调用多模态大模型获取分析结果
    response = client.chat.completions.create(
        model="glm-4.1v-thinking-flashx",
        messages=messages
    )
    result_text = response.choices[0].message.content.strip()
    return result_text

def analyze_macro(stock_name: str) -> str:
    """
    调用 GLM-4-Plus 模型，生成关于整体A股市场宏观环境和投资价值的分析段落。
    """
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    prompt = (
        "请从宏观角度分析当前中国的宏观经济环境和整个A股市场的投资价值，并给出详细的宏观分析。"
        "请用中文回答。"
    )
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(model="glm-4-plus", messages=messages)
    macro_analysis = response.choices[0].message.content.strip()
    return macro_analysis

def analyze_ai_free(stock_name: str, fund_analysis: str, industry_analysis: str,
                   tech_analysis: str, macro_analysis: str) -> str:
    """
    调用 GLM-4-Plus 模型，基于已有的分析，自由生成AI视角的重要内容分析段落。
    """
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    # 将之前的分析内容提供给模型，要求进一步补充重要内容
    prompt = (
        f"以下是关于股票「{stock_name}」的分析：\n"
        f"基本面分析：{fund_analysis}\n"
        f"行业分析：{industry_analysis}\n"
        f"技术面分析：{tech_analysis}\n"
        f"宏观分析：{macro_analysis}\n"
        "请你作为AI，从整体上进一步分析该股票，不要包含和上述分析重叠的部分，并自由阐述任何上述分析未充分覆盖的重要内容。请给出详细的 AI 分析。"
    )
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(model="glm-4-plus", messages=messages)
    ai_analysis = response.choices[0].message.content.strip()
    return ai_analysis

def parse_three_analysis(result_text: str) -> tuple:
    """
    将多模态模型返回的综合分析结果文本解析为基本面、行业、技术面的分析内容三部分。
    假定 result_text 按格式包含三个部分的分析。
    """
    # 按固定标签划分文本
    fund_part = ""
    industry_part = ""
    tech_part = ""
    if "基本面分析" in result_text and "行业分析" in result_text and "技术面分析" in result_text:
        try:
            fund_tag = result_text.index("基本面分析")
            ind_tag = result_text.index("行业分析")
            tech_tag = result_text.index("技术面分析")
            fund_part = result_text[fund_tag + 6 : ind_tag].strip("：: \n")
            industry_part = result_text[ind_tag + 5 : tech_tag].strip("：: \n")
            tech_part = result_text[tech_tag + 6 :].strip("：: \n")
        except Exception:
            # 若解析失败，则将全文分别拆分为三段（按行或段落）
            segments = [seg.strip() for seg in result_text.splitlines() if seg.strip()]
            # 简单 fallback: 前三个非空段落分别作为三部分
            if len(segments) >= 3:
                fund_part, industry_part, tech_part = segments[0], segments[1], segments[2]
            else:
                fund_part = result_text
                industry_part = ""
                tech_part = ""
    else:
        # 格式不符预期，直接返回全文作为基本面分析，其余为空
        fund_part = result_text
    return fund_part, industry_part, tech_part

def get_score(analysis_text: str, aspect_name: str) -> int:
    """
    调用 GLM-4-Plus 模型，对给定分析文本进行0~100评分。调用5次取平均值作为最终评分。
    aspect_name 用于提示是哪个维度的评分（如“基本面分析”）。
    """
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    scores = []
    prompt = (
        f"以下是对股票的{aspect_name}。\n{analysis_text}\n"
        "请你根据上述分析内容，从0到100对该股票的此方面表现进行评分。"
        "请大胆给出评分，并且只输出一个数字。"
    )
    for _ in range(5):
        messages = [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(model="glm-4-plus", messages=messages)
        score_str = response.choices[0].message.content.strip()
        # 提取数字
        try:
            score_val = int(''.join(filter(str.isdigit, score_str)))
        except:
            # 如果无法解析，则跳过
            continue
        # 保证在0-100范围
        if 0 <= score_val <= 100:
            scores.append(score_val)
    if not scores:
        return 0
    avg_score = sum(scores) / len(scores)
    return int(round(avg_score))