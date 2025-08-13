import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from mcstatus import JavaServer, BedrockServer

RESULT_FILE = "scan_results.txt"
semaphore = None

def safe_insert_result(text_widget, result, description=None):
    """Safely insert results into the text widget from any thread."""
    if description:
        text_widget.insert(tk.END, result + "\n")
        text_widget.insert(tk.END, f"描述: {description}\n\n")
    else:
        text_widget.insert(tk.END, result + "\n")
    text_widget.see(tk.END)

async def scan_server(host, port, server_type, progress_var, total_tasks, text_results, root):
    """Async function to scan a single Minecraft server."""
    async with semaphore:
        try:
            result = None
            description = None
            if server_type == "java":
                server = JavaServer(host, port)
                status = await asyncio.wait_for(server.async_status(), timeout=3)
                description = getattr(status.description, 'clean', str(status.description))
                result = f"[Java] {host}:{port} | 版本: {status.version.name} | 玩家: {status.players.online}/{status.players.max}"
            elif server_type == "bedrock":
                server = BedrockServer(host, port)
                status = await asyncio.wait_for(server.async_status(), timeout=5)
                
                players_online = getattr(status.players, 'online', '?')
                players_max = getattr(status.players, 'max', '?')
                
                # Get a more concise description for Bedrock servers
                motd_obj = getattr(status, 'motd', None)
                if motd_obj and getattr(motd_obj, 'clean', None):
                    description = motd_obj.clean.strip()
                elif motd_obj and getattr(motd_obj, 'raw', None):
                    description = motd_obj.raw.strip()
                else:
                    description = "N/A"

                result = f"[Bedrock] {host}:{port} | 版本: {status.version.name} | 玩家: {players_online}/{players_max}"

            if result:
                root.after(0, safe_insert_result, text_results, result, description)
                with open(RESULT_FILE, "a", encoding="utf-8") as f:
                    f.write(result + "\n")
                    if description:
                        f.write(f"描述: {description}\n\n")
        except:
            pass
        finally:
            progress_var.set(progress_var.get() + 1)
            root.after(0, lambda: progress_bar.config(value=(progress_var.get() / total_tasks) * 100))

async def start_scan_async(ip_list, port_start, port_end, scan_java, scan_bedrock, concurrency, text_results, root):
    """Main async function to manage the scanning tasks."""
    global semaphore
    semaphore = asyncio.Semaphore(concurrency)
    open(RESULT_FILE, "w", encoding="utf-8").close()

    tasks = []
    for ip in ip_list:
        ip = ip.strip()
        for port in range(port_start, port_end + 1):
            if scan_java:
                tasks.append((ip, port, "java"))
            if scan_bedrock:
                tasks.append((ip, port, "bedrock"))

    if not tasks:
        root.after(0, lambda: messagebox.showerror("错误", "没有需要扫描的任务"))
        return

    total_tasks = len(tasks)
    progress_var.set(0)
    progress_bar['value'] = 0

    await asyncio.gather(*(scan_server(h, p, t, progress_var, total_tasks, text_results, root) for h, p, t in tasks))
    root.after(0, lambda: messagebox.showinfo("完成", "扫描完成！结果已保存到 scan_results.txt"))

def run_scan():
    """Starts the scan in a separate thread."""
    ip_text = text_ips.get("1.0", tk.END).strip()
    if not ip_text:
        messagebox.showerror("错误", "请输入至少一个 IP 或域名")
        return

    try:
        port_start, port_end = map(int, entry_ports.get().split("-"))
    except:
        messagebox.showerror("错误", "端口范围格式不正确，示例：20000-25000")
        return

    concurrency = int(entry_concurrency.get())
    scan_java = var_java.get()
    scan_bedrock = var_bedrock.get()
    ip_list = ip_text.splitlines()

    text_results.delete("1.0", tk.END)

    threading.Thread(
        target=lambda: asyncio.run(
            start_scan_async(ip_list, port_start, port_end, scan_java, scan_bedrock, concurrency, text_results, root)
        ),
        daemon=True
    ).start()

# -------------------- GUI --------------------
root = tk.Tk()
root.title("Minecraft 多IP端口扫描器")
root.geometry("650x600")

tk.Label(root, text="目标IP/域名（每行一个）:").pack(anchor="w", padx=10, pady=(10, 0))
text_ips = tk.Text(root, height=5)
text_ips.pack(fill="x", padx=10)

tk.Label(root, text="端口范围 (如 20000-25000):").pack(anchor="w", padx=10, pady=(10, 0))
entry_ports = tk.Entry(root)
entry_ports.insert(0, "20000-25000")
entry_ports.pack(fill="x", padx=10)

frame_opts = tk.Frame(root)
frame_opts.pack(pady=5, anchor="w", padx=10)
var_java = tk.BooleanVar(value=True)
var_bedrock = tk.BooleanVar(value=True)
tk.Checkbutton(frame_opts, text="扫描Java版", variable=var_java).pack(side="left", padx=5)
tk.Checkbutton(frame_opts, text="扫描基岩版", variable=var_bedrock).pack(side="left", padx=5)

tk.Label(root, text="最大并发数:").pack(anchor="w", padx=10, pady=(10, 0))
entry_concurrency = tk.Entry(root)
entry_concurrency.insert(0, "100")
entry_concurrency.pack(fill="x", padx=10)

progress_var = tk.IntVar(value=0)
progress_bar = ttk.Progressbar(root, length=500)
progress_bar.pack(pady=15, padx=10)

tk.Button(root, text="开始扫描", command=run_scan, bg="#4CAF50", fg="white", height=2).pack(fill="x", padx=10)

tk.Label(root, text="扫描结果:").pack(anchor="w", padx=10, pady=(10, 0))
text_results = tk.Text(root, height=15)
text_results.pack(fill="both", expand=True, padx=10, pady=5)

root.mainloop()