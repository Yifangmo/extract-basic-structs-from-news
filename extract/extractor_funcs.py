"""DictExtrator所调用的函数
"""
from .labelstr import *
import re

def get_field_value(sent: str, entities_index2original: dict, span: 'list|str'):
    """获取实体句子的span所对应的在原句子的值

    Args:
        sent (str): 原句子
        entities_index2original (dict): span映射信息
        span (list|str): 一个或多个span

    Returns:
        list|str: span对应的一个或多个值
    """
    res = None
    if isinstance(span, list):
        res = []
        for sp in span:
            if sp not in entities_index2original:
                print("get_field_values 实体索引映射错误：({},{})".format(sp[0], sp[1]))
                continue
            sent_idx_span = entities_index2original[sp]
            res.append(sent[sent_idx_span[0]:sent_idx_span[1]])
    else:
        sent_idx_span = entities_index2original[span]
        res = sent[sent_idx_span[0]: sent_idx_span[1]]
    return res

def get_classified_alias(alias: set):
    """对别名分类

    Args:
        alias (set): 别名的集合

    Returns:
        dict: primary_name、english_name（如果有）、full_name（如果有）的dict
    """
    invalid_reobj = re.compile(r"\d{3,}")
    alias = {i for i in alias if not invalid_reobj.search(i)}
    en_reobj = re.compile(r"([A-Za-z\d]{3,}(?:\s[A-Za-z\d]+)*)")
    english_names = {n for n in alias if en_reobj.fullmatch(n)}
    full_names = {n for n in alias if n.endswith(("公司","集团","基金"))}
    primary_names = alias - english_names - full_names
    if len(primary_names) == 0:
        primary_names = full_names
    if len(primary_names) == 0:
        primary_names = english_names
    names = {}
    if len(primary_names) > 0:
        names["primary_name"] = sorted(primary_names, key=lambda n: (len(n), n))[0]
    if len(english_names) > 0:
        names["english_name"] = sorted(english_names, key=lambda n: (len(n), n), reverse=True)[0]
    if len(full_names) > 0:
        names["full_name"] = sorted(full_names, key=lambda n: (len(n), n), reverse=True)[0]
    return names

def get_clause_span(sent: str, token_low_index: int, token_high_index: int, unique_sep:str = None, *additional_seps: str):
    """获取某个范围所在子句的位置

    Args:
        sent (str): 句子
        token_low_index (int): 索引范围头
        token_high_index (int): 索引范围尾
        unique_sep (str, optional): 使用指定的唯一子句分隔符. Defaults to None.

    Returns:
        tuple: 范围所在子句的索引范围
    """
    separators = ["；", "，", "。", "】", "【"]
    if unique_sep:
        separators = [unique_sep]
    elif additional_seps:
        separators += additional_seps
    l = len(sent)
    begin = None
    end = None
    for i in range(token_low_index, -1, -1):
        if sent[i] in separators:
            begin = i+1
            break
    for i in range(token_high_index, l, 1):
        if sent[i] in separators:
            end = i
            break
    begin = begin if begin else 0
    end = end if end else l
    return begin, end

def divide_real_dts_span(sent: str, idxspan2real_dts: dict, real_dt2label_dts: dict, separators: list):
    """为出现交易类型的子句划分索引范围，子句间的分隔符是标点符号。返回的是某个子句在整个句子中的索引范围到该子句所含交易类型的映射。

    Args:
        sent (str): 句子
        idxspan2real_dts (dict): 子句span到实际交易类型映射
        real_dt2label_dts (dict): 交易类型实体信息
        separators (list): 分隔符列表，索引越低的优先作为划分子句的分隔符

    Returns:
        dict: 新的子句span到实际交易类型映射
    """
    if len(separators) == 0:
        return idxspan2real_dts
    separator = separators.pop(0)
    new_idxspan2real_dts = {}
    for span, real_dts in idxspan2real_dts.items():
        if len(real_dts) == 1:
            new_idxspan2real_dts[span] = real_dts
            continue
        for real_dt in real_dts:
            label_dts = real_dt2label_dts[real_dt]
            new_span = get_clause_span(sent, label_dts[0][0], label_dts[0][1], separator)
            if new_span not in new_idxspan2real_dts:
                new_idxspan2real_dts[new_span] = [real_dt]
            else:
                new_idxspan2real_dts[new_span].append(real_dt)

    return divide_real_dts_span(sent, new_idxspan2real_dts, real_dt2label_dts, separators)

