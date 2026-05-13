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
# 2. THE LOGIN SWITCH
# ==========================================
@app.route('/login', methods=['POST'])
async def login(headers="guest", body="anonymous"):
    """
    Reads credentials from the client.
    For the MVP, we just accept the username and return a success message.
    (Note: True RFC 6265 implementation requires modifying the framework's Set-Cookie header).
    """
    print(f"[SampleApp] Login attempt: {body}")
    
    try:
        credentials = json.loads(body)
        username = credentials.get("username")
        
        if username:
            # In a full build, you would generate a session token here.
            data = {"status": "success", "message": f"Welcome, {username}"}
            return json.dumps(data).encode("utf-8")
        else:
            return json.dumps({"status": "error", "message": "Missing username"}).encode("utf-8")
            
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON"}).encode("utf-8")


# ==========================================
# 3. PEER REGISTRATION
# ==========================================
@app.route('/submit-info', methods=['POST'])
async def submit_info(headers="guest", body="anonymous"):
    """
    When a peer logs in, they hit this endpoint with their listening IP and Port.
    We add them to the active_peers dictionary.
    """
    print(f"[SampleApp] Received peer info: {body}")
    
    try:
        payload = json.loads(body)
        username = payload.get("username")
        ip = payload.get("ip")
        port = payload.get("port")
        
        if username and ip and port:
            # Register the peer in the tracker
            active_peers[username] = {"ip": ip, "port": port}
            data = {"status": "success", "message": f"{username} registered in tracker."}
            return json.dumps(data).encode("utf-8")
        else:
            return json.dumps({"status": "error", "message": "Missing IP, Port, or Username"}).encode("utf-8")

    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON payload"}).encode("utf-8")


# ==========================================
# 4. PEER DISCOVERY
# ==========================================
@app.route('/get-list', methods=['GET'])
async def get_list(headers="guest", body="anonymous"):
    """
    Peers call this to find out who else is online to establish P2P connections.
    Returns the entire active_peers dictionary.
    """
    print(f"[SampleApp] Sending peer list. Current peers: {len(active_peers)}")
    
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
