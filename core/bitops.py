# -*- coding: utf-8 -*-
"""
core/bitops.py
计算机导论大作业 —— 补码加减法运算引擎（最小闭环版）

设计原则
--------
1. 纯标准库，不依赖任何第三方包（tkinter 也不在这里导入），便于单元测试与对拍。
2. 所有步骤都产出"快照"，供界面层（ui/）与可视化层（viz/）直接消费，
   三层只通过 add_steps() / to_twos_complement_steps() 返回的 dict 通信。
3. 位宽支持 8 / 16，符号位为最高位，负数用补码表示。

对外接口
--------
    to_bits(value, width)                  -> list[int]   十进制 -> 补码位串
    bits_to_int(bits)                      -> int         补码位串 -> 有符号十进制
    to_twos_complement_steps(value, width) -> list[dict]  求补过程（原码->反码->补码）
    add_steps(a, b, width)                 -> dict        完整加法过程 + 每步快照
    check_overflow(a, b, result, width)    -> bool        溢出判定（独立函数，便于对拍）
"""

from __future__ import annotations

# ---------------------------------------------------------------- 基础工具

def mask_of(width: int) -> int:
    """返回 width 位全 1 的掩码，例如 width=8 -> 0b11111111。"""
    return (1 << width) - 1


def to_bits(value: int, width: int) -> list:
    """
    十进制整数 -> width 位补码位串（高位在前）。

    例：to_bits(-5, 8) -> [1, 1, 1, 1, 1, 0, 1, 1]
    """
    if not (-(1 << (width - 1)) <= value <= (1 << (width - 1)) - 1):
        raise ValueError(f"{value} 超出 {width} 位补码可表示范围 "
                         f"[{-(1 << (width - 1))}, {(1 << (width - 1)) - 1}]")
    raw = value & mask_of(width)          # 取补码（Python 负数按无限位补码运算，与掩码后即定长补码）
    return [(raw >> (width - 1 - i)) & 1 for i in range(width)]


def bits_to_int(bits: list) -> int:
    """补码位串 -> 有符号十进制（最高位是符号位）。"""
    width = len(bits)
    raw = 0
    for bit in bits:
        raw = (raw << 1) | bit
    if raw & (1 << (width - 1)):          # 符号位为 1 -> 负数，按补码还原
        return raw - (1 << width)
    return raw


def bits_to_str(bits: list) -> str:
    """位串 -> '1011 0110' 这种便于阅读的字符串（每 4 位空一格）。"""
    s = "".join(str(b) for b in bits)
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


# ---------------------------------------------------------------- 求补过程

