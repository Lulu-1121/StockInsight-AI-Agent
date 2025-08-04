import os
import math
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from config import TUSHARE_TOKEN

plt.rcParams['font.sans-serif'] = ['Heiti TC']   
plt.rcParams['axes.unicode_minus'] = False  
plt.rcParams['figure.dpi'] = 800

# 如果使用 Tushare，则初始化其 API（需要在 config.py 中提供 TUSHARE_TOKEN）
pro = None
if TUSHARE_TOKEN:
    try:
        import tushare as ts
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()
    except ImportError:
        pro = None

def generate_charts(stock_code: str, stock_name: str, start_date: str, end_date: str, output_dir: str):
    """
    获取股票在指定日期范围内的历史行情数据，并生成收盘价走势图和成交量图。
    保存图表为PNG文件和行情数据为Excel文件，返回图表文件路径和Excel文件路径。
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    # 获取历史数据（优先使用 tushare，其次尝试 akshare）
    df = None
    if pro:
        try:
            # tushare 接口要求日期格式YYYYMMDD
            df_query = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
            if not df_query.empty:
                # 转换日期格式并排序
                df_query['trade_date'] = pd.to_datetime(df_query['trade_date'])
                df_query.sort_values('trade_date', inplace=True)
                df_query.reset_index(drop=True, inplace=True)
                # 重命名列统一格式
                df_query.rename(columns={'trade_date': 'date', 'open': 'open', 'high': 'high', 
                                         'low': 'low', 'close': 'close', 'vol': 'volume'}, inplace=True)
                df = df_query[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            else:
                df = None
        except Exception:
            df = None
    if df is None:
        try:
            import akshare as ak
        except ImportError:
            ak = None
        if ak:
            # akshare 接口使用 YYYYMMDD 格式日期
            try:
                df_query = ak.stock_zh_a_hist(symbol=stock_code.split('.')[0], period="daily",
                                              start_date=start_date, end_date=end_date, adjust="")
                # akshare返回的DataFrame含列: 日期, 开盘, 收盘, 最高, 最低, 成交量, etc.
                df_query.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                                         '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
                df_query['date'] = pd.to_datetime(df_query['date'])
                df_query.sort_values('date', inplace=True)
                df_query.reset_index(drop=True, inplace=True)
                df = df_query[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            except Exception:
                df = None
    # 如果仍未获取数据，则生成一个空的 DataFrame 以免后续报错
    if df is None or df.empty:
        date_range = pd.date_range(pd.to_datetime(start_date), pd.to_datetime(end_date))
        df = pd.DataFrame({
            'date': date_range,
            'open': [math.nan]*len(date_range),
            'high': [math.nan]*len(date_range),
            'low':  [math.nan]*len(date_range),
            'close': [math.nan]*len(date_range),
            'volume': [math.nan]*len(date_range)
        })
    # 计算技术指标: 移动平均线和布林带上下轨，以及成交量均线
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA60'] = df['close'].rolling(window=60).mean()
    # Bollinger Bands (20日均线上下2倍标准差)
    df['BOLL_mid'] = df['MA20']
    df['BOLL_std'] = df['close'].rolling(window=20).std()
    df['BOLL_upper'] = df['BOLL_mid'] + 2 * df['BOLL_std']
    df['BOLL_lower'] = df['BOLL_mid'] - 2 * df['BOLL_std']
    # 成交量移动平均线
    df['VOL_MA5'] = df['volume'].rolling(window=5).mean()
    df['VOL_MA10'] = df['volume'].rolling(window=10).mean()
    df['VOL_MA20'] = df['volume'].rolling(window=20).mean()
    df['VOL_MA60'] = df['volume'].rolling(window=60).mean()

    dates = df['date']
    closes = df['close']
    volumes = df['volume']

    # 绘制收盘价走势图
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    ax1.set_title(f"{stock_name} 收盘价走势", fontsize=12)
    ax1.set_xlabel("日期", fontsize=10)
    ax1.set_ylabel("价格", fontsize=10)
    # 绘制收盘价曲线
    ax1.plot(dates, closes, label='收盘价', color='black')
    # 绘制移动平均线 (5日, 10日, 20日, 60日)
    ax1.plot(dates, df['MA5'], label='MA5', color='red')
    ax1.plot(dates, df['MA10'], label='MA10', color='orange')
    ax1.plot(dates, df['MA20'], label='MA20', color='green')
    ax1.plot(dates, df['MA60'], label='MA60', color='purple')
    # 绘制布林带上下轨
    ax1.plot(dates, df['BOLL_upper'], label='BOLL上轨', color='grey', linestyle='--')
    ax1.plot(dates, df['BOLL_lower'], label='BOLL下轨', color='grey', linestyle='--')
    # 日期轴格式化，不重叠
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig1.autofmt_xdate(rotation=45)
    ax1.legend(fontsize=8)
    ax1.grid(True, linestyle='--', alpha=0.5)
    price_chart_path = os.path.join(output_dir, "price_chart.png")
    fig1.savefig(price_chart_path, dpi=150, bbox_inches='tight')
    plt.close(fig1)

    # 绘制成交量走势图
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.set_title(f"{stock_name} 成交量", fontsize=12)
    ax2.set_xlabel("日期", fontsize=10)
    ax2.set_ylabel("成交量", fontsize=10)
    # 绘制成交量柱状图（使用涨跌颜色）
    vol_colors = None
    try:
        # 根据涨跌设置颜色：收盘价较前日上涨为红，下降为绿
        close_vals = df['close'].fillna(method='ffill')  # 填充NaN以便比较
        # 用前一日的收盘比对当前收盘
        prev_close = close_vals.shift(1)
        vol_colors = ['red' if close_vals[i] >= prev_close[i] else 'green' for i in range(len(close_vals))]
    except Exception:
        vol_colors = ['blue'] * len(volumes)  # 若数据不全则统一颜色
    ax2.bar(dates, volumes, color=vol_colors, label='成交量')
    # 绘制成交量均线 (5日, 10日, 20日, 60日)
    ax2.plot(dates, df['VOL_MA5'], label='MA5', color='orange')
    ax2.plot(dates, df['VOL_MA10'], label='MA10', color='purple')
    ax2.plot(dates, df['VOL_MA20'], label='MA20', color='brown')
    ax2.plot(dates, df['VOL_MA60'], label='MA60', color='blue')
    # 日期轴格式化，防止重叠
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig2.autofmt_xdate(rotation=45)
    ax2.legend(fontsize=8)
    ax2.grid(True, linestyle='--', alpha=0.5)
    volume_chart_path = os.path.join(output_dir, "volume_chart.png")
    fig2.savefig(volume_chart_path, dpi=150, bbox_inches='tight')
    plt.close(fig2)

    # 保存行情数据到 Excel 文件
    code_for_file = stock_code.replace('.', '_')
    excel_file_name = f"{code_for_file}_{start_date}_{end_date}.xlsx"
    excel_path = os.path.join(output_dir, excel_file_name)
    # 输出DataFrame到Excel（不包含NaN的技术指标列）
    df_to_save = df[['date', 'open', 'high', 'low', 'close', 'volume',
                     'MA5', 'MA10', 'MA20', 'MA60',
                     'BOLL_upper', 'BOLL_lower',
                     'VOL_MA5', 'VOL_MA10', 'VOL_MA20', 'VOL_MA60']].copy()
    df_to_save.to_excel(excel_path, index=False)
    return price_chart_path, volume_chart_path, excel_path