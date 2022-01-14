import csv
import re

def separate_long_sentence(sen: str):
    sen = sen.strip(',')
    sen = sen.strip('，')
    invalid_sen_li = [sen]
    valid_sen_li = []
    while len(invalid_sen_li) != 0:
        s = invalid_sen_li.pop()
        comma_matches = list(re.finditer("[,，]",s))
        comma_count = len(comma_matches)
        if comma_count == 0:
            continue
        sen_separate_idx = comma_matches[comma_count // 2].start()
        first = s[:sen_separate_idx]
        second = s[sen_separate_idx+1:]
        if len(first) > 256:
            invalid_sen_li.append(first)
        else:
            valid_sen_li.append(first)
        if len(second) > 256:
            invalid_sen_li.append(second)
        else:
            valid_sen_li.append(second)
    return valid_sen_li
    
def validate_sentence(sen: str):
    if len(sen) > 256:
        return separate_long_sentence(sen)
    else:
        return [sen]
    
def get_news_collection(count=0):
    news_collection = []
    with open("./input/融资合集_news.csv") as inf:
        reader = csv.reader(inf)
        next(reader)
        i = 0
        for row in reader:
            i += 1
            if i > count:
                break
            title = row[0]
            content = []
            for seg in re.split("\n\n", row[1]):
                if seg == "":
                    continue
                for sen in re.split("。", seg):
                    vsen = validate_sentence(sen)
                    for s in vsen:
                        if s != "":
                            content.append(s + "。")
            news_collection.append({"title": title, "content": content})
    return news_collection

def get_test_data():
    data = []
    with open("./input/test_sample.txt") as inf:
        for row in inf:
            if row.startswith('#'):
                break
            if not row.startswith('-'):
                data.append({"sent": row.strip('\n'), "use_ner": True})
    return data