def to_twos_complement_steps(value: int, width: int) -> list:
    """
    演示"原码 -> 反码 -> 补码"的求补过程。

    正数：原码即补码，一步结束。
    负数：原码（符号位 1 + 绝对值）-> 各数值位取反（反码）-> 末位加一（补码）。

    返回步骤列表，每步：
        {"title": 步骤名, "bits": 位串, "note": 中文说明}
    """
    steps = []
    if value >= 0:
        bits = to_bits(value, width)
        steps.append({
            "title": "正数：原码即补码",
            "bits": bits,
            "note": f"{value} 是正数，符号位为 0，原码与补码相同",
        })
        return steps

    # 边界特例：最小负数没有原码/反码表示
    # -128 的绝对值 128 需要 8 个数值位，再加 1 位符号位共 9 位，超出 8 位位宽，
    # 所以 8 位下 -128 只能直接写补码 1000 0000（这也是"补码比原码多表示一个数"的原因）。
    if value == -(1 << (width - 1)):
        bits = to_bits(value, width)
        steps.append({
            "title": "① 最小负数特例",
            "bits": bits,
            "note": (f"{value} 在 {width} 位下没有原码和反码表示"
                     f"（|{value}|={-value} 需要 {width - 1} 个数值位，再加符号位就超宽），"
                     f"补码直接规定为 1000 0000"),
        })
        steps.append({
            "title": "② 直接取补码",
            "bits": bits,
            "note": "这就是补码能比原码多表示一个负数的原因：0 只有一种表示，省下的编码给了最小负数",
        })
        return steps

    abs_val = -value
    sign_and_mag = [1] + [(abs_val >> (width - 2 - i)) & 1 for i in range(width - 1)]
    steps.append({
        "title": "① 写原码",
        "bits": sign_and_mag,
        "note": f"{value} 是负数：符号位写 1，数值位写 |{value}|={abs_val} 的二进制",
    })

    inverted = [sign_and_mag[0]] + [1 - b for b in sign_and_mag[1:]]
    steps.append({
        "title": "② 数值位取反（反码）",
        "bits": inverted,
        "note": "符号位保持不变，其余各位 0 变 1、1 变 0",
    })

    # 末位加一：从最低位开始处理进位链
    result = inverted[:]
    carry = 1
    for i in range(width - 1, -1, -1):
        s = result[i] + carry
        result[i] = s & 1
        carry = s >> 1
        if carry == 0:
            break
    steps.append({
        "title": "③ 末位加一（补码）",
        "bits": result,
        "note": "反码加 1 得到补码；若产生向符号位的进位则丢弃（定长截断）",
    })

    assert result == to_bits(value, width), "求补过程与 to_bits 结果不一致"
    return steps


# ---------------------------------------------------------------- 溢出判定

def check_overflow(a: int, b: int, result: int, width: int) -> bool:
    """
    补码溢出判定：两个同号数相加，结果符号与被加数不同 -> 溢出。
    等价于硬件里的 "最高位进位 C_out ⊕ 次高位进位 C_{n-1}"。

    这里用数学定义实现，便于与硬件实现在对拍中互相验证。
    """
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    exact = a + b
    return not (lo <= exact <= hi)


# ---------------------------------------------------------------- 加法主过程

