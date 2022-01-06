from extract import news_extractor
from extract.rule import rules
from merge_.merger import DictMerger
import csv
import inspect
import xlsxwriter
import json

# news_collection: [{"title": "", "content": [""]}], result: [[{"sent": "", "use_ner": True}],[]]
def write_handler(news_collection, result):
    sent_sep = "\n--------\n"
    with open("./output/valid_sentences.csv", "w") as outf:
        writer = csv.writer(outf)
        # writer.writerow(["news_id", "title", "content", "valid_sentences_usener", "valid_sentences_nousener"])
        writer.writerow(["news_id", "title", "valid_sentences_usener", "valid_sentences_nousener"])
        rows = []
        for i, news in enumerate(news_collection, 1):
            row = []
            row.append(str(i))
            res = result[i-1]
            row.append(news.get("title"))
            # row.append(sent_sep.join(news.get("content")))
            res_usener_row = []
            res_nousener_row = []
            for i in res:
                if i["use_ner"]:
                    res_usener_row.append(i["sent"])
                else:
                    res_nousener_row.append(i["sent"])
            row.append(sent_sep.join(res_usener_row))
            row.append(sent_sep.join(res_nousener_row))
            rows.append(row)
        writer.writerows(rows)
    pass

def extract_handler(news_collection, result):
    sent_sep = "\n--------\n"
    newsextra = news_extractor.NewsDictExtractor([i[1]() for i in inspect.getmembers(rules, inspect.isclass) if i[0].startswith("Rule")])
    merger = DictMerger()
    
    rows_data = {
        "news_id": [],
        "title": [],
        "sents_usener": [],
        "sents_nousener": [],
        "merged_structs": []
    }
    for i, res in enumerate(result):
        news = news_collection[i]
        rows_data["news_id"].append(str(i + 1))
        rows_data["title"].append(news["title"])
        sents_usener = []
        sents_nousener = []
        for r in res:
            if r["use_ner"]:
                sents_usener.append(r["sent"])
            else:
                sents_nousener.append(r["sent"])
        rows_data["sents_usener"].append(sent_sep.join(sents_usener))
        rows_data["sents_nousener"].append(sent_sep.join(sents_nousener))
        extr_structs = newsextra(res)
        merged_structs = merger(extr_structs)
        rows_data["merged_structs"].append(json.dumps(merged_structs, ensure_ascii=False, indent=4))
    write_xlsx(rows_data)
    
def write_xlsx(rows_data):
    wb = xlsxwriter.Workbook("./output/merge_result.xlsx")
    sh1 = wb.add_worksheet()
    sh1.set_column(0, 0, 8)
    sh1.set_column(1, 1, 25)
    sh1.set_column(2, 3, 35)
    sh1.set_column(4, 4, 50)
    str_format = wb.add_format(
        {'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
    sh1.write_row(0, 0, rows_data.keys(), str_format)
    col_idx = 0
    for k, v in rows_data.items():
        sh1.write_column(1, col_idx, v, str_format)
        col_idx += 1
    wb.close()
    
