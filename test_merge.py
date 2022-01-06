#!/usr/bin/env python
from test_extract import test_merger
import extract.news_extractor as news_extractor
from merge_.merger import DictMerger
import extract.rule.rules as rule
import inspect

def get_test_data():
    data = []
    with open("./input/test_sample.txt") as inf:
        for row in inf:
            if row.startswith('#'):
                break
            if not row.startswith('-'):
                data.append({"sent": row.strip('\n'), "use_ner": True})
    return data

def test_news_extractors(sents):
    newsextra = news_extractor.NewsDictExtractor([i[1]() for i in inspect.getmembers(rule, inspect.isclass) if i[0].startswith("Rule")])
    print("sents: ", sents)
    extr_res = newsextra(sents)
    merger = DictMerger()
    merged = merger(extr_res)
    print(merged)
    

if __name__ == "__main__":
    sents = get_test_data()
    # test_merger(sents)
    test_news_extractors(sents)
    pass


