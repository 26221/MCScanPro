import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from mcstatus import JavaServer, BedrockServer
import os
import re
import webbrowser
import json

# 文件路径
HTML_REPORT_FILE = "scan_report.html"
HISTORY_DATA_FILE = "server_history.json"
semaphore = None

def safe_insert_result(text_widget, result, description=None):
    """Safely insert results into the text widget from any thread."""
    if description:
        text_widget.insert(tk.END, result + "\n")
        text_widget.insert(tk.END, f"描述: {description}\n\n")
    else:
        text_widget.insert(tk.END, result + "\n")
    text_widget.see(tk.END)

class ServerReport:
    """Class to manage server data, including loading, scanning, and report generation."""

    def __init__(self, root):
        self.root = root
        self.servers_data = {}  # Store server data with IP:port as key
        self.lock = threading.Lock()

    def load_history_data(self):
        """Load server data from the history file."""
        if os.path.exists(HISTORY_DATA_FILE):
            try:
                with open(HISTORY_DATA_FILE, "r", encoding="utf-8") as f:
                    self.servers_data = json.load(f)
            except Exception as e:
                messagebox.showerror("错误", f"加载历史数据时发生错误: {e}")
                self.servers_data = {}
        else:
            self.servers_data = {}

    def save_history_data(self):
        """Save current server data to the history file."""
        with open(HISTORY_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.servers_data, f, indent=4)

    def generate_html_report(self):
        """Generate an HTML report from the current server data."""
        try:
            java_servers = {k: v for k, v in self.servers_data.items() if v.get("type") == "java"}
            bedrock_servers = {k: v for k, v in self.servers_data.items() if v.get("type") == "bedrock"}

            html_content = """
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Minecraft 扫描报告</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 20px; background-color: #f4f7f9; color: #333; }
                    .container { max-width: 800px; margin: auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
                    h1 { color: #2c3e50; text-align: center; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                    h2 { color: #34495e; border-bottom: 1px solid #e0e0e0; padding-bottom: 5px; margin-top: 20px; }
                    .server-card { border: 1px solid #e0e0e0; border-radius: 6px; padding: 15px; margin-bottom: 15px; background-color: #fcfcfc; }
                    .server-card h3 { margin-top: 0; color: #34495e; font-size: 1.2em; }
                    .server-card p { margin: 5px 0; }
                    .java-server { border-left: 5px solid #2ecc71; }
                    .bedrock-server { border-left: 5px solid #3498db; }
                    .description { font-style: italic; color: #7f8c8d; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Minecraft 扫描报告</h1>
            """
            
            if java_servers:
                html_content += """
                    <h2>Java Edition 服务器</h2>
                """
                for address, server_info in java_servers.items():
                    html_content += f"""
                    <div class="server-card java-server">
                        <h3>{address}</h3>
                        <p><strong>版本:</strong> {server_info.get("version", "N/A")}</p>
                        <p><strong>玩家:</strong> {server_info.get("players", "N/A")}</p>
                        <p class="description"><strong>描述:</strong> {server_info.get("description", "N/A")}</p>
                    </div>
                    """

            if bedrock_servers:
                html_content += """
                    <h2>Bedrock Edition 服务器</h2>
                """
                for address, server_info in bedrock_servers.items():
                    html_content += f"""
                    <div class="server-card bedrock-server">
                        <h3>{address}</h3>
                        <p><strong>版本:</strong> {server_info.get("version", "N/A")}</p>
                        <p><strong>玩家:</strong> {server_info.get("players", "N/A")}</p>
                        <p class="description"><strong>描述:</strong> {server_info.get("description", "N/A")}</p>
                    </div>
                    """

            html_content += """
                </div>
            </body>
            </html>
            """
            
            with open(HTML_REPORT_FILE, "w", encoding="utf-8") as f:
                f.write(html_content)

            messagebox.showinfo("完成", f"HTML报告已生成，文件路径：{os.path.abspath(HTML_REPORT_FILE)}")
            webbrowser.open(HTML_REPORT_FILE)

        except Exception as e:
            messagebox.showerror("错误", f"生成HTML报告时发生错误：{e}")

    async def _scan_single_server(self, host, port, server_type, progress_var, total_tasks, text_results, progress_bar):
        """Async function to scan a single Minecraft server and update data."""
        async with semaphore:
            address = f"{host}:{port}"
            try:
                if server_type == "java":
                    server = JavaServer(host, port)
                    status = await asyncio.wait_for(server.async_status(), timeout=3)
                    description = getattr(status.description, 'clean', str(status.description))
                    server_info = {
                        "type": "java",
                        "status": "online",
                        "version": status.version.name,
                        "players": f"{status.players.online}/{status.players.max}",
                        "description": description
                    }
                elif server_type == "bedrock":
                    server = BedrockServer(host, port)
                    status = await asyncio.wait_for(server.async_status(), timeout=5)
                    players_online = getattr(status.players, 'online', '?')
                    players_max = getattr(status.players, 'max', '?')
                    motd_obj = getattr(status, 'motd', None)
                    description = motd_obj.clean.strip() if motd_obj and getattr(motd_obj, 'clean', None) else "N/A"
                    server_info = {
                        "type": "bedrock",
                        "status": "online",
                        "version": status.version.name,
                        "players": f"{players_online}/{players_max}",
                        "description": description
                    }
                else:
                    return

                with self.lock:
                    self.servers_data[address] = server_info

                result = f"[{server_info['type'].capitalize()}] {address} | 状态: {server_info['status']} | 版本: {server_info['version']} | 玩家: {server_info['players']}"
                self.root.after(0, safe_insert_result, text_results, result, description)

            except:
                pass # Do nothing for offline servers
            finally:
                self.root.after(0, lambda p=progress_var, b=progress_bar, t=total_tasks: (p.set(p.get() + 1), b.config(value=(p.get() / t) * 100)))

    async def _start_scan_async(self, tasks, concurrency, progress_var, progress_bar, text_results):
        """Main async function to manage scanning tasks."""
        global semaphore
        semaphore = asyncio.Semaphore(concurrency)
        total_tasks = len(tasks)
        
        self.root.after(0, lambda pv=progress_var, pb=progress_bar, tr=text_results: (pv.set(0), pb.config(value=0), tr.delete("1.0", tk.END)))
        
        # 清空服务器数据，只保留本次扫描的在线服务器
        self.servers_data = {}

        await asyncio.gather(*(self._scan_single_server(h, p, t, progress_var, total_tasks, text_results, progress_bar) for h, p, t in tasks))
        
        self.save_history_data()
        self.root.after(0, lambda: messagebox.showinfo("完成", "扫描完成！正在生成报告..."))
        self.root.after(100, self.generate_html_report)
    
    def run_new_scan(self, ip_list, port_start, port_end, scan_java, scan_bedrock, concurrency, progress_var, progress_bar, text_results):
        """Starts a new scan from scratch, but merges with old data."""
        self.load_history_data()

        servers_to_scan = set()
        
        # Add new servers from user input
        for ip in ip_list:
            ip = ip.strip()
            if not ip: continue
            for port in range(port_start, port_end + 1):
                address = f"{ip}:{port}"
                if scan_java:
                    servers_to_scan.add((ip, port, "java"))
                if scan_bedrock:
                    servers_to_scan.add((ip, port, "bedrock"))

        # Add servers from history if they match the selected types
        for address, server_info in self.servers_data.items():
            host, port = address.split(":")
            port = int(port)
            server_type = server_info.get("type", "java")
            if (scan_java and server_type == "java") or (scan_bedrock and server_type == "bedrock"):
                servers_to_scan.add((host, port, server_type))
        
        tasks = list(servers_to_scan)

        if not tasks:
            messagebox.showerror("错误", "没有需要扫描的任务")
            return
        
        threading.Thread(
            target=lambda: asyncio.run(
                self._start_scan_async(tasks, concurrency, progress_var, progress_bar, text_results)
            ),
            daemon=True
        ).start()

    def run_rescan(self, concurrency, scan_java, scan_bedrock, progress_var, progress_bar, text_results):
        """Loads old data, rescans all servers, and generates a new report."""
        if not os.path.exists(HISTORY_DATA_FILE):
            messagebox.showerror("错误", f"找不到历史文件：{HISTORY_DATA_FILE}")
            return

        self.load_history_data()
        messagebox.showinfo("开始", f"加载了 {len(self.servers_data)} 条历史记录，即将开始重新扫描...")

        tasks = []
        for address, server_info in self.servers_data.items():
            host, port = address.split(":")
            server_type = server_info.get("type", "java")
            if (scan_java and server_type == "java") or (scan_bedrock and server_type == "bedrock"):
                tasks.append((host, int(port), server_type))

        if not tasks:
            messagebox.showerror("错误", "没有需要重新扫描的任务，请检查扫描类型是否勾选。")
            return
            
        threading.Thread(
            target=lambda: asyncio.run(
                self._start_scan_async(tasks, concurrency, progress_var, progress_bar, text_results)
            ),
            daemon=True
        ).start()


