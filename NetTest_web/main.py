import http.server
import socketserver
import os
import sys
import threading
import subprocess
import time
import json
import webbrowser
# import signal

# --- Helper for PyInstaller paths ---
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Check base path first
    full_path = os.path.join(base_path, relative_path)
    if os.path.exists(full_path):
        return full_path
        
    # Fallback to sys.executable directory (useful for onedir mode / side-by-side files)
    exe_dir = os.path.dirname(sys.executable)
    alt_path = os.path.join(exe_dir, relative_path)
    if os.path.exists(alt_path):
        return alt_path
        
    # Return original logic if not found (let it fail later or assume CWD)
    return full_path

# Configuration
PORT = 8000
HTML_FILE = get_resource_path("front-end.html")

# Global state
iperf_process = None
running = False
log_history = []
msg_queue = []  # Queue for SSE messages

def add_log(message):
    """Add log to history and queue for SSE"""
    global log_history, msg_queue
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S] ", time.localtime())
    full_msg = timestamp + message
    log_history.append(full_msg)
    # Keep history size reasonable
    if len(log_history) > 5000:
        log_history = log_history[-5000:]
    msg_queue.append(full_msg)
    # Prevent memory leak in msg_queue (limit to 10000)
    if len(msg_queue) > 10000:
        msg_queue = msg_queue[-10000:]

def run_iperf_thread(cmd_list):
    """Execution thread handling Windows/Linux differences"""
    global iperf_process, running

    running = True
    add_log(f"Starting command: {' '.join(cmd_list)}")
    
    is_windows = sys.platform == 'win32'
    
    # Packaged iperf3 needs its directory in PATH to find bundled DLLs (cygwin1.dll)
    my_env = os.environ.copy()
    if cmd_list and len(cmd_list) > 0 and os.path.isabs(cmd_list[0]):
        exe_dir = os.path.dirname(cmd_list[0])
        my_env["PATH"] = exe_dir + os.pathsep + my_env.get("PATH", "")
    
    try:
        if is_windows:
            # WINDOWS: Use startupinfo to hide window, standard PIPE
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # Windows buffering needs specific handling or just standard polling
            iperf_process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, # 改为 DEVNULL 防止 Bad file descriptor
                startupinfo=startupinfo,
                text=True,
                bufsize=1,  # Line buffering
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8', # 强制 UTF-8
                errors='replace',  # 忽略编码错误
                env=my_env
            )
            
            # Read line by line
            while iperf_process and iperf_process.poll() is None:
                line = iperf_process.stdout.readline()
                if line:
                    add_log(line.strip())
        else:
            # LINUX/MACOS: Switch between PTY and PIPE based on availability
            # PTY is preferred for line buffering behavior in some tools
            try:
                import pty
                master_fd, slave_fd = pty.openpty()
                
                iperf_process = subprocess.Popen(
                    cmd_list,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    stdin=subprocess.PIPE,
                    text=True,
                    close_fds=True
                )
                os.close(slave_fd) # Close slave in parent
                
                # Read from master_fd
                master_file = os.fdopen(master_fd, 'r', encoding='utf-8', errors='replace')
                
                while iperf_process and iperf_process.poll() is None:
                    try:
                        # Blocking read creates issues if process dies, so we use select or simple readline in thread
                        # os.read allows us to read partial chunks without waiting for newlines if needed,
                        # but here we prefer lines.
                        line = master_file.readline()
                        if line:
                            add_log(line.strip())
                        else:
                            break
                    except (IOError, OSError):
                        break
            except ImportError:
                # Fallback if pty not available
                iperf_process = subprocess.Popen(
                     cmd_list,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT,
                     text=True,
                     bufsize=1
                )
                while iperf_process and iperf_process.poll() is None:
                    line = iperf_process.stdout.readline()
                    if line:
                        add_log(line.strip())
                    
    except Exception as e:
        add_log(f"Execution Error: {str(e)}")
    finally:
        running = False
        add_log("Process finished.")
        iperf_process = None

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            if os.path.exists(HTML_FILE):
                with open(HTML_FILE, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"Error: front-end.html not found.")
            return
            
        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            # Send initial history
            # (Optional: send only recent lines to avoid huge payload on reconnect)
            for line in log_history[-50:]: 
                self.wfile.write(f"data: {line}\n\n".encode('utf-8'))
            self.wfile.flush()
                
            last_idx = len(msg_queue)
            
            try:
                while True:
                    # Check for new messages
                    current_len = len(msg_queue)
                    if current_len > last_idx:
                        for i in range(last_idx, current_len):
                            msg = msg_queue[i]
                            # Sanitize msg Newlines for SSE compatibility (data: ... \n\n)
                            # Or just assume single line? iperf sometimes outputs multi lines?
                            # Usually readline gives single line.
                            self.wfile.write(f"data: {msg}\n\n".encode('utf-8'))
                        self.wfile.flush()
                        last_idx = current_len
                    time.sleep(0.1)
            except (ConnectionAbortedError, BrokenPipeError):
                pass
            return

        # Serve other static files if needed
        return super().do_GET()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        # Declare globals at the top of the function to avoid SyntaxError
        global iperf_process, log_history, msg_queue, running
        
        response = {"status": "ok", "msg": ""}
        
        if self.path == '/api/start':
            if running:
                response = {"status": "error", "msg": "Already running"}
            else:
                cmd_str = data.get('command', 'iperf3 -v')
                import shlex
                cmd_parts = shlex.split(cmd_str)
                
                # --- Resolve iperf3 path ---
                iperf_exe = "iperf3.exe" if sys.platform == 'win32' else "iperf3"
                iperf_path = get_resource_path(iperf_exe)
                
                if cmd_parts and cmd_parts[0] == 'iperf3':
                    if os.path.exists(iperf_path):
                        cmd_parts[0] = iperf_path
                    else:
                        print(f"[Warning] Bundled {iperf_exe} not found at {iperf_path}, using system PATH.")

                t = threading.Thread(target=run_iperf_thread, args=(cmd_parts,), daemon=True)
                t.start()
                response = {"status": "ok", "msg": "Started"}
                
        elif self.path == '/api/stop':
            if iperf_process:
                try:
                    iperf_process.terminate()
                    response = {"status": "ok", "msg": "Stopping..."}
                except Exception as e:
                    response = {"status": "warning", "msg": f"Process already stopped or error: {e}"}
            else:
                 response = {"status": "error", "msg": "Not running"}

        elif self.path == '/api/clear':
            log_history = []
            msg_queue = []
            response = {"status": "ok", "msg": "Cleared"}

        elif self.path == '/api/shutdown':
            if iperf_process:
                try:
                    iperf_process.terminate()
                except Exception:
                    pass
            
            def kill_server():
                time.sleep(1)
                os._exit(0)
            
            threading.Thread(target=kill_server, daemon=True).start()
            response = {"status": "ok", "msg": "Shutting down"}

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        # Silence default server logging to console to keep it clean
        pass

def open_browser():
    time.sleep(1)
    webbrowser.open(f'http://localhost:{PORT}')

if __name__ == '__main__':
    # Ensure CWD is script directory - DISABLED for PyInstaller compatibility
    # os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print(f"Starting lightweight server on http://localhost:{PORT}")
    print("Press Ctrl+C to exit")
    
    # Launch browser in separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Use ThreadingTCPServer to handle SSE (long polling) and API requests concurrently
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    
    try:
        # Bind to localhost for security
        with socketserver.ThreadingTCPServer(("localhost", PORT), RequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if iperf_process:
            iperf_process.terminate()
