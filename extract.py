# adb shell 'cat /sdcard/Android/data/com.jjwxc.reader/SimpleHook/record/record.log' > record.log
# hook JSON and Cipher

import base64
import gzip
import json
import os

records = []
with open('record.log', 'r') as f:
    for line in f:
        r = json.loads(gzip.decompress(base64.b64decode(line.strip())))
        if r['type'] != 'Json' and r['type'] != 'Cipher':
            continue
        if r['type'] == 'Json' and json.loads(r['record'])['jsonType'] != 'JsonObjectCreate':
            continue
        records.append(r)

buf = dict()

for rec in records:
    if rec['type'] != 'Json':
        continue
    json_data = json.loads(rec['record'])['values']
    if 'chapterId' not in json_data:
        continue
    key = json_data['chapterId'] + "_" + json_data['chapterName'].replace("/", "_")
    if key not in buf or len(json_data['content']) > len(buf[key]['content']):
        buf[key] = json_data


os.makedirs('temp', exist_ok=True)
for key in buf:
    for rec in records:
        if rec['type'] != 'Cipher':
            continue
        data = json.loads(rec['record'])
        input_data = data['rawData']['Base64'].replace('\n', '')
        output_data = data['resultData']['BytesToString']
        if input_data == buf[key]['content']:
            buf[key]['content'] = output_data
            with open('temp/' + key + '.json', 'w', encoding='utf-8') as f:
                print("写入文件: " + key)
                json.dump(buf[key], f, ensure_ascii=False, indent=4)
                break
    else:
        print("未找到对应的输入数据: " + key)
