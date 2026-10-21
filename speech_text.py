"""只校验真实识别候选中的明确故事请求，保留原始识别供核查。"""
import re


def select_voice_text(payload):
    alternatives = payload.get('alternatives', [])
    texts = [item.get('text', '').replace(' ', '').strip() for item in alternatives]
    raw = texts[0] if texts else payload.get('text', '').replace(' ', '').strip()
    result = {'raw': raw, 'text': raw, 'reason': ''}
    # 不把否定、转述、引用分析或叙述变成助手讲故事的请求。
    if re.search(r'不|别|勿|听我|我讲|我来|分析|解释|引用|意思|含义|是谁|推荐|书名|标题|写了|听了|看了|读了|过|昨天|以前|吗|？|\?', raw):
        return result
    pattern = r'((?:请|能不能|可以|麻烦你)(?:给我)?)(?:讲|将)((?:一个|个|一段)[^，。？！!?]{0,12}故事)[。！!]*'
    for text in texts:
        match = re.fullmatch(pattern, text)
        if not match:
            continue
        suffix = match.group(2)
        top = raw.rstrip('。！!')
        if not top.endswith(suffix):
            continue
        prefix = top[:-len(suffix)]
        if not 1 <= len(prefix) <= 3 or re.search(r'我|你|他|她|它|这|那|听|看|读|写', prefix):
            continue
        chosen = match.group(1) + '讲' + suffix
        if chosen != raw:
            result.update(text=chosen, reason='同段真实候选含明确故事请求，正文一致；将/讲同音校验')
        return result
    return result