def add_steps(a: int, b: int, width: int = 8) -> dict:
    """
    补码加法全过程，返回结果 + 逐位进位链 + 每一步快照。

    返回 dict：
        width, a, b,
        a_bits, b_bits, sum_bits,
        carry_bits     长度 width+1，carry_bits[0] 是初始进位 0，
                       carry_bits[i+1] 是第 i 位（从低位起）向高位的进位
        carry_in_each  按"从低位到高位"排列的每位进位输入，供动画逐格高亮
        overflow, overflow_reason,
        result_signed, result_unsigned,
        steps          步骤快照列表
    """
    if width not in (8, 16):
        raise ValueError("width 仅支持 8 或 16")

    a_bits = to_bits(a, width)
    b_bits = to_bits(b, width)

    # 从最低位向最高位逐位相加，记录每一位的进位
    sum_bits = [0] * width
    carry_bits = [0] * (width + 1)      # carry_bits[0] 恒为 0
    for pos in range(width - 1, -1, -1):          # pos 是位串下标（高位在前）
        idx_from_low = width - 1 - pos             # 从低位数的序号
        total = a_bits[pos] + b_bits[pos] + carry_bits[idx_from_low]
        sum_bits[pos] = total & 1
        carry_bits[idx_from_low + 1] = total >> 1

    c_out = carry_bits[width]                      # 最高位向外的进位
    c_last = carry_bits[width - 1]                 # 次高位向符号位的进位
    overflow = bool(c_out ^ c_last)
    overflow_by_math = check_overflow(a, b, bits_to_int(sum_bits), width)
    assert overflow == overflow_by_math, "硬件判溢出与数学判溢出不一致"

    result_signed = bits_to_int(sum_bits)
    result_unsigned = sum(
        bit << (width - 1 - i) for i, bit in enumerate(sum_bits)
    )

    # 供动画逐格高亮的进位输入（低位在前）
    carry_in_each = carry_bits[:width]

    # ---- 生成步骤快照：让界面可以"单步播放"
    steps = []

    steps.append({
        "title": "① 输入十进制数",
        "note": f"a = {a}，b = {b}，位宽 {width} 位（补码范围 "
                f"[{-(1 << (width - 1))}, {(1 << (width - 1)) - 1}]）",
        "a_bits": a_bits, "b_bits": b_bits, "sum_bits": [None] * width,
        "carry_bits": None, "highlight": None,
    })

    steps.append({
        "title": "② 转成补码",
        "note": f"a={a} -> {bits_to_str(a_bits)}；b={b} -> {bits_to_str(b_bits)}",
        "a_bits": a_bits, "b_bits": b_bits, "sum_bits": [None] * width,
        "carry_bits": None, "highlight": None,
    })

    for idx_from_low in range(width):
        pos = width - 1 - idx_from_low
        partial_sum = sum_bits[:pos + 1] + [None] * pos
        steps.append({
            "title": f"③ 第 {idx_from_low + 1} 位相加（从右往左）",
            "note": (f"{a_bits[pos]} + {b_bits[pos]} + 进位 {carry_in_each[idx_from_low]}"
                     f" = {a_bits[pos] + b_bits[pos] + carry_in_each[idx_from_low]}"
                     f"，本位写 {sum_bits[pos]}，向高位进位 {carry_bits[idx_from_low + 1]}"),
            "a_bits": a_bits, "b_bits": b_bits, "sum_bits": partial_sum,
            "carry_bits": carry_in_each, "highlight": pos,
        })

    steps.append({
        "title": "④ 溢出判定",
        "note": (f"最高位进位 C_out={c_out}，次高位进位 C_n-1={c_last}，"
                 f"两者异或 = {int(overflow)} -> "
                 + ("溢出！结果不可信" if overflow else "未溢出，结果有效")),
        "a_bits": a_bits, "b_bits": b_bits, "sum_bits": sum_bits,
        "carry_bits": carry_in_each, "highlight": 0,
    })

    steps.append({
        "title": "⑤ 结果回读",
        "note": (f"补码 {bits_to_str(sum_bits)} 解释为有符号数 = {result_signed}"
                 + ("（溢出，此值不作有效结果）" if overflow else "")),
        "a_bits": a_bits, "b_bits": b_bits, "sum_bits": sum_bits,
        "carry_bits": carry_in_each, "highlight": None,
    })

    return {
        "width": width,
        "a": a,
        "b": b,
        "a_bits": a_bits,
        "b_bits": b_bits,
        "sum_bits": sum_bits,
        "carry_bits": carry_bits,
        "carry_in_each": carry_in_each,
        "overflow": overflow,
        "overflow_reason": f"C_out({c_out}) ⊕ C_n-1({c_last}) = {int(overflow)}",
        "result_signed": result_signed,
        "result_unsigned": result_unsigned,
        "steps": steps,
    }


# ---------------------------------------------------------------- 命令行自测

if __name__ == "__main__":
    demo = add_steps(-5, 3, 8)
    print("a =", demo["a"], "  bits:", bits_to_str(demo["a_bits"]))
    print("b =", demo["b"], "  bits:", bits_to_str(demo["b_bits"]))
    print("sum  :", bits_to_str(demo["sum_bits"]), "->", demo["result_signed"])
    print("溢出 :", demo["overflow"], demo["overflow_reason"])
    print("-" * 46)
    for s in demo["steps"]:
        print(f"{s['title']}: {s['note']}")

    print("\n=== 求补过程：-5 ===")
    for s in to_twos_complement_steps(-5, 8):
        print(f"{s['title']}: {bits_to_str(s['bits'])}  {s['note']}")

    print("\n=== 溢出示例：100 + 100 ===")
    ov = add_steps(100, 100, 8)
    print("sum:", bits_to_str(ov["sum_bits"]), "溢出:", ov["overflow"], ov["overflow_reason"])