def normalize_sentence(sent: str):
    """去除无关紧要的空白字符、引号等；将英文标点转换为中文标点；将标签指示符转为书名号

    Args:
        sent (str): 句子
    Returns:
        str: 规范化后的句子
    """
    def repl(m):
        dic = {1: "", 2: "，", 3: "；", 4: "：", 5: "（", 6: "）", 7: "《", 8: "》"}
        for i in range(1, 7):
            if m.group(i):
                return dic[i]
    # 处理标题的空格
    # if not sent.endswith("。") or sent.endswith(("？", "！")):
        # sent = re.sub(r"(?<![A-Za-z])\s(?![A-Za-z])", "，", sent)
        # pass
    return re.sub(r"((?<![A-Za-z])\s|\s(?![A-Za-z])|“|”|「|」|‘|’|\")|(,)|(;)|(:)|(\()|(\))|(<)|(>)", repl, sent)


def get_financing_company_info(match_result, sent, entities_index2original, alias, total_labels_used):
    """从所有的match_result中获取fc信息
    """
    financing_company_info = {}
    for mr in match_result:
        mr_struct = mr["struct"]
        if "financing_company" in mr_struct:
            fc_span = mr_struct["financing_company"]
            del mr_struct["financing_company"]
            total_labels_used.add(fc_span)
            fc_name = get_field_value(sent, entities_index2original, fc_span)
            fc_names = get_classified_alias(alias[fc_name])
            fc = {}
            for k, v in fc_names.items():
                fc[k] = v
            bp = None
            if "business_profile" in mr_struct:
                bp_span = mr_struct["business_profile"]
                del mr_struct["business_profile"]
                total_labels_used.add(bp_span)
                bp = get_field_value(sent, entities_index2original, bp_span)
            if fc_name not in financing_company_info or fc_name in financing_company_info and bp:
                financing_company_info[fc_name] = {"business_profile": bp, "financing_company": fc} if bp else {"financing_company": fc}
    return financing_company_info

def forward_extend_dtspan(sent, labels_indexes, idxspan2real_dts):
    """使前面未被dt_span覆盖的时间标签被其后面的dt_span覆盖，因为前面的时间很大可能是其后real_dt相关的时间
    """
    for i, li in enumerate(labels_indexes):
        if li[2] == LABEL_DISCLOSE_DATE or li[2] == LABEL_OCCURRENCE_DATE:
            time_span = get_clause_span(sent, li[0], li[1])
            spans = sorted(idxspan2real_dts.keys())
            for j, span in enumerate(spans):
                real_dts = idxspan2real_dts[span]
                if span[0] <= time_span[0] and time_span[1] <= span[1]:
                    break
                if j == 0 and span[0] > time_span[1] or \
                    j > 0 and spans[j-1][1] < time_span[0] and span[0] > time_span[1]:
                    del idxspan2real_dts[span]
                    idxspan2real_dts[(time_span[0], span[1])] = real_dts
                    break

def backward_extend_dtspan(sent, idxspan2real_dts, real_dt2label_dts, dt_amount_pair):
    """向后扩展span，使所有span邻接，合并以"、"分割但无金额的span
    """
    spans = sorted(idxspan2real_dts.keys())
    for i, span in enumerate(spans):
        real_dts = idxspan2real_dts[span]
        if i == len(spans)-1:
            del idxspan2real_dts[span]
            idxspan2real_dts[(span[0], len(sent))] = real_dts
            break
        if span[1] != spans[i+1][0] - 1:
            del idxspan2real_dts[span]
            idxspan2real_dts[(span[0], spans[i+1][0] - 1)] = real_dts
            continue
        if i > 0 and span[0] == spans[i-1][1] + 1 and sent[spans[i-1][1]] == "、":
            has_amount = False
            for real_dt in real_dts:
                if real_dt2label_dts[real_dt][0] in dt_amount_pair:
                    has_amount = True
                    break
            if not has_amount:
                pre_real_dts = idxspan2real_dts[spans[i-1]]
                del idxspan2real_dts[span]
                del idxspan2real_dts[spans[i-1]]
                idxspan2real_dts[(spans[i-1][0], span[1])] = real_dts + pre_real_dts
       
