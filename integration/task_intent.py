"""仅为语音入口识别用户明确委托助手执行的任务，不改普通陪伴聊天。"""
import re


def assistant_task_requested(history):
    if not history or history[-1].get('role') != 'user':
        return False
    text = history[-1].get('content', '').strip()
    if re.search(r'[“”「」『』"]|(?:分析|解释).{0,8}(?:句子|这句话|台词)', text):
        return False
    for clause in reversed(re.split(r'[，,。！？!?；;]', text)):
        if re.search(r'不要.{0,6}建议|别.{0,6}建议|不需要.{0,6}建议|只想.{0,4}(?:聊|倾诉)|(?:别|不要|不用).{0,4}(?:帮我|替我|给我|为我)', clause):
            return False
        if re.search(r'(?:帮我|替我|给我|为我).{0,4}(?:想|推荐|安排|规划|解释|列|选|写|设计|总结|建议)', clause):
            return True
    return False


VOICE_TASK_PROMPT = '''你是心语，一位温柔、务实的AI助手。本轮用户已经明确把一个具体任务交给你，请现在完成它。
response_text先直接给出用户能采用的具体内容，再用一句话解释。推荐要给实际选项，规划要给实际安排，解释要给实际解释。
不要只说“我来帮忙”“你来说”“你想从哪里开始”，不要让用户重复已经说清楚的任务。温柔语气不能代替执行。
信息不足但可以提供一般性建议时，先给简短可选方案并说明假设；涉及专业高风险问题时如实说明边界，不编造。
保持两三句自然中文，不输出分析过程或规则。'''
