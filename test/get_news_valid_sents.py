import re
P = (
    r"领投|"
    r"跟投|"
    r"继续加持|"
    r"由[^，,]*?([^联]合投|牵头)|"
    r"(担任|本轮|作?为)[^，,]*?(财务顾问|FA|独家顾问|融资顾问)|"
    r"筹集[^，,]*?(轮资金|融资)|"
    r"融资由[^，,]*?(构成|投资)|"
    r"投资(方|者|人|机构)(有|是|为|还?包括)|"
    r"(美元|美金|[^多]元|人民币|亿|万)[^，,：:；;)）（(]*?[投融]资|"
    r"估值[^，,：:；;)）（(]*?(美元|美金|元|人民币|亿|万)|"
    r"(美元|美金|元|人民币|亿|万)[^，,：:；;)）（(]*?估值|"
    r"(((Pre)?(A|B|C|D|E|F|种子|天使|本)轮)|等)投资(方|者|人|机构)|"
    r"(?<!累计)([投融]资[金总]?额|融资|筹集)[^，,：:；;)）（(]*?(美元|美金|元|人民币|亿|万)|"
    r"((累计|总共|连续)(获|完成)|(获得?|完成)两轮|公布|开启)[^，,：:；;)）（(]*?((美元|美金|元|人民币|亿|万)[^，,：:；;)）（(]*?|轮|略)[融投]资|"
    r"([公宣]布|取得|启动|完成|迎来|获得?|筹集|开启)[^，,：:；;)）（(]*?(美元|美金|元|人民币|亿|万)[^，,：:；;)）（(]*?[融投]资(后|之后)|"
    r"(?<!累计|总共|连续)(?<!共)([公宣]布(?!连续)|取得|启动|完成|迎来|获得?|筹集)(?!本轮|两轮|后续|的)[^，,：:；;)）（(]*?([融投]资(?!人|者|方|机构|之后|后)|投资(人|者|方|机构)[^，,]*[融投]资)"
)
P_PURPOSE = (
    r"(资金|融资)[\u4e00-\u9fa5，,]{0,10}((?<!应)(用(于|途[为，,]))|支持)|"
    r"投资[\u4e00-\u9fa5，,]{0,4}((?<!应)用(于|途[为，]))"
)
P_EXCLUDE = r"((完成|经历|发生|获得?|进行)[^,，]*?[\d]+|[亿万千百十两])((起|例|笔)|次融资)|[共达][^,，]*[\d][家种]"

P_TEST = r"投资|融资|领投|合投|跟投|加持|财务顾问"
RE_OBJ = re.compile(P, re.I)
RE_OBJ_PURPOSE = re.compile(P_PURPOSE, re.I)
RE_OBJ_EXCLUDE = re.compile(P_EXCLUDE, re.I)

def get_news_valid_sents(news: dict):
    title = news.get("title")
    content = news.get("content")
    res = []
    vtitle = _get_valid_sent(title)
    if vtitle:
        res.append(vtitle)
    res.append(vtitle)
    for sent in content:
        vsent = _get_valid_sent(sent)
        if vsent:
            res.append(vsent)
    return res

def _get_valid_sent(sent:str):
    if not sent: return None
    res = None
    if not RE_OBJ_EXCLUDE.search(sent):
        if RE_OBJ.search(sent):
            res = {"sent": sent, "use_ner": True}
        elif RE_OBJ_PURPOSE.search(sent):
            res = {"sent": sent, "use_ner": False}
    return res

def test(inputf, outputf):
    news_collection = inputf(1)
    results = []
    for news in news_collection:
        res = get_news_valid_sents(news)
        results.append(res)
    outputf(news_collection, results)