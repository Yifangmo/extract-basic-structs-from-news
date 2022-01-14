from extract.extractor import DictExtractor
import re

class NewsDictExtractor(object):
    def __init__(self, rules):
        self.__sent_extractor = DictExtractor(*rules)
        self.__purpose_reobj = re.compile((
            r"(?P<prefix>([此该本]轮)?(资金|融资)[\u4e00-\u9fa5，,]{0,10}((?<!应)(用(于|途[为，,]))|支持)|"
            r"投资[\u4e00-\u9fa5，,]{0,4}((?<!应)用(于|途[为，])))"
        ))
        
    def __call__(self, news_sentences: 'list[dict]'):
        extraction_results = []
        # 融资方信息到其交易类型的映射、最近描述过的融资方
        sentence_context = {
            "fc_name2real_dts": {},
            "last_fc_name": None
        }
        for sent in news_sentences:
            use_ner = sent["use_ner"]
            sent = sent["sent"]
            if use_ner:
                # 先获取deal_type和financing_company信息
                sent_ctx = self.__get_sent_ctx(sentence_context)
                # 再提取结构化信息
                sentence_struct_info = self.__sent_extractor(sent, sent_ctx)
                extraction_results += self.__get_extraction_results(sentence_struct_info)
                # 最后更新deal_type和financing_company信息
                self.__update_sent_ctx(sentence_struct_info, sentence_context)
            purpose = self.__extract_purpose(sent, sentence_context)
            if purpose:
                extraction_results.append(purpose)
        return extraction_results

    # TODO
    # [{"fc_name": ["deal_type1", "deal_type2"]}, {}]
    def __get_sent_ctx(self, sentence_context: dict):
        sent_ctx = None
        print("sentence_context: ", sentence_context)
        fc_name2real_dts = sentence_context["fc_name2real_dts"]
        last_fc_name = sentence_context["last_fc_name"]
        if not last_fc_name:
            return sent_ctx
        # TODO
        # 该融资方有交易类型信息
        if len(fc_name2real_dts[last_fc_name])>0:
            if len(fc_name2real_dts) == 1:
                sent_ctx = {"deal_type": fc_name2real_dts[last_fc_name][0], "fc_name": last_fc_name}
            elif len(fc_name2real_dts) > 1:
                sent_ctx = {"deal_type": fc_name2real_dts[last_fc_name][-1], "fc_name": last_fc_name}
        else:
            sent_ctx = {"deal_type": None, "fc_name": last_fc_name}
        return sent_ctx
    
    def __update_sent_ctx(self, sentence_struct_info: dict, sentence_context: dict):
        # 子句的index_span到实际交易类型的映射
        clause_span2real_dts = sentence_struct_info["clause_span2real_dts"]
        # 子句的index_span到融资方信息的映射
        clause_span2fc_info = sentence_struct_info["clause_span2fc_info"]
        fc_name2real_dts = sentence_context["fc_name2real_dts"]
        for cl_span, fc_info in clause_span2fc_info.items():
            fc_name = fc_info["fc_info"]["financing_company"]["primary_name"]
            sentence_context["last_fc_name"] = fc_name
            if fc_name not in fc_name2real_dts:
                fc_name2real_dts[fc_name] = []
            if cl_span in clause_span2real_dts:
                real_dts = clause_span2real_dts[cl_span]
                for real_dt in real_dts:
                    fc_name2real_dts[fc_name].append(real_dt[2])
    
    def __get_extraction_results(self, sentence_struct_info):
        extraction_results = []
        match_results = sentence_struct_info["match_results"]
        for mr in match_results:
            extraction_results.append(mr["struct"])
        return extraction_results
    
    # purpose_of_raised_funds
    def __extract_purpose(self, sent, sentence_context:dict):
        match = self.__purpose_reobj.search(sent)
        if not match:
            return None
        start = match.span("prefix")[0]
        end = sent.find("。", start)
        end = len(sent) - 1 if end == -1 else end
        sent_ctx = self.__get_sent_ctx(sentence_context)
        deal_type = sent_ctx.get("deal_type")
        fc_name = sent_ctx.get("fc_name")
        res = None
        if deal_type:
            res = {"deal_type": deal_type, "purpose_of_raised_funds": sent[start:end]}
        if fc_name:
            res["financing_company"] = {"primary_name": fc_name}
        return res