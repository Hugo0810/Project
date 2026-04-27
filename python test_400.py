import socket

# 建立與伺服器的連線
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 8080))

# 關鍵：故意發送格式錯誤的請求！
# 正常的請求應該是 "GET / HTTP/1.1"，我們故意只發送 "GET /" (只有兩個部分)
s.sendall(b"GET /\r\n\r\n")

# 印出伺服器的回應
print("--- 收到來自伺服器的回應 ---")
print(s.recv(1024).decode())
s.close()