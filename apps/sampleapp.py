#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
app.sampleapp
~~~~~~~~~~~~~~~~~

"""

import sys
import os
import importlib.util
import json
from daemon import AsynapRous

app = AsynapRous()

# ==========================================
# 1. THE IN-MEMORY TRACKER (Your "Database")
# ==========================================
# This dictionary stores the active users. 
# Format: {"username": {"ip": "192.168.1.5", "port": 5000}}
active_peers = {}

# ==========================================
# 1.5 THE BOUNCER (Authentication Helper)
# ==========================================
def is_authenticated(headers):
    """
    Checks the incoming HTTP headers for the 'session_user' cookie.
    Returns the username if found, otherwise returns False.
    """
    header_str = str(headers)
    if "session_user=" in header_str:
        try:
            parts = header_str.split("session_user=")
            username = parts[1].split(";")[0].strip(" '\"}")
            return username
        except:
            return False
    return False


# ==========================================
# 2. THE LOGIN SWITCH (Cookie Issuer)
# ==========================================
@app.route('/login', methods=['POST'])
async def login(headers="guest", body="anonymous"):
    try:
        credentials = json.loads(body)
        username = credentials.get("username")
        
        if username:
            response_body = json.dumps({"status": "success", "message": f"Welcome, {username}"})
            
            # Manually craft the response to force the Set-Cookie header
            raw_http = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Set-Cookie: session_user={username}; Path=/; HttpOnly\r\n"
                f"Content-Length: {len(response_body)}\r\n\r\n"
                f"{response_body}"
            )
            return raw_http.encode("utf-8")
        else:
            return json.dumps({"status": "error", "message": "Missing username"}).encode("utf-8")
            
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON"}).encode("utf-8")


# ==========================================
# 3. PEER REGISTRATION (Protected)
# ==========================================
@app.route('/submit-info', methods=['POST'])
async def submit_info(headers="guest", body="anonymous"):
    # 1. Check for the wristband
    current_user = is_authenticated(headers)
    if not current_user:
        return json.dumps({"status": "error", "message": "Unauthorized"}).encode("utf-8")

    # 2. If they have it, register them
    try:
        payload = json.loads(body)
        ip = payload.get("ip")
        port = payload.get("port")
        
        if ip and port:
            active_peers[current_user] = {"ip": ip, "port": port}
            return json.dumps({"status": "success", "message": f"{current_user} registered."}).encode("utf-8")
        else:
            return json.dumps({"status": "error", "message": "Missing IP or Port"}).encode("utf-8")

    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid payload"}).encode("utf-8")

# ==========================================
# 4. PEER DISCOVERY (Protected)
# ==========================================
@app.route('/get-list', methods=['GET'])
async def get_list(headers="guest", body="anonymous"):
    # Check for the wristband
    if not is_authenticated(headers):
        return json.dumps({"status": "error", "message": "Unauthorized"}).encode("utf-8")
        
    data = {
        "status": "success",
        "active_peers": active_peers
    }
    return json.dumps(data).encode("utf-8")


# ==========================================
# 5. LOCAL CHAT STORAGE
# ==========================================
# This stores the messages for YOUR specific screen.
chat_history = []

# ==========================================
# 6. RECEIVE FROM PEER (NON-BLOCKING)
# ==========================================
# Notice the 'async def' instead of just 'def'
@app.route('/send-peer', methods=['POST'])
async def send_peer(headers="guest", body="anonymous"):
    """
    Asynchronous receiver. This allows the server to handle 
    hundreds of incoming messages simultaneously without freezing.
    """
    try:
        payload = json.loads(body)
        sender = payload.get("username", "Unknown")
        message = payload.get("message", "")
        
        if message:
            chat_history.append({"sender": sender, "message": message})
            print(f"[P2P Message] {sender}: {message}")
            return json.dumps({"status": "delivered"}).encode("utf-8")
        else:
            return json.dumps({"status": "error", "message": "Empty message"}).encode("utf-8")

    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid format"}).encode("utf-8")

# ==========================================
# 7. UPDATE FRONTEND SCREEN (NON-BLOCKING)
# ==========================================
@app.route('/get-messages', methods=['GET'])
async def get_messages(headers="guest", body="anonymous"):
    data = {
        "status": "success",
        "messages": chat_history
    }
    return json.dumps(data).encode("utf-8")

def create_sampleapp(ip, port):
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()
