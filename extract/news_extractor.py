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
        sentence_context = []
        title_info = None
        # if not first_sent.endswith('。') or first_sent.endswith(('？', '！')):
        #     title_info, extraction_result = self
        for sent in news_sentences:
            use_ner = sent["use_ner"]
            sent = sent["sent"]
            if use_ner:
                # 先获取deal_type和financing_company信息
                sent_ctx = self.__get_sent_ctx(title_info, sentence_context)
                # 再提取结构化信息
                sentence_struct_info = self.__sent_extractor(sent, sent_ctx)
                extraction_results += self.__get_extraction_results(sentence_struct_info)
                # 最后更新deal_type和financing_company信息
                self.__update_sent_ctx(sentence_struct_info, sentence_context, title_info)
            res = self.__extract_purpose(sent, title_info, sentence_context)
            if res :
                extraction_results.append(res)
        return extraction_results
    
    # purpose_of_raised_funds
    def __extract_purpose(self, sent, title_info, sentence_context):
        match = self.__purpose_reobj.search(sent)
        if not match:
            return None
        start = match.span("prefix")[0]
        end = len(sent) - 1
        sent_ctx = self.__get_sent_ctx(title_info, sentence_context)
        deal_type = sent_ctx.get("deal_type")
        fc_name = sent_ctx.get("fc_name")
        res = None
        if deal_type:
            res = {"deal_type": deal_type, "purpose_of_raised_funds": sent[start:end]}
        if fc_name:
            res["financing_company"] = {"primary_name": fc_name}
        return res

    # TODO
    # [{"fc_name": ["deal_type1", "deal_type2"]}, {}]
    def __get_sent_ctx(self, title_info, sentence_context):
        sent_ctx = None
        if title_info:
            sent_ctx = title_info
        elif len(sentence_context) > 0:
            sent_ctx = sentence_context[-1]
        print("title_info: ", title_info)
        print("sentence_context: ", sentence_context)
        if sent_ctx:
            first_fc_name = next(iter(sent_ctx))
            print("first_fc_name: ", first_fc_name)
            deal_type = sent_ctx[first_fc_name][0]
            sent_ctx = {"deal_type": deal_type, "fc_name": first_fc_name}
        return sent_ctx
    
    def __update_sent_ctx(self, sentence_struct_info, sentence_context, title_info):
        # 子句的index_span到实际交易类型的映射
        clause_span2real_dts = sentence_struct_info["clause_span2real_dts"]
        # 子句的index_span到融资方信息的映射
        clause_span2fc_info = sentence_struct_info["clause_span2fc_info"]
        fc_name2dts = self.__get_fc_name2dts(clause_span2real_dts, clause_span2fc_info)
        if len(fc_name2dts) > 0:
            sentence_context.append(fc_name2dts)
    
    def __get_extraction_results(self, sentence_struct_info):
        extraction_results = []
        match_results = sentence_struct_info["match_results"]
        for mr in match_results:
            extraction_results.append(mr["struct"])
        return extraction_results
    
    def __get_fc_name2dts(self, clause_span2real_dts, clause_span2fc_info):
        fc_name2dts = {}
        for cl_span, real_dts in clause_span2real_dts.items():
            if len(real_dts) != 1:
                continue
            dt = real_dts[0][2]
            if cl_span in clause_span2fc_info:
                fc_name = clause_span2fc_info[cl_span]["fc_info"]["financing_company"]["primary_name"]
                if fc_name not in fc_name2dts:
                    fc_name2dts[fc_name] = [dt]
                else:
                    fc_name2dts[fc_name].append(dt)
            else:
                if None not in fc_name2dts:
                    fc_name2dts[None] = [dt]
                else:
                    fc_name2dts[None].append(dt)
        return fc_name2dts