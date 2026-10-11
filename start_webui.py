import os
import sys
import time
import socket
import webbrowser
import threading

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(REPO_ROOT)

def find_available_port(start_port=7860, max_attempts=20):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def open_browser_delayed(url, delay=1.5):
    def _open():
        time.sleep(delay)
        print(f"\n[WebUI] 正在浏览器中自动打开界面: {url}")
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

def main():
    print("=" * 60)
    print("    SAM 3D Body & MHR 3D 骨架姿态估计工作台 (Phase 1 独立版)")
    print("=" * 60)
    print("[1/3] 正在检测端口与网络服务...")
    port = find_available_port(7860)
    url = f"http://127.0.0.1:{port}"
    print(f"[WebUI] 绑定服务地址: {url}")

    from webui.app import app, get_runner

    print("[2/3] 正在加载 GPU 模型与 MHR 资产 (仅首次启动需要)...")
    get_runner()
    print("[2/3] 模型就绪！显存预热完成。")

    print(f"[3/3] 启动本地 Web 服务器，即将弹出浏览器...")
    open_browser_delayed(url, delay=1.2)
    print("-" * 60)
    print(f" 服务已运行！请在浏览器访问: {url}")
    print(" 按 Ctrl + C 可停止服务。")
    print("-" * 60)

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