def get_real_dt2label_dts(sent, labels_indexes, repl_deal_type_reobj, invalid_repl_dt_reobj):
    """获取实际交易类型到交易类型实体spans（可能一个实际交易类型对应多个交易类型实体）的映射、交易类型实体与金额对
    """
    label_dt2repl_dt = {}
    repl_dt2real_dt = {}
    dt_amount_pair = {}
    for i, li in enumerate(labels_indexes):
        label_content = sent[li[0]:li[1]]
        if li[2] == LABEL_DEAL_TYPE:
            repl_dt = repl_deal_type_reobj.sub("", label_content)
            # 此类交易类型实体只用于匹配模板来获取融资方信息，不作为实际交易事件，也不为之划分span
            if invalid_repl_dt_reobj.search(repl_dt):
                continue
            # 励销云宣布完成新一轮2000万美元B轮融资
            if i > 1 and labels_indexes[i-1][2]==LABEL_AMOUNT and labels_indexes[i-2][2]==LABEL_DEAL_TYPE:
                pre_label_dt_content = sent[labels_indexes[i-2][0]:labels_indexes[i-2][1]]
                pre_li_span = (labels_indexes[i-2][0], labels_indexes[i-2][1])
                if pre_li_span in label_dt2repl_dt:
                    pre_repl_dt = label_dt2repl_dt[pre_li_span]
                    # 新一轮2000万美元B轮融资
                    if re.search(r"[A-Za-z]", repl_dt):
                        # 将原有的 新一 替换为 B
                        label_dt2repl_dt[(li[0],li[1])] = repl_dt
                        label_dt2repl_dt[pre_li_span] = repl_dt
                        # 删除原有的repl_dt，避免同一交易事件（real_dt）有多个repl_dt
                        del repl_dt2real_dt[pre_repl_dt]
                        # 将实际交易类型由新一轮替换为B轮融资
                        if label_content.endswith("融资") or not pre_label_dt_content.endswith("融资"):
                            repl_dt2real_dt[repl_dt] = label_content
                    # B轮2000万美元新融资 | B轮2000万美元融资
                    else:
                        label_dt2repl_dt[(li[0],li[1])] = pre_repl_dt
                        # 将实际交易类型由B轮替换为B轮融资
                        if label_content.endswith("融资") and not pre_label_dt_content.endswith("融资"):
                            repl_dt2real_dt[pre_repl_dt] = pre_label_dt_content + label_content
                    continue
            # "B+轮战略融资" 和 "B+轮投资"
            if repl_dt in repl_dt2real_dt:
                label_dt2repl_dt[(li[0], li[1])] = repl_dt
                pre_real_dt = repl_dt2real_dt[repl_dt]
                ult_real_dt = label_content
                # 优先取融资结尾的，再取长度更长的
                if pre_real_dt.endswith("融资"):
                    ult_real_dt = pre_real_dt
                if pre_real_dt != label_content:
                    if label_content.endswith("融资") and len(pre_real_dt) < len(label_content):
                        ult_real_dt = label_content
                else:
                    if len(pre_real_dt) >= len(label_content):
                        ult_real_dt = pre_real_dt
                if ult_real_dt != pre_real_dt:
                    repl_dt2real_dt[repl_dt] = ult_real_dt
                continue
            
            if i > 0 and labels_indexes[i-1][2]==LABEL_AMOUNT and li[0] - labels_indexes[i-1][1] < 2:
                dt_amount_pair[(li[0],li[1])] = (labels_indexes[i-1][0],labels_indexes[i-1][1])
            
            label_dt2repl_dt[(li[0], li[1])] = repl_dt
            repl_dt2real_dt[repl_dt] = label_content
    real_dt2label_dts = {}
    for label_dt, repl_dt in label_dt2repl_dt.items():
            real_dt = repl_dt2real_dt[repl_dt]
            if real_dt not in real_dt2label_dts:
                real_dt2label_dts[real_dt] = [label_dt]
            else:
                real_dt2label_dts[real_dt].append(label_dt)
    return real_dt2label_dts, dt_amount_pair