def main():
    root = tk.Tk()
    root.title("Minecraft 多IP端口扫描器")
    root.geometry("650x650")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    tab_new_scan = ttk.Frame(notebook)
    notebook.add(tab_new_scan, text="新扫描")

    tab_rescan = ttk.Frame(notebook)
    notebook.add(tab_rescan, text="刷新服务器列表")
    
    report_manager = ServerReport(root)

    # --- 新扫描页面 (tab_new_scan) ---
    var_java_new = tk.BooleanVar(value=True)
    var_bedrock_new = tk.BooleanVar(value=True)
    entry_concurrency_new = tk.Entry(tab_new_scan)
    entry_concurrency_new.insert(0, "100")
    
    progress_var_new = tk.IntVar(value=0)
    progress_bar_new = ttk.Progressbar(tab_new_scan, length=500)
    
    text_results_new = tk.Text(tab_new_scan, height=15)
    
    tk.Label(tab_new_scan, text="目标IP/域名（每行一个）:").pack(anchor="w", padx=10, pady=(10, 0))
    text_ips_new = tk.Text(tab_new_scan, height=5)
    text_ips_new.pack(fill="x", padx=10)

    tk.Label(tab_new_scan, text="端口范围 (如 20000-25000):").pack(anchor="w", padx=10, pady=(10, 0))
    entry_ports_new = tk.Entry(tab_new_scan)
    entry_ports_new.insert(0, "20000-25000")
    entry_ports_new.pack(fill="x", padx=10)

    frame_opts_new = tk.Frame(tab_new_scan)
    frame_opts_new.pack(pady=5, anchor="w", padx=10)
    tk.Checkbutton(frame_opts_new, text="扫描Java版", variable=var_java_new).pack(side="left", padx=5)
    tk.Checkbutton(frame_opts_new, text="扫描基岩版", variable=var_bedrock_new).pack(side="left", padx=5)

    tk.Label(tab_new_scan, text="最大并发数:").pack(anchor="w", padx=10, pady=(10, 0))
    entry_concurrency_new.pack(fill="x", padx=10)

    progress_bar_new.pack(pady=15, padx=10)
    tk.Button(tab_new_scan, text="开始扫描", command=lambda: report_manager.run_new_scan(
        text_ips_new.get("1.0", tk.END).strip().splitlines(),
        *map(int, entry_ports_new.get().split("-")),
        var_java_new.get(), var_bedrock_new.get(), int(entry_concurrency_new.get()),
        progress_var_new, progress_bar_new, text_results_new
    ), bg="#4CAF50", fg="white", height=2).pack(fill="x", padx=10)

    tk.Label(tab_new_scan, text="扫描结果:").pack(anchor="w", padx=10, pady=(10, 0))
    text_results_new.pack(fill="both", expand=True, padx=10, pady=5)

    # --- 加载并重新扫描页面 (tab_rescan) ---
    var_java_rescan = tk.BooleanVar(value=True)
    var_bedrock_rescan = tk.BooleanVar(value=True)
    entry_concurrency_rescan = tk.Entry(tab_rescan)
    entry_concurrency_rescan.insert(0, "100")
    
    progress_var_rescan = tk.IntVar(value=0)
    progress_bar_rescan = ttk.Progressbar(tab_rescan, length=500)
    
    text_results_rescan = tk.Text(tab_rescan, height=15)

    tk.Label(tab_rescan, text="此页面将对历史报告中的服务器进行重新扫描，并更新报告。").pack(padx=10, pady=(20, 10))

    tk.Label(tab_rescan, text="最大并发数:").pack(anchor="w", padx=10, pady=(10, 0))
    entry_concurrency_rescan.pack(fill="x", padx=10)

    frame_opts_rescan = tk.Frame(tab_rescan)
    frame_opts_rescan.pack(pady=5, anchor="w", padx=10)
    tk.Checkbutton(frame_opts_rescan, text="扫描Java版", variable=var_java_rescan).pack(side="left", padx=5)
    tk.Checkbutton(frame_opts_rescan, text="扫描基岩版", variable=var_bedrock_rescan).pack(side="left", padx=5)

    progress_bar_rescan.pack(pady=15, padx=10)
    
    tk.Button(tab_rescan, text="刷新服务器列表", command=lambda: report_manager.run_rescan(
        int(entry_concurrency_rescan.get()), var_java_rescan.get(), var_bedrock_rescan.get(),
        progress_var_rescan, progress_bar_rescan, text_results_rescan
    ), bg="#2196F3", fg="white", height=2).pack(fill="x", padx=10)

    tk.Label(tab_rescan, text="重新扫描结果:").pack(anchor="w", padx=10, pady=(10, 0))
    text_results_rescan.pack(fill="both", expand=True, padx=10, pady=5)

    root.mainloop()

if __name__ == "__main__":
    main()
