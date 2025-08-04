import csv
import json

# 读取 csv 文件并构建数据结构
data_dict = {}
csv_file_path = 'data.csv'
with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
    reader = csv.DictReader(csv_file)
    for row in reader:
        name = row.get('name')
        ts_code = row.get('ts_code')
        industry = row.get('industry')
        if name:
            data_dict[name] = {
                'ts_code': ts_code,
                'industry': industry
            }

# 将构建好的数据写入 jsonl 文件
jsonl_file_path = 'stock_info.jsonl'
with open(jsonl_file_path, 'w', encoding='utf-8') as jsonl_file:
    for name, info in data_dict.items():
        json_line = {
            'name': name,
            'ts_code': info['ts_code'],
            'industry': info['industry']
        }
        jsonl_file.write(json.dumps(json_line, ensure_ascii=False) + '\n')