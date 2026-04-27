import socket
import threading
import os
import time
from datetime import datetime
import urllib.parse
import mimetypes
import email.utils

LOG_FILE = "server_log.txt"
DOCUMENT_ROOT = "./www"  # 伺服器的檔案系統根目錄 [cite: 10]


def write_log(client_ip, access_time, requested_file, response_status):
    """將每一筆請求記錄寫入日誌檔 [cite: 26, 27]"""
    log_entry = f"{client_ip} - [{access_time}] - {requested_file} - {response_status}\n"
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)
    print(log_entry.strip())


def handle_client(client_socket, client_address):
    """每個執行緒負責處理一個 HTTP 請求 [cite: 54]"""
    client_ip = client_address[0]
    try:
        # 從連線接收 HTTP 請求 [cite: 13]
        request_data = client_socket.recv(4096).decode('utf-8')
        if not request_data:
            return

        access_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 解析請求以確定特定檔案
        lines = request_data.split('\r\n')
        request_line = lines[0].split()

        if len(request_line) < 3:
            # 處理 400 Bad Request
            response = "HTTP/1.1 400 Bad Request\r\n\r\n"
            client_socket.sendall(response.encode())
            write_log(client_ip, access_time, "Unknown", "400 Bad Request")
            return

        method, path, version = request_line
        requested_file = urllib.parse.unquote(path)

        if path == '/':
            requested_file = '/index.html'

        filepath = DOCUMENT_ROOT + requested_file

        # 解析 Headers [cite: 58, 59]
        headers = {}
        for line in lines[1:]:
            if ': ' in line:
                key, value = line.split(': ', 1)
                headers[key] = value


        # 檢查伺服器檔案系統中是否存在該檔案 [cite: 10, 19]
        if not os.path.exists(filepath):
            # 回傳 404 Not Found 錯誤訊息 [cite: 19, 57]
            response_body = "<html><body><h1>404 Not Found</h1></body></html>"
            response_header = "HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n"
            client_socket.sendall((response_header + response_body).encode())
            write_log(client_ip, access_time, requested_file, "404 Not Found")
            return




        # 處理 GET 或 HEAD 請求
        if method in ['GET', 'HEAD']:
            # 1. 取得檔案最後修改時間 (用於 304 和 Last-Modified)
            file_mtime_ts = os.path.getmtime(filepath)
            last_modified_str = email.utils.formatdate(file_mtime_ts, usegmt=True)

            # 2. 檢查 304 Not Modified
            if 'If-Modified-Since' in headers:
                if_modified_since_str = headers['If-Modified-Since']
                if_modified_since_tuple = email.utils.parsedate(if_modified_since_str)
                if if_modified_since_tuple:
                    if_modified_since_ts = time.mktime(if_modified_since_tuple)
                    # 如果檔案修改時間 <= 客戶端紀錄的時間，代表檔案沒變更
                    if int(file_mtime_ts) <= int(if_modified_since_ts):
                        response_header = "HTTP/1.1 304 Not Modified\r\n"
                        response_header += f"Last-Modified: {last_modified_str}\r\n"
                        connection_header = headers.get('Connection', 'close')
                        response_header += f"Connection: {connection_header}\r\n\r\n"

                        client_socket.sendall(response_header.encode())
                        write_log(client_ip, access_time, requested_file, "304 Not Modified")
                        if connection_header.lower() != 'keep-alive':
                            client_socket.close()
                        return

            # 3. 嘗試打開檔案，讀取內容 (若無權限則觸發 403)
            try:
                with open(filepath, 'rb') as f:
                    file_content = f.read()
            except PermissionError:
                response_body = "<html><body><h1>403 Forbidden</h1></body></html>"
                response_header = "HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n"
                client_socket.sendall((response_header + response_body).encode())
                write_log(client_ip, access_time, requested_file, "403 Forbidden")
                return

            # 4. 判斷檔案的 Content-Type
            content_type, _ = mimetypes.guess_type(filepath)
            if content_type is None:
                content_type = 'application/octet-stream'

            # 5. 組合完整的 200 OK 標頭 (確保 GET 和 HEAD 都有這些標頭)
            response_header = "HTTP/1.1 200 OK\r\n"
            response_header += f"Content-Length: {len(file_content)}\r\n"
            response_header += f"Content-Type: {content_type}\r\n"
            response_header += f"Last-Modified: {last_modified_str}\r\n"
            response_header += "Cache-Control: max-age=3600\r\n"

            # 處理連線標頭
            connection_header = headers.get('Connection', 'close')
            response_header += f"Connection: {connection_header}\r\n\r\n"

            # 6. 透過 TCP 連線發送回應給客戶端
            client_socket.sendall(response_header.encode())

            # 7. 關鍵：只有 GET 指令才發送檔案內容！這就是 HEAD 的作用！
            if method == 'GET':
                client_socket.sendall(file_content)

            write_log(client_ip, access_time, requested_file, "200 OK")

            if connection_header.lower() != 'keep-alive':
                client_socket.close()

    except Exception as e:
        print(f"Error handling client {client_ip}: {e}")
    finally:
        client_socket.close()


def start_server(host='127.0.0.1', port=8080):
    if not os.path.exists(DOCUMENT_ROOT):
        os.makedirs(DOCUMENT_ROOT)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Server started on {host}:{port}...")

    try:
        while True:
            # 在被客戶端聯繫時建立連線 socket [cite: 12]
            client_socket, client_address = server_socket.accept()
            print(f"Accepted connection from {client_address}")
            # 實作多執行緒，同時處理多個請求 [cite: 8]
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            client_thread.start()
    except KeyboardInterrupt:
        print("Shutting down server.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()