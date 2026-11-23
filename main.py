# -*- coding: utf-8 -*-
"""
main.py —— 补码加减法运算模拟器（最小闭环版 / D3 模板）

这一版由组长先跑通，作用有两个：
1. 证明「输入 → 补码 → 逐位相加 → 溢出判定 → 结果」技术路线可行，可直接给老师演示；
2. 作为界面层与渲染层的样板：B、C 在此结构上继续做漂亮与做动画，不另起炉灶。

运行：
    python main.py
"""

import sys

try:                                    # tkinter 属于标准库，但某些精简版 Python 会缺失
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:                       # noqa: BLE001
    print("当前 Python 没有 tkinter，无法启动图形界面。")
    print("可改用命令行验证核心逻辑：python core/bitops.py")
    sys.exit(1)

from core.bitops import add_steps, bits_to_str, to_twos_complement_steps

WIN_W, WIN_H = 1250, 760
COLOR_BG = "#F5F7FA"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#1F2933"
COLOR_MUTED = "#6B7785"
COLOR_ACCENT = "#2F6FED"
COLOR_OVERFLOW = "#D93025"
COLOR_OK = "#188038"


class ComplementApp:
    """主应用：输入区 + 位格画布 + 日志区 + 控制条。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("补码加减法运算模拟器")
        self.root.geometry(f"{WIN_W}x{WIN_H}")
        self.root.configure(bg=COLOR_BG)

        # DPI 自适应：把 tk 的缩放系数乘到字号上，并限幅，避免 125%/150% 下字体炸掉
        try:
            self._scale = max(0.8, min(2.0, float(self.root.tk.call("tk", "scaling")) / 1.33))
        except Exception:               # noqa: BLE001
            self._scale = 1.0

        self.result = None              # 当前 add_steps() 的返回值
        self.step_index = 0             # 当前播放到第几步

        self._build_style()
        self._build_input_area()
        self._build_canvas_area()
        self._build_log_area()
        self._build_control_bar()

        self.calculate()                # 启动先算一次默认值，界面不至于空白

    # ------------------------------------------------------------ 样式
    def _font(self, size, bold=False):
        s = max(8, int(round(size * self._scale)))
        return ("Microsoft YaHei UI", s, "bold") if bold else ("Microsoft YaHei UI", s)

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:               # noqa: BLE001
            pass
        style.configure("TFrame", background=COLOR_BG)
        style.configure("Card.TFrame", background=COLOR_CARD)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                        font=self._font(11))
        style.configure("TButton", font=self._font(11), padding=(10, 6))

    # ------------------------------------------------------------ 输入区
    def _build_input_area(self):
        bar = ttk.Frame(self.root, padding=(16, 14, 16, 6))
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(bar, text="补码加减法运算模拟器",
                  font=self._font(16, bold=True)).pack(side=tk.LEFT, padx=(0, 24))

        ttk.Label(bar, text="a =").pack(side=tk.LEFT)
        self.entry_a = ttk.Entry(bar, width=8, font=self._font(12))
        self.entry_a.insert(0, "-5")
        self.entry_a.pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(bar, text="b =").pack(side=tk.LEFT)
        self.entry_b = ttk.Entry(bar, width=8, font=self._font(12))
        self.entry_b.insert(0, "3")
        self.entry_b.pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(bar, text="位宽").pack(side=tk.LEFT)
        self.width_var = tk.StringVar(value="8")
        self.width_box = ttk.Combobox(bar, textvariable=self.width_var, width=5,
                                      values=("8", "16"), state="readonly",
                                      font=self._font(11))
        self.width_box.pack(side=tk.LEFT, padx=(4, 12))
        self.width_box.bind("<<ComboboxSelected>>", lambda _e: self.calculate())

        ttk.Button(bar, text="计算", command=self.calculate).pack(side=tk.LEFT)
        ttk.Button(bar, text="重置", command=self.reset).pack(side=tk.LEFT, padx=6)

    # ------------------------------------------------------------ 画布
    def _build_canvas_area(self):
        box = ttk.Frame(self.root, padding=(16, 6, 16, 6), style="Card.TFrame")
        box.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(box, bg=COLOR_CARD, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.draw_steps())

    # ------------------------------------------------------------ 日志
    def _build_log_area(self):
        box = ttk.Frame(self.root, padding=(16, 0, 16, 6))
        box.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(box, text="步骤日志", font=self._font(11, bold=True)).pack(anchor="w")
        self.log = tk.Text(box, height=7, font=("Consolas", max(9, int(10 * self._scale))),
                           bg="#FBFCFE", fg=COLOR_TEXT, relief="flat", wrap="word")
        self.log.pack(fill=tk.X, pady=(4, 0))

    # ------------------------------------------------------------ 控制条
    def _build_control_bar(self):
        bar = ttk.Frame(self.root, padding=(16, 4, 16, 14))
        bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_prev = ttk.Button(bar, text="上一步", command=self.prev_step)
        self.btn_prev.pack(side=tk.LEFT)
        self.btn_next = ttk.Button(bar, text="下一步", command=self.next_step)
        self.btn_next.pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="全部展开", command=self.show_all).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="")
        self.status = ttk.Label(bar, textvariable=self.status_var, font=self._font(11, bold=True))
        self.status.pack(side=tk.RIGHT)

    # ------------------------------------------------------------ 业务逻辑
    def calculate(self):
        try:
            a = int(self.entry_a.get().strip())
            b = int(self.entry_b.get().strip())
            width = int(self.width_var.get())
        except ValueError:
            messagebox.showerror("输入错误", "请输入两个十进制整数。")
            return

        lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
        if not (lo <= a <= hi and lo <= b <= hi):
            messagebox.showerror("超出范围", f"{width} 位补码可表示 {lo} ~ {hi}。")
            return

        self.result = add_steps(a, b, width)
        self.step_index = 0
        self.draw_steps()
        self.refresh_log()

    def reset(self):
        self.entry_a.delete(0, tk.END)
        self.entry_a.insert(0, "-5")
        self.entry_b.delete(0, tk.END)
        self.entry_b.insert(0, "3")
        self.width_var.set("8")
        self.calculate()

    def next_step(self):
        if not self.result:
            return
        if self.step_index < len(self.result["steps"]) - 1:
            self.step_index += 1
            self.draw_steps()
            self.refresh_log()

    def prev_step(self):
        if not self.result:
            return
        if self.step_index > 0:
            self.step_index -= 1
            self.draw_steps()
            self.refresh_log()

    def show_all(self):
        if not self.result:
            return
        self.step_index = len(self.result["steps"]) - 1
        self.draw_steps()
        self.refresh_log()

    # ------------------------------------------------------------ 渲染
    def draw_steps(self):
        """把当前步骤的三行位格画出来：a / b / 结果，带进位标记与高亮。"""
        c = self.canvas
        c.delete("all")
        if not self.result:
            return

        step = self.result["steps"][self.step_index]
        width = self.result["width"]
        cw = max(c.winfo_width(), 400)
        ch = max(c.winfo_height(), 240)

        cell = min(56, int((cw - 120) / max(width, 8)))
        gap = 2
        total_w = width * (cell + gap)
        x0 = (cw - total_w) // 2
        row_y = [ch * 0.18, ch * 0.40, ch * 0.66]

        labels = [
            ("a", self.result["a"], step["a_bits"]),
            ("b", self.result["b"], step["b_bits"]),
            ("和", None, step["sum_bits"]),
        ]

        highlight = step.get("highlight")

        for row, (name, value, bits) in enumerate(labels):
            y = row_y[row]
            c.create_text(x0 - 34, y + cell / 2, text=name,
                          font=self._font(12, bold=True), fill=COLOR_MUTED)
            for i in range(width):
                x = x0 + i * (cell + gap)
                bit = bits[i] if bits and bits[i] is not None else None
                fill = "#FFFFFF"
                if bit is None:
                    fill = "#F0F2F5"
                if row == 2 and highlight is not None and i == highlight:
                    fill = "#FFE9A8"
                outline = COLOR_ACCENT if (row == 2 and bit is not None) else "#D5DBE3"
                c.create_rectangle(x, y, x + cell, y + cell,
                                   fill=fill, outline=outline, width=2)
                c.create_text(x + cell / 2, y + cell / 2,
                              text="" if bit is None else str(bit),
                              font=("Consolas", max(11, int(cell * 0.42)), "bold"),
                              fill=COLOR_TEXT)

        # 进位链：画在 b 行与"和"行之间
        carries = step.get("carry_bits")
        if carries:
            y_arrow = row_y[1] + cell + 22
            for i in range(width - 1):
                cin = carries[width - 1 - (i + 1)] if i + 1 < len(carries) else 0
                x = x0 + (i + 1) * (cell + gap)
                color = COLOR_ACCENT if cin else "#C9D1DA"
                c.create_text(x - gap / 2, y_arrow, text="↑" if cin else "·",
                              font=("Consolas", max(10, int(cell * 0.35))), fill=color)

        # 底部状态：结果与溢出
        if self.step_index >= len(self.result["steps"]) - 1:
            if self.result["overflow"]:
                text = f"溢出！{self.result['overflow_reason']}  →  结果不可信"
                color = COLOR_OVERFLOW
            else:
                text = (f"结果 = {self.result['result_signed']}（补码 "
                        f"{bits_to_str(self.result['sum_bits'])}）")
                color = COLOR_OK
            c.create_text(cw / 2, ch * 0.90, text=text,
                          font=self._font(14, bold=True), fill=color)

        self.status_var.set(f"第 {self.step_index + 1}/{len(self.result['steps'])} 步")

    def refresh_log(self):
        if not self.result:
            return
        self.log.delete("1.0", tk.END)
        step = self.result["steps"][self.step_index]
        self.log.insert(tk.END, f"【{step['title']}】{step['note']}\n")

        # 负数求补过程也顺带展示，帮助理解
        if self.step_index >= 1:
            for v in (self.result["a"], self.result["b"]):
                if v < 0:
                    self.log.insert(tk.END, f"\n-- {v} 的求补过程 --\n")
                    for s in to_twos_complement_steps(v, self.result["width"]):
                        self.log.insert(tk.END, f"{s['title']}：{bits_to_str(s['bits'])}  {s['note']}\n")
                    break


def main():
    root = tk.Tk()
    ComplementApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
