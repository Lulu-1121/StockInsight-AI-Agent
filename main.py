import os
import shutil
import time
from datetime import datetime
import gradio as gr
import analyzer
import stock_plotter
import nlp_parser

# 清理过期文件（删除 tmp_reports 中1小时之前的文件夹）
def clear_expired_reports():
    base_dir = "tmp_reports"
    if not os.path.isdir(base_dir):
        return
    now = time.time()
    for fname in os.listdir(base_dir):
        fpath = os.path.join(base_dir, fname)
        if os.path.isdir(fpath):
            mtime = os.path.getmtime(fpath)
            # 删除1小时之前的文件夹
            if now - mtime > 3600:
                shutil.rmtree(fpath, ignore_errors=True)

# 处理用户查询的主函数
def on_query(user_input):
    clear_expired_reports()
    # 解析用户输入
    parse_result = nlp_parser.parse_user_query(user_input)
    stock_code = parse_result.get("stock_code", "")
    stock_name = parse_result.get("stock_name", "")
    industry_name = parse_result.get("industry_name", "")  # 可能由 parse_user_query 提取
    start_date = parse_result.get("start_date", "")
    end_date = parse_result.get("end_date", "")
    mode = parse_result.get("mode", "analysis")

    # 如果解析未得到股票代码但有名称，再尝试从名称映射代码
    if not stock_code and stock_name:
        # parse_user_query内部已尝试，如仍没有则在此返回错误提示
        raise gr.Error(f"无法识别股票代码，请确认输入的股票名称/代码: {stock_name}")

    # 创建用于保存本次报告的目录
    os.makedirs("tmp_reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    code_for_dir = stock_code.replace('.', '_') if stock_code else stock_name
    report_dir = os.path.join("tmp_reports", f"{code_for_dir}_{timestamp}")
    os.makedirs(report_dir, exist_ok=True)

    # 根据查询模式执行不同操作
    if mode == "data":
        # 数据模式，仅返回历史数据Excel文件（和图表）
        price_chart_path, volume_chart_path, excel_path = stock_plotter.generate_charts(stock_code, stock_name, start_date, end_date, report_dir)
        # 数据模式不进行分析，直接提供Excel下载和图表（图表在此模式下可选显示）
        # 这里仍然返回图表路径方便预览，但分析文本留空
        empty_text = "（本次查询为行情数据请求，未生成分析结论。）"
        return empty_text, empty_text, empty_text, empty_text, empty_text, price_chart_path, volume_chart_path, excel_path, None

    # 分析模式：生成图表、新闻摘要、AI分析
    # 1. 获取历史行情数据并绘制图表
    price_chart_path, volume_chart_path, excel_path = stock_plotter.generate_charts(stock_code, stock_name, start_date, end_date, report_dir)
    # 2. 获取新闻摘要（股票新闻10条，行业新闻5条）
    stock_news_list = nlp_parser.get_stock_news(stock_name, count=10)
    # 如果解析结果没有industry_name，则尝试通过stock_name获取所属行业名（可在股票新闻中推测或略过）
    if not industry_name:
        industry_name = parse_result.get("industry_name", "")
    industry_news_list = nlp_parser.get_industry_news(industry_name, count=5) if industry_name else []
    # 3. 调用多模态大模型获取 基本面/行业/技术面 分析
    analysis_text = analyzer.analyze_fund_ind_tech(stock_name, stock_news_list, industry_news_list, price_chart_path, volume_chart_path)
    # 防止重复输出，确保只生成一次分析结论
    analysis_text = analysis_text.strip()
    # 4. 解析三部分分析文本
    fund_text, industry_text, tech_text = analyzer.parse_three_analysis(analysis_text)
    # 5. 调用 glm-4-plus 获取宏观分析 和 AI自由分析
    macro_text = analyzer.analyze_macro(stock_name).strip()
    ai_text = analyzer.analyze_ai_free(stock_name, fund_text, industry_text, tech_text, macro_text).strip()
    # 6. 分别对五部分分析调用AI评分5次取平均
    score_fund = analyzer.get_score(fund_text, "基本面分析")
    score_industry = analyzer.get_score(industry_text, "行业分析")
    score_tech = analyzer.get_score(tech_text, "技术面分析")
    score_macro = analyzer.get_score(macro_text, "宏观分析")
    score_ai = analyzer.get_score(ai_text, "AI分析")
    # 7. 组织左侧输出内容，每部分标题和评分加粗显示，内容换行显示
    fund_output = f"**基本面分析（评分：{score_fund}）**\n{fund_text}"
    industry_output = f"**行业分析（评分：{score_industry}）**\n{industry_text}"
    tech_output = f"**技术面分析（评分：{score_tech}）**\n{tech_text}"
    macro_output = f"**宏观分析（评分：{score_macro}）**\n{macro_text}"
    ai_output = f"**AI分析（评分：{score_ai}）**\n{ai_text}"
    # 8. 生成PDF报告文件，包含分析文本和图表
    pdf_path = os.path.join(report_dir, f"{code_for_dir}_报告.pdf")
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        c = canvas.Canvas(pdf_path, pagesize=A4)
        c.setFont('STSong-Light', 12)
        # 报告标题
        title_text = f"{stock_name}（{stock_code}）分析报告"
        c.drawString(50, 800, title_text)
        y = 770
        # 输出每个分析段落文本
        sections = [("基本面分析", fund_text, score_fund),
                    ("行业分析", industry_text, score_industry),
                    ("技术面分析", tech_text, score_tech),
                    ("宏观分析", macro_text, score_macro),
                    ("AI分析", ai_text, score_ai)]
        for cat, text, score in sections:
            c.drawString(50, y, f"{cat} (评分: {score})：")
            y -= 20
            # 简单按固定宽度换行
            width_limit = 38  # 每行约38个汉字
            text_lines = [text[i:i+width_limit] for i in range(0, len(text), width_limit)]
            for line in text_lines:
                c.drawString(70, y, line)
                y -= 18
                if y < 100:  # 页面空间不足时换页
                    c.showPage()
                    c.setFont('STSong-Light', 12)
                    y = 800
            y -= 10
            if y < 100:
                c.showPage()
                c.setFont('STSong-Light', 12)
                y = 800
        # 新页放图表
        c.showPage()
        # 将图表插入PDF第二页
        try:
            c.drawImage(price_chart_path, 50, 440, width=500, height=300)
            c.drawImage(volume_chart_path, 50, 100, width=500, height=300)
        except Exception:
            pass
        c.save()
    except Exception as e:
        pdf_path = None  # 如果生成PDF失败，则返回None

    return fund_output, industry_output, tech_output, macro_output, ai_output, price_chart_path, volume_chart_path, excel_path, pdf_path

# 搭建 Gradio 界面
with gr.Blocks(title="股票多维度分析AI工具") as demo:
    gr.Markdown("## 股票多维度分析 AI Agent\n输入股票名称或代码和问题，例如：`海尔智家最近1年情况如何？`")
    with gr.Row():
        query_input = gr.Textbox(label="股票名称或问句", placeholder="输入股票名称、代码或问题进行查询", lines=1)
        submit_btn = gr.Button("查询")
    with gr.Row():
        with gr.Column():
            fund_output = gr.Markdown()
            industry_output = gr.Markdown()
            tech_output = gr.Markdown()
            macro_output = gr.Markdown()
            ai_output = gr.Markdown()
        with gr.Column():
            price_image = gr.Image(label="股价走势", height=350)
            volume_image = gr.Image(label="成交量走势", height=250)
            with gr.Row():
                excel_file = gr.File(label="下载Excel", interactive=False)
                pdf_file = gr.File(label="下载PDF", interactive=False)
    # 将点击按钮事件绑定处理函数
    submit_btn.click(fn=on_query,
                     inputs=query_input,
                     outputs=[fund_output, industry_output, tech_output, macro_output, ai_output,
                              price_image, volume_image, excel_file, pdf_file],
                     queue=True)

# 启动应用
if __name__ == "__main__":
    demo.launch()