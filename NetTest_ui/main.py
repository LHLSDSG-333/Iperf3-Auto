import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import threading
import queue
import time
import os
import sys
import re
from datetime import datetime

class IperfApp:
    def __init__(self, root):
        self.root = root
        self.root.title("iPerf3 网络性能测试工具")
        self.root.geometry("1100x750")
        
        # --- 全局状态 ---
        self.running = False
        self.process = None
        self.queue = queue.Queue()
        self.start_time = 0
        self.total_duration = 10
        self.stdout_file = None
        
        # --- 数据存储 ---
        self.log_data = []          # 原始日志缓存
        self.breakpoint_data = []   # 断点记录
        self.bp_recorded_values = [] 
        self.stats = self.reset_stats()
        
        # --- 断点测试配置 ---
        self.breakpoint_active = False
        self.breakpoint_interval = 5.0
        self.next_breakpoint_time = 0

        # --- UI 初始化 ---
        self.colors = self.init_colors()
        self.init_styles()
        self.create_widgets()
        
        # --- 启动事件循环 ---
        self.root.after(100, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_colors(self):
        return {
            'bg': '#2b2b2b',
            'fg': '#d4d4d4',
            'panel_bg': '#1e1e1e',
            'input_bg': '#252526',
            'border': '#3c3c3c',
            'primary': '#007acc',
            'success': '#387b3c',
            'warning': '#d67e00',
            'danger': '#a1260d',
            'highlight': '#569cd6'
        }

    def reset_stats(self):
        return {
            'total_mbps': 0.0, 'count': 0, 'max_mbps': 0.0,
            'total_jitter': 0.0, 'jitter_count': 0,
            'total_lost': 0, 'total_packets': 0,
            'total_retr': 0
        }

    def get_app_path(self):
        """获取应用程序运行的基础目录"""
        if getattr(sys, 'frozen', False):
            # 打包后的 .exe 所在目录
            return os.path.dirname(sys.executable)
        else:
            # 脚本所在目录
            return os.path.dirname(os.path.abspath(__file__))

    def check_dependencies(self):
        """检查必要的 iperf3.exe 和 dll 是否存在于当前目录"""
        base_dir = self.get_app_path()
        iperf_path = os.path.join(base_dir, "iperf3.exe")
        
        # 检查列表
        missing_files = []
        if not os.path.exists(iperf_path):
            missing_files.append("iperf3.exe")
        
        if sys.platform == 'win32':
             cygwin_path = os.path.join(base_dir, "cygwin1.dll")
             if not os.path.exists(cygwin_path):
                 missing_files.append("cygwin1.dll")
        
        return iperf_path, missing_files

    # ---------------- UI 构建 ----------------
    def init_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        c = self.colors
        style.configure('.', background=c['bg'], foreground=c['fg'], font=('Segoe UI', 9))
        style.configure('TFrame', background=c['bg'])
        style.configure('Panel.TFrame', background=c['panel_bg'], borderwidth=1, relief='solid')
        
        style.configure('TLabel', background=c['bg'], foreground=c['fg'])
        
        # --- 输入框样式配置 (强制深色) ---
        style.configure('TEntry', 
                        fieldbackground=c['input_bg'], 
                        foreground=c['fg'],           
                        insertcolor='white',          
                        borderwidth=1)
        
        # 添加映射以确保在各种状态下背景色正确
        style.map('TEntry', 
                  fieldbackground=[('readonly', c['bg']), ('disabled', c['bg']), ('!disabled', c['input_bg'])],
                  foreground=[('disabled', '#888888')])
        # -------------------------------------
        
        style.configure('Panel.TLabel', background=c['panel_bg'])
        style.configure('Title.TLabel', foreground=c['highlight'], font=('Segoe UI', 10, 'bold'))
        style.configure('Stats.TLabel', font=('Consolas', 12, 'bold'), foreground='#cccccc', background=c['panel_bg'])
        style.configure('StatsLabel.TLabel', font=('Segoe UI', 8), foreground='#808080', background=c['panel_bg'])
        
        style.configure('TButton', padding=4, relief='flat', background=c['input_bg'])
        style.map('TButton', background=[('active', c['border'])])
        
        style.configure('Primary.TButton', background=c['primary'], foreground='white')
        style.map('Primary.TButton', background=[('active', '#106ebe'), ('disabled', c['border'])])
        
        style.configure('Danger.TButton', background=c['danger'], foreground='white')
        style.map('Danger.TButton', background=[('active', '#8a1f0b')])
        
        style.configure('Horizontal.TProgressbar', background=c['primary'], troughcolor=c['input_bg'], bordercolor=c['border'])

    def create_widgets(self):
        container = tk.Frame(self.root, bg=self.colors['bg'])
        container.pack(fill='both', expand=True, padx=8, pady=8)
        
        # === 左侧控制区 ===
        left_panel = ttk.Frame(container, style='Panel.TFrame', padding=10)
        left_panel.pack(side='left', fill='y', padx=(0, 8))
        
        self._build_config_form(left_panel)
        self._build_control_buttons(left_panel)
        
        # === 右侧展示区 ===
        right_panel = tk.Frame(container, bg=self.colors['bg'])
        right_panel.pack(side='right', fill='both', expand=True)
        
        self._build_stats_panel(right_panel)
        self._build_log_panel(right_panel)

    def _build_config_form(self, parent):
        ttk.Label(parent, text="配置参数", style='Title.TLabel', background=self.colors['panel_bg']).pack(anchor='w', pady=(0, 10))
        
        form_bg = self.colors['panel_bg']
        form = tk.Frame(parent, bg=form_bg)
        form.pack(fill='x')
        
        # 基础连接
        self.server_ip = self._add_input_row(form, "服务器 IP:", "127.0.0.1")
        self.server_port = self._add_input_row(form, "端口 (-p):", "5201")
        
        # 协议及带宽
        ttk.Label(form, text="协议:", style='Panel.TLabel').pack(anchor='w', pady=(5, 2))
        self.protocol_var = tk.StringVar(value="tcp")
        proto_box = tk.Frame(form, bg=form_bg)
        proto_box.pack(fill='x', pady=(0, 5))
        
        # 协议单选
        ttk.Radiobutton(proto_box, text="TCP", variable=self.protocol_var, value="tcp", 
                       command=self.toggle_udp_ui).pack(side='left', padx=5)
        ttk.Radiobutton(proto_box, text="UDP", variable=self.protocol_var, value="udp", 
                       command=self.toggle_udp_ui).pack(side='left', padx=5)
        
        # UDP 带宽输入框 (默认隐藏)
        self.udp_bw_frame = tk.Frame(form, bg=form_bg)
        self.udp_bw_entry = self._add_input_row_layout(self.udp_bw_frame, "UDP 带宽 (-b):", "100M")

        # 方向
        ttk.Label(form, text="方向:", style='Panel.TLabel').pack(anchor='w', pady=(5, 2))
        self.direction_var = tk.StringVar(value="upload")
        dir_box = tk.Frame(form, bg=form_bg)
        dir_box.pack(fill='x', pady=(0, 5))
        ttk.Radiobutton(dir_box, text="上传 ( -> Server)", variable=self.direction_var, value="upload").pack(side='left', padx=5)
        ttk.Radiobutton(dir_box, text="下载 ( <- Server)", variable=self.direction_var, value="download").pack(side='left', padx=5)
        
        # 测试参数
        self.duration = self._add_input_row(form, "持续时间 (s):", "10")
        self.interval = self._add_input_row(form, "报告间隔 (s):", "1")
        self.parallel = self._add_input_row(form, "并行流数 (-P):", "1")

        ttk.Separator(parent, orient='horizontal').pack(fill='x', pady=10)

    def _build_control_buttons(self, parent):
        # 主控
        self.btn_start = ttk.Button(parent, text="开始测试", style='Primary.TButton', command=self.start_test)
        self.btn_start.pack(fill='x', pady=5)
        
        self.btn_stop = ttk.Button(parent, text="停止测试", style='Danger.TButton', command=self.stop_test, state='disabled')
        self.btn_stop.pack(fill='x', pady=5)
        
        # 断点模块
        ttk.Label(parent, text="断点测试 (采样)", style='Title.TLabel', background=self.colors['panel_bg']).pack(anchor='w', pady=(15, 5))
        self.bp_interval_entry = self._add_input_row(parent, "采样间隔 (s):", "5")
        
        self.btn_bp_start = ttk.Button(parent, text="开始采样", command=self.start_breakpoint_test)
        self.btn_bp_start.pack(fill='x', pady=5)
        
        self.btn_bp_stop = ttk.Button(parent, text="停止采样", command=self.stop_breakpoint_test, state='disabled')
        self.btn_bp_stop.pack(fill='x', pady=5)
        
        ttk.Separator(parent, orient='horizontal').pack(fill='x', pady=15)
        
        # 数据操作
        ttk.Button(parent, text="保存主日志", command=lambda: self.save_data('main')).pack(fill='x', pady=2)
        ttk.Button(parent, text="保存断点日志", command=lambda: self.save_data('bp')).pack(fill='x', pady=2)
        ttk.Button(parent, text="清空数据", command=self.clear_data).pack(fill='x', pady=2)

    def _build_stats_panel(self, parent):
        panel = ttk.Frame(parent, style='Panel.TFrame', padding=10)
        panel.pack(fill='x', pady=(0, 8))
        
        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(panel, variable=self.progress_var, maximum=100, style='Horizontal.TProgressbar').pack(fill='x', pady=(0, 10))
        
        grid = tk.Frame(panel, bg=self.colors['panel_bg'])
        grid.pack(fill='x')
        
        self.lbl_status = self._create_stat_item(grid, 0, "状态", "就绪")
        self.lbl_avg_bw = self._create_stat_item(grid, 1, "平均带宽", "-")
        self.lbl_max_bw = self._create_stat_item(grid, 2, "最大带宽", "-")
        self.lbl_bp_count = self._create_stat_item(grid, 3, "断点记录", "0")

    def _build_log_panel(self, parent):
        split = tk.Frame(parent, bg=self.colors['bg'])
        split.pack(fill='both', expand=True)
        
        # 上半部分：主日志
        log_frame = ttk.Frame(split, style='Panel.TFrame', padding=5)
        log_frame.pack(fill='both', expand=True, pady=(0, 5))
        ttk.Label(log_frame, text="运行日志", style='Panel.TLabel', font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        self.txt_main_log = scrolledtext.ScrolledText(log_frame, bg='#252526', fg='#cccccc', 
                                                     insertbackground='white', font=('Consolas', 10), relief='flat')
        self.txt_main_log.pack(fill='both', expand=True)
        
        # 下半部分：断点日志
        bp_frame = ttk.Frame(split, style='Panel.TFrame', padding=5)
        bp_frame.pack(fill='both', expand=True, pady=(5, 0))
        ttk.Label(bp_frame, text="断点采样记录", style='Panel.TLabel', font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        self.txt_bp_log = scrolledtext.ScrolledText(bp_frame, bg='#252526', fg='#d7ba7d', 
                                                   insertbackground='white', font=('Consolas', 10), height=8, relief='flat')
        self.txt_bp_log.pack(fill='both', expand=True)

    # ---------------- 辅助方法 ----------------

    def _add_input_row(self, parent, label, default):
        frame = tk.Frame(parent, bg=self.colors['panel_bg'])
        frame.pack(fill='x', pady=2)
        return self._add_input_row_layout(frame, label, default)

    def _add_input_row_layout(self, frame, label, default):
        ttk.Label(frame, text=label, style='Panel.TLabel', width=15).pack(side='left')
        entry = ttk.Entry(frame)
        entry.insert(0, default)
        entry.pack(side='right', fill='x', expand=True)
        return entry

    def _create_stat_item(self, parent, col, title, initial):
        frame = tk.Frame(parent, bg=self.colors['panel_bg'], bd=0)
        frame.grid(row=0, column=col, sticky='nsew', padx=5)
        parent.grid_columnconfigure(col, weight=1)
        ttk.Label(frame, text=title, style='StatsLabel.TLabel').pack(anchor='w')
        lbl = ttk.Label(frame, text=initial, style='Stats.TLabel')
        lbl.pack(anchor='w')
        return lbl

    def toggle_udp_ui(self):
        if self.protocol_var.get() == 'udp':
            self.udp_bw_frame.pack(fill='x', pady=2, after=self.proto_frame)
        else:
            self.udp_bw_frame.pack_forget()

    # ---------------- 核心逻辑 ----------------

    def start_test(self):
        if self.running: return

        self.clear_data(clear_ui=False)
        self.txt_main_log.delete(1.0, tk.END)
        
        # 1. 依赖检查
        iperf_exe, missing = self.check_dependencies()
        if missing:
            msg = "缺少必要组件，请确保以下文件在程序同级目录下:\n" + "\n".join(missing)
            messagebox.showerror("组件缺失", msg)
            self.txt_main_log.insert(tk.END, f"[System Error] {msg}\n")
            return

        # 2. 构建命令
        try:
            cmd = self.build_command(iperf_exe)
        except ValueError as e:
            messagebox.showerror("配置错误", str(e))
            return

        self.txt_main_log.insert(tk.END, f"--- 开始测试 ---\n")
        self.txt_main_log.insert(tk.END, f"执行程序: {iperf_exe}\n")
        self.txt_main_log.insert(tk.END, f"参数列表: {cmd[1:]}\n\n")

        self.running = True
        self.start_time = time.time()
        
        # UI 状态更新
        self._set_ui_state(running=True)
        self.lbl_status.configure(text="运行中", foreground=self.colors['success'])

        # 启动线程
        t = threading.Thread(target=self.run_subprocess, args=(cmd,), daemon=True)
        t.start()

    def build_command(self, exe_path):
        cmd = [exe_path, '-c', self.server_ip.get().strip(), 
               '-p', self.server_port.get().strip(),
               '-i', self.interval.get().strip(),
               '--forceflush'] # 关键：强制刷新缓冲区
        
        if self.protocol_var.get() == 'udp':
            cmd.append('-u')
            if bw := self.udp_bw_entry.get().strip():
                cmd.extend(['-b', bw])
                
        if self.direction_var.get() == 'download':
            cmd.append('-R')

        try:
            self.total_duration = int(self.duration.get())
            cmd.extend(['-t', str(self.total_duration)])
        except:
            raise ValueError("持续时间必须为整数")

        try:
            if (p := int(self.parallel.get())) > 1:
                cmd.extend(['-P', str(p)])
        except: pass
        
        return cmd

    def run_subprocess(self, cmd):
        app_dir = os.path.dirname(cmd[0])
        
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # 使用 SW_HIDE 隐藏黑框
        
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=app_dir, # 工作目录设为 exe 所在目录
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, # 关闭输入
                text=True, # 启用文本缓冲
                bufsize=1, # 行缓冲
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo
            )
            
            self.queue.put(('log', f"[System] 进程 PID: {self.process.pid} 已启动\n"))
            
            # 实时读取循环
            while self.running:
                line = self.process.stdout.readline()
                if line:
                    self.queue.put(('log', line))
                elif self.process.poll() is not None:
                    break # 进程结束且无新输出
            
            code = self.process.wait()
            self.queue.put(('finish', code))
            
        except Exception as e:
            self.queue.put(('error', str(e)))
        finally:
            self.running = False

    def on_close(self):
        if self.running:
            if messagebox.askokcancel("退出", "测试正在进行中，确认停止并退出？"):
                self.stop_test()
                self.root.after(200, self.destroy)
        else:
            self.destroy()

    def destroy(self):
        if self.process and self.process.poll() is None:
            try: self.process.kill()
            except: pass
        self.root.destroy()
        sys.exit(0)

    # ---------------- 业务逻辑处理 ----------------

    def process_queue(self):
        try:
            while True:
                type_, data = self.queue.get_nowait()
                if type_ == 'log':
                    self._append_log(data)
                    self._parse_line_metrics(data)
                elif type_ == 'finish':
                    self._on_finished(data)
                elif type_ == 'error':
                    self._append_log(f"[Error] {data}\n")
                    self._on_finished(-1)
        except queue.Empty: pass
        self.root.after(100, self.process_queue)

    def _append_log(self, text):
        # 限制日志长度，防卡顿
        if len(self.log_data) > 5000:
            del self.log_data[:1000]
            self.txt_main_log.delete('1.0', '1001.0')
        
        self.log_data.append(text)
        self.txt_main_log.insert(tk.END, text)
        self.txt_main_log.see(tk.END)

    def _parse_line_metrics(self, line):
        if '[SUM]' in line or 'sender' in line or 'receiver' in line:
            return

        # 匹配带宽: "38.6 Mbits/sec"
        match = re.search(r'\s+(\d+(?:\.\d+)?)\s+([KMGT]?bits\/sec)', line)
        if match:
            mbps = self._convert_to_mbps(float(match.group(1)), match.group(2))
            
            # 更新实时统计
            s = self.stats
            s['count'] += 1
            s['total_mbps'] += mbps
            s['max_mbps'] = max(s['max_mbps'], mbps)
            
            avg = s['total_mbps'] / s['count']
            self.lbl_avg_bw.configure(text=f"{avg:.2f} Mbps")
            self.lbl_max_bw.configure(text=f"{s['max_mbps']:.2f} Mbps")

            # 更新进度条
            elapsed = time.time() - self.start_time
            if self.total_duration > 0:
                p = (elapsed / self.total_duration) * 100
                self.progress_var.set(min(p, 100))
            
            # 解析 UDP Jitter/Loss 或 TCP Retr
            self._parse_extra_metrics(line)

            # 断点采样
            if self.breakpoint_active and elapsed >= self.next_breakpoint_time:
                self._record_breakpoint(mbps, elapsed)

    def _parse_extra_metrics(self, line):
        if self.protocol_var.get() == 'udp':
            # UDP: 0.034 ms  0/89 (0%)
            m = re.search(r'(\d+(?:\.\d+)?)\s+ms\s+(\d+)/(\d+)', line)
            if m:
                self.stats['total_jitter'] += float(m.group(1))
                self.stats['jitter_count'] += 1
                self.stats['total_lost'] += int(m.group(2))
                self.stats['total_packets'] += int(m.group(3))
        else:
            # TCP Retr (iperf3 output format varies, usually column after bandwidth)
            # 简化处理：从行中提取 Retr 字段有点复杂，暂略或根据具体版本调整
            pass

    def _convert_to_mbps(self, val, unit):
        if unit.startswith('G'): return val * 1000
        if unit.startswith('K'): return val / 1000
        if unit == 'bits/sec': return val / 1000000
        return val

    def _record_breakpoint(self, mbps, elapsed):
        self.bp_recorded_values.append(mbps)
        ts = datetime.now().strftime("%H:%M:%S")
        log = f"[{ts}] T:{elapsed:.1f}s BW:{mbps:.2f} Mbps"
        self.breakpoint_data.append(log)
        self.txt_bp_log.insert(tk.END, log + "\n")
        self.txt_bp_log.see(tk.END)
        self.lbl_bp_count.configure(text=str(len(self.breakpoint_data)))
        self.next_breakpoint_time += self.breakpoint_interval

    def _on_finished(self, code):
        self.running = False
        self._set_ui_state(running=False)
        self.progress_var.set(100)
        
        status = "完成" if code == 0 else "异常停止"
        color = self.colors['fg'] if code == 0 else self.colors['warning']
        self.lbl_status.configure(text=status, foreground=color)
        
        self._generate_summary_report()
        if self.breakpoint_active:
            self.stop_breakpoint_test()

    def _generate_summary_report(self):
        s = self.stats
        if s['count'] == 0: return

        avg = s['total_mbps'] / s['count']
        lines = [
            "\n========= 测试汇总 =========",
            f"平均带宽: {avg:.2f} Mbps",
            f"峰值带宽: {s['max_mbps']:.2f} Mbps",
        ]
        
        if self.protocol_var.get() == 'udp' and s['jitter_count'] > 0:
            avg_jit = s['total_jitter'] / s['jitter_count']
            loss_rate = (s['total_lost'] / s['total_packets'] * 100) if s['total_packets'] else 0
            lines.append(f"平均抖动: {avg_jit:.3f} ms")
            lines.append(f"丢包情况: {s['total_lost']}/{s['total_packets']} ({loss_rate:.2f}%)")
            
        lines.append("===========================\n")
        text = "\n".join(lines)
        self._append_log(text)

    def _set_ui_state(self, running):
        state = 'disabled' if running else 'normal'
        inv_state = 'normal' if running else 'disabled'
        self.btn_start.configure(state=state)
        self.btn_stop.configure(state=inv_state)

    # ---------------- 功能逻辑 ----------------

    def stop_test(self):
        if self.process and self.running:
            self.process.terminate()
            self._append_log("\n[User] 请求停止...\n")

    def start_breakpoint_test(self):
        if not self.running:
            messagebox.showwarning("提示", "请先启动主测试")
            return
        try:
            self.breakpoint_interval = float(self.bp_interval_entry.get())
        except:
            self.breakpoint_interval = 5.0
            
        self.breakpoint_active = True
        elapsed = time.time() - self.start_time
        self.next_breakpoint_time = elapsed + self.breakpoint_interval
        
        self.btn_bp_start.configure(state='disabled')
        self.btn_bp_stop.configure(state='normal')
        self.txt_bp_log.insert(tk.END, f"--- 开始记录 (间隔:{self.breakpoint_interval}s) ---\n")

    def stop_breakpoint_test(self):
        self.breakpoint_active = False
        self.btn_bp_start.configure(state='normal')
        self.btn_bp_stop.configure(state='disabled')
        
        if self.bp_recorded_values:
            avg = sum(self.bp_recorded_values) / len(self.bp_recorded_values)
            self.txt_bp_log.insert(tk.END, f"--- 记录结束 (平均: {avg:.2f} Mbps) ---\n")

    def clear_data(self, clear_ui=True):
        self.log_data = []
        self.breakpoint_data = []
        self.bp_recorded_values = []
        self.stats = self.reset_stats()
        
        if clear_ui:
            self.txt_main_log.delete(1.0, tk.END)
            self.txt_bp_log.delete(1.0, tk.END)
            self.lbl_avg_bw.configure(text="-")
            self.lbl_max_bw.configure(text="-")
            self.progress_var.set(0)
            self.lbl_status.configure(text="就绪", foreground=self.colors['fg'])

    def save_data(self, type_):
        fname = f"iperf_{type_}_{datetime.now().strftime('%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(initialfile=fname, defaultextension=".txt")
        if not path: return
        
        content = "".join(self.log_data) if type_ == 'main' else "".join(self.breakpoint_data)
        try:
            with open(path, 'w', encoding='utf-8') as f: f.write(content)
            messagebox.showinfo("保存成功", path)
        except Exception as e:
            messagebox.showerror("错误", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = IperfApp(root)
    root.mainloop()
