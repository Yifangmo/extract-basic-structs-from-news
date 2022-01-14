#!/usr/bin/env python
from test.get_news_valid_sents import test
from test.get_news_from_flie import get_news_collection
from test.write_result import write_handler
from test.write_result import extract_handler

def main():
    # test(get_news_collection, write_handler)
    test(get_news_collection, extract_handler)
    
if __name__ == "__main__":
    main()