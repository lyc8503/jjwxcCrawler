# 晋江文学城 爬虫
# 使用安卓 App 的 Api, 仅可以获取免费章节


import logging
import requests
import json
from tenacity import retry, stop_after_attempt, wait_fixed
import time
from html2text import html2text


logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                    level=logging.INFO)

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 5.1; Lenovo) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                  "Chrome/39.0.0.0 Mobile Safari/537.36/JINJIANG-Android/206(Lenovo;android 5.1;Scale/2.0)",
    "Referer": "http://android.jjwxc.net?v=206"
}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_free_chapter(target_novel_id, target_chapter_id):
    r = requests.get("https://app-cdn.jjwxc.net/androidapi/chapterContent", params={
        "novelId": target_novel_id,
        "chapterId": target_chapter_id
    }, headers=headers, timeout=5)
    return r.json()


def get_vip_chapter(target_novel_id, target_chapter_id, target_chapter_name):
    try:
        with open(f"temp/{target_chapter_id}_{target_chapter_name}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"章节 {target_chapter_id} 获取失败: {e}")
        return {}


def write_file(s, end="\n"):
    with open("output.txt", "a+", encoding="utf-8") as f:
        f.write(s + end)


novel_id = input("请输入小说 ID: ")

# 获取小说信息
basic_info = requests.get("https://app-cdn.jjwxc.net/androidapi/novelbasicinfo", params={
    "novelId": novel_id
}, headers=headers).json()

logging.info(basic_info)

logging.info("书名: " + basic_info['novelName'])
logging.info("章节: " + str(basic_info['maxChapterId']) + ", 入V: " + str(basic_info['vipChapterid']))

# 全文免费的处理
if basic_info['vipChapterid'] == "0":
    basic_info['vipChapterid'] = str(int(basic_info['maxChapterId']) + 1)

# 写入基本信息
write_file(basic_info['novelName'] + "  " + basic_info['authorName'])
write_file(basic_info['novelSize'] + " 字  " + basic_info['novelChapterCount'] + " 章")
write_file("")
write_file("文章类型: " + basic_info['novelClass'])
write_file("作品视角: " + basic_info['mainview'])
write_file("作品风格: " + basic_info['novelStyle'])
write_file("所属系列: " + basic_info['series'])
write_file("内容标签: " + basic_info['novelTags'])
write_file("一句话简介: " + basic_info['novelIntroShort'])
write_file(basic_info['protagonist'] + " " + basic_info['costar'])
write_file("评分: " + basic_info['novelReviewScore'] +
           " 总积分: " + basic_info['novelScore'] +
           " 排名: " + basic_info['ranking'])

write_file("")
write_file("-----简介-----")
write_file(html2text(html2text(basic_info['novelIntro'])))


logging.info("获取目录...")
chapter_info = requests.get("https://app-cdn.jjwxc.net/androidapi/chapterList", params={
    "novelId": novel_id,
    "more": 0,
    "whole": 1
}, headers=headers).json()

logging.info("已经获取目录: " + str(len(chapter_info['chapterlist'])))

logging.info("尝试获取免费章节...")
for i in range(1, int(basic_info['vipChapterid'])):
    try:

        # 处理卷名 (chaptertype = 1)
        if chapter_info['chapterlist'][i - 1]['chaptertype'] == "1":
            write_file("### " + chapter_info['chapterlist'][i - 1]['chaptername'] + " ###")
            write_file("")
            chapter_info['chapterlist'].pop(i - 1)

        # 写入章节名
        write_file("----------")
        write_file("第 " + str(i) + " 章  " + chapter_info['chapterlist'][i - 1]['chaptername'] + "  " +
                   chapter_info['chapterlist'][i - 1]['chapterdate'])
        write_file(chapter_info['chapterlist'][i - 1]['chaptersize'] + " 字  " +
                   chapter_info['chapterlist'][i - 1]['chapterintro'])
        write_file("")

        # 处理被锁章节
        if chapter_info['chapterlist'][i - 1]['islock'] != '0':
            logging.warning("章节被锁.")
            write_file("章节被锁!")
            write_file("")
            continue

        logging.info("获取章节: " + str(i))
        content = get_free_chapter(novel_id, i)
        logging.debug(content)

        if "content" in content:
            write_file(html2text(html2text(content['content'])))
            if content['sayBody'] != "":
                write_file("作者有话说:")
                write_file(content['sayBody'])
                write_file("")
            logging.info("章节获取成功.")
        else:
            write_file("章节内容获取失败!")
            logging.warning("章节获取失败!")

        time.sleep(0.7)
    except Exception as e:
        write_file("内容获取失败: " + str(e))
        logging.exception(e)


logging.info("尝试获取V章...")

for i in range(int(basic_info['vipChapterid']), int(basic_info['maxChapterId']) + 1):
    try:
        if chapter_info['chapterlist'][i - 1]['chaptertype'] == "1":
            write_file("### " + chapter_info['chapterlist'][i - 1]['chaptername'] + " ###")
            write_file("")
            chapter_info['chapterlist'].pop(i - 1)

        write_file("----------")
        write_file("第 " + str(i) + " 章  " + chapter_info['chapterlist'][i - 1]['chaptername'] + "  " +
                   chapter_info['chapterlist'][i - 1]['chapterdate'])
        write_file(chapter_info['chapterlist'][i - 1]['chaptersize'] + " 字  " + chapter_info['chapterlist'][i - 1][
            'chapterintro'])
        write_file("")

        # 处理被锁章节
        if chapter_info['chapterlist'][i - 1]['islock'] != '0':
            logging.warning("章节被锁.")
            write_file("章节被锁!")
            write_file("")
            continue

        logging.info("获取章节: " + str(i))
        content = get_vip_chapter(novel_id, i, chapter_info['chapterlist'][i - 1]['chaptername'])
        logging.debug(content)

        if "content" in content:
            write_file(html2text(html2text(content['content'])))
            if content['sayBody'] != "":
                write_file("作者有话说:")
                write_file(content['sayBody'])
                write_file("")

            logging.info("章节获取成功.")
        else:
            write_file("章节获取失败: V章")
            logging.warning("章节获取失败!")

        # time.sleep(1)
    except Exception as e:
        write_file("章节获取失败: " + str(e))
        logging.exception(e)

logging.info("完成.")
