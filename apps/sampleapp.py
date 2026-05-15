#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#

"""
app.sampleapp
~~~~~~~~~~~~~~~~~
"""

import sys
import os
import importlib.util
import urllib.request
import urllib.error
import json
import uuid
import asyncio
from daemon import AsynapRous

app = AsynapRous()

# ==========================================
# 1. THE IN-MEMORY DATABASES
# ==========================================
active_peers = {}
active_sessions = {} # Maps secure UUIDs to usernames
chat_history = []

# ==========================================
# 2. THE SECURE BOUNCER
# ==========================================
def is_authenticated(headers):
    """
    Checks the incoming HTTP headers for the 'session_id' cookie.
    Looks up the secure ID in the server's vault.
    """
    header_str = str(headers)
    if "session_id=" in header_str:
        try:
            parts = header_str.split("session_id=")
            extracted_id = parts[1].split(";")[0].strip(" '\"}")
            
            # Check the vault for the real username
            return active_sessions.get(extracted_id, False)
        except:
            return False
    return False

# ==========================================
# 3. THE HTTP WRAPPER
# ==========================================
def wrap_http(response_dict):
    body = json.dumps(response_dict)
    raw_http = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
        f"{body}"
    )
    return raw_http.encode("utf-8")

# ==========================================
# 4. SECURE LOGIN ROUTE
# ==========================================
@app.route('/login', methods=['POST'])
async def login(headers="guest", body="anonymous"):
    try:
        credentials = json.loads(body)
        username = credentials.get("username")
        
        if username:
            # 1. Generate an unguessable Session ID
            session_id = str(uuid.uuid4())
            
            # 2. Store the truth in the server's memory vault
            active_sessions[session_id] = username
            
            response_body = json.dumps({"status": "success", "message": f"Welcome, {username}"})
            
            # 3. Give the browser the secure ID AND the UI helper cookie
            raw_http = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Set-Cookie: session_id={session_id}; Path=/\r\n"
                f"Set-Cookie: session_user={username}; Path=/\r\n"
                f"Content-Length: {len(response_body)}\r\n\r\n"
                f"{response_body}"
            )
            return raw_http.encode("utf-8")
        else:
            return wrap_http({"status": "error", "message": "Missing username"})
            
    except json.JSONDecodeError:
        return wrap_http({"status": "error", "message": "Invalid JSON"})

# ==========================================
# 5. TRACKER MANAGEMENT
# ==========================================
@app.route('/submit-info', methods=['POST'])
async def submit_info(headers="guest", body="anonymous"):
    current_user = is_authenticated(headers)
    if not current_user:
        return wrap_http({"status": "error", "message": "Unauthorized"})

    try:
        payload = json.loads(body)
        if payload.get("ip") and payload.get("port"):
            active_peers[current_user] = {"ip": payload.get("ip"), "port": payload.get("port")}
            return wrap_http({"status": "success", "message": f"{current_user} registered."})
        return wrap_http({"status": "error", "message": "Missing IP or Port"})
    except:
        return wrap_http({"status": "error", "message": "Invalid payload"})

@app.route('/get-list', methods=['GET'])
async def get_list(headers="guest", body="anonymous"):
    if not is_authenticated(headers):
        return wrap_http({"status": "error", "message": "Unauthorized"})
    return wrap_http({"status": "success", "active_peers": active_peers})

# ==========================================
# 6. RECEIVE FROM PEER (The Mailbox)
# ==========================================
@app.route('/send-peer', methods=['POST'])
async def send_peer(headers="guest", body="anonymous"):
    try:
        payload = json.loads(body)
        if payload.get("message"):
            chat_history.append({
                "sender": payload.get("username", "Unknown"), 
                "message": payload.get("message", ""), 
                "channel": payload.get("channel", "general"),
                "is_direct": payload.get("is_direct", False)
            })
            return wrap_http({"status": "delivered"})
        return wrap_http({"status": "error", "message": "Empty message"})
    except:
        return wrap_http({"status": "error", "message": "Invalid format"})

# ==========================================
# 7. UPDATE FRONTEND SCREEN
# ==========================================
@app.route('/get-messages', methods=['GET'])
async def get_messages(headers="guest", body="anonymous"):
    return wrap_http({"status": "success", "messages": chat_history})

# ==========================================
# 8. THE BROADCASTER (P2P Shotgun)
# ==========================================
@app.route('/broadcast-peer', methods=['POST'])
async def broadcast_peer(headers="guest", body="anonymous"):
    current_user = is_authenticated(headers)
    if not current_user:
        return wrap_http({"status": "error", "message": "Unauthorized"})

    try:
        payload = json.loads(body)
        message = payload.get("message", "")
        channel = payload.get("channel", "general") 
        
        if not message:
            return wrap_http({"status": "error", "message": "Empty message"})

        chat_history.append({"sender": current_user, "message": message, "channel": channel, "is_direct": False})

        broadcast_payload = json.dumps({
            "username": current_user, 
            "message": message, 
            "channel": channel,
            "is_direct": False
        }).encode('utf-8')
        
        for peer_name, info in active_peers.items():
            if peer_name == current_user:
                continue
                
            url = f"http://{info['ip']}:{info['port']}/send-peer"
            
            try:
                req = urllib.request.Request(url, data=broadcast_payload, method='POST')
                req.add_header('Content-Type', 'application/json')
                
                # ASYNC FIX: Yield control to the Event Loop while the network request fires
                await asyncio.to_thread(urllib.request.urlopen, req, timeout=2)
            except Exception:
                pass 

        return wrap_http({"status": "broadcast complete"})

    except json.JSONDecodeError:
        return wrap_http({"status": "error", "message": "Invalid format"})

# ==========================================
# 9. DIRECT MESSAGE (P2P Sniper Rifle)
# ==========================================
@app.route('/direct-peer', methods=['POST'])
async def direct_peer(headers="guest", body="anonymous"):
    current_user = is_authenticated(headers)
    if not current_user:
        return wrap_http({"status": "error", "message": "Unauthorized"})

    try:
        payload = json.loads(body)
        message = payload.get("message", "")
        target_user = payload.get("target_user", "")
        
        if not message or not target_user:
            return wrap_http({"status": "error", "message": "Missing message or target"})

        if target_user not in active_peers:
            return wrap_http({"status": "error", "message": "Target user not found on tracker"})

        # Add to your own screen so you can see what you sent
        chat_history.append({"sender": f"{current_user} (To {target_user})", "message": message, "channel": "direct", "is_direct": True})

        # Build payload for the target
        direct_payload = json.dumps({
            "username": f"{current_user} (Private)", 
            "message": message, 
            "channel": "direct",
            "is_direct": True
        }).encode('utf-8')
        
        # Get target's specific address
        target_info = active_peers[target_user]
        url = f"http://{target_info['ip']}:{target_info['port']}/send-peer"
        
        try:
            req = urllib.request.Request(url, data=direct_payload, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            # ASYNC FIX: Shoot the direct message without blocking
            await asyncio.to_thread(urllib.request.urlopen, req, timeout=2)
            return wrap_http({"status": "success", "message": "Direct message sent"})
        except Exception as e:
            return wrap_http({"status": "error", "message": f"Failed to reach peer: {str(e)}"})

    except json.JSONDecodeError:
        return wrap_http({"status": "error", "message": "Invalid format"})

def create_sampleapp(ip, port):
    app.prepare_address(ip, port)
    app.run()