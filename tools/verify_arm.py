"""使用Unicorn执行ADS生成的真实A32机器码，不替代AXD截图和实机测试。"""
import hashlib
import json
import random
import re
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_CPSR

ROOT = Path(__file__).resolve().parents[1]
REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
        UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
        UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_CPSR]
NAMES = ['r' + str(i) for i in range(12)] + ['sp', 'lr', 'pc', 'cpsr']


def symbols(elf):
    offset = struct.unpack_from('<I', elf, 32)[0]
    entry_size, count = struct.unpack_from('<HH', elf, 46)
    sections = [struct.unpack_from('<10I', elf, offset + i * entry_size) for i in range(count)]
    result = {}
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        table = elf[strings[4]:strings[4] + strings[5]]
        for pos in range(section[4], section[4] + section[5], section[9]):
            name, value, _, _, _, _ = struct.unpack_from('<IIIBBH', elf, pos)
            result[table[name:].split(b'\0')[0].decode('ascii', errors='replace')] = value
    return result


def instructions(path):
    result = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if re.match(r'^\s+(mov|cmp|beq|ldrsh|rsblt|add|subs|bne|bx|mul)', line, re.I):
            result.append(re.sub(r'\s+', '', line.split(';')[0]).lower())
    return result


def main():
    elf = (ROOT / 'arm/pcm_gate_verify.axf').read_bytes()
    code = (ROOT / 'arm/pcm_gate_verify.bin').read_bytes()
    addresses = symbols(elf)
    if instructions(ROOT / 'arm/pcm_gate.S') != instructions(ROOT / 'arm/pcm_gate_ads.s'):
        raise SystemExit('GNU与ADS版本指令不一致')
    cases = [('正常', [1000, -1000] * 160, 500), ('阈值下方', [499, -499] * 160, 500),
             ('阈值相等', [500, -500] * 160, 500), ('静音', [0] * 320, 500),
             ('PCM边界', [-32768, 32767, 0, -1], 500), ('空帧', [], 500),
             ('零门限', [0], 0), ('最大门限', [-32768], 32768),
             ('最长合法帧', [-32768] * 65535, 32768)]
    rng = random.Random(1132026)
    for i in range(100):
        cases.append((f'随机{i}', [rng.randint(-32768, 32767) for _ in range(rng.randint(0, 320))], rng.randint(0, 32768)))
    results = []
    first_trace = []
    for index, (name, samples, threshold) in enumerate(cases):
        emulator = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        emulator.mem_map(0x10000, 0x1000)
        emulator.mem_write(0x10000, code)
        emulator.mem_map(0x20000, 0x40000)
        emulator.mem_map(0x70000, 0x20000)
        pcm = struct.pack('<' + 'h' * len(samples), *samples)
        if pcm:
            emulator.mem_write(0x20000, pcm)
        emulator.reg_write(UC_ARM_REG_SP, 0x7f000)
        for register in REGS[4:12]:
            emulator.reg_write(register, 0x12345678)
        count = [0]

        def hook(uc, address, size, _):
            count[0] += 1
            if index == 0 and len(first_trace) < 30:
                first_trace.append({label: uc.reg_read(register) for label, register in zip(NAMES, REGS)})

        emulator.hook_add(UC_HOOK_CODE, hook)
        emulator.reg_write(UC_ARM_REG_R0, 0x20000)
        emulator.reg_write(UC_ARM_REG_R1, len(samples))
        emulator.reg_write(UC_ARM_REG_LR, 0x80000)
        emulator.emu_start(addresses['pcm_sum_abs_arm'], 0x80000, count=1000000)
        actual = emulator.reg_read(UC_ARM_REG_R0)
        sum_registers = {label: emulator.reg_read(register) for label, register in zip(NAMES, REGS)}
        sum_count = count[0]
        emulator.reg_write(UC_ARM_REG_R1, len(samples))
        emulator.reg_write(UC_ARM_REG_R2, threshold)
        emulator.reg_write(UC_ARM_REG_LR, 0x80000)
        emulator.emu_start(addresses['pcm_gate_arm'], 0x80000, count=100)
        active = emulator.reg_read(UC_ARM_REG_R0)
        expected = sum(abs(value) for value in samples)
        expected_gate = int(bool(samples) and expected >= len(samples) * threshold)
        preserved = all(emulator.reg_read(register) == 0x12345678 for register in REGS[4:12])
        unchanged = not pcm or bytes(emulator.mem_read(0x20000, len(pcm))) == pcm
        passed = (actual == expected and active == expected_gate and preserved and unchanged
                  and emulator.reg_read(UC_ARM_REG_PC) == 0x80000 and emulator.reg_read(UC_ARM_REG_SP) == 0x7f000)
        results.append({'case': name, 'count': len(samples), 'threshold': threshold,
                        'expected_sum': expected, 'arm_sum': actual,
                        'expected_gate': expected_gate, 'arm_gate': active,
                        'sum_instructions': sum_count, 'gate_instructions': count[0] - sum_count,
                        'callee_saved_preserved': preserved, 'input_memory_unchanged': unchanged,
                        'sum_return_registers': sum_registers,
                        'gate_return_registers': {label: emulator.reg_read(register) for label, register in zip(NAMES, REGS)},
                        'passed': passed})
    out = ROOT / 'records/ARM指令验证'
    out.mkdir(parents=True, exist_ok=True)
    report = {'environment': 'Windows电脑上的Unicorn A32指令执行，非AXD，非T113实机，不报告板端时间或周期',
              'code_sha256': hashlib.sha256(code).hexdigest(), 'axf_sha256': hashlib.sha256(elf).hexdigest(),
              'gnu_ads_instructions_equal': True, 'seed': 1132026, 'cases': results,
              'all_passed': all(case['passed'] for case in results)}
    (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'register_trace.json').write_text(json.dumps({'input_pcm16_head': [1000, -1000] * 4,
        'input_memory_head_hex': struct.pack('<8h', *([1000, -1000] * 4)).hex(), 'before_instruction': first_trace}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"ARM实际机器码验证：{sum(case['passed'] for case in results)}/{len(results)}；记录：{out}")
    if not report['all_passed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
