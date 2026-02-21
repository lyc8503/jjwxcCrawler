# adb shell 'cat /sdcard/Android/data/com.jjwxc.reader/SimpleHook/record/record.log' > record.log
# capture HAR using proxypin

import base64
import gzip
import json
import os

records = []
with open('record.log', 'r') as f:
    for line in f:
        r = json.loads(gzip.decompress(base64.b64decode(line.strip())))
        if r['type'] != 'Cipher':
            continue
        if json.loads(r['record'])['cryptType'] != 'Decrypt':
            continue
        records.append(r)

buf = dict()

for rec in records:
    # print(rec['type'], rec['subType'])
    data = json.loads(rec['record'])
    # input_data = data['rawData']['Base64']
    output_data = data['resultData']['BytesToString']
    try:
        json_data = json.loads(output_data)
        if type(json_data) != dict:
            continue
        if 'chapterId' not in json_data:
            continue
        buf[json_data['chapterId'] + "_" + json_data['chapterName']] = json_data
    except json.JSONDecodeError:
        pass


with open('capture.har', 'r', encoding='utf-8') as f:
    har = json.load(f)
    for entry in har['log']['entries']:
        url = entry['request']['url']
        if 'chapterContent' not in url:
            continue
        try:
            json_data = json.loads(entry['response']['content']['text'])
        except json.JSONDecodeError:
            continue
        if 'chapterId' not in json_data:
            continue
        if 'isvip' not in json_data or json_data['isvip'] == 0:
            continue
        buf[json_data['chapterId'] + "_" + json_data['chapterName']] = json_data


os.makedirs('temp', exist_ok=True)
for key in buf:
    for rec in records:
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
