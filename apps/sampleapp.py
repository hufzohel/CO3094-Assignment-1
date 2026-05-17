#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
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
# 1. THE CENTRALIZED DATABASE (Tracker)
# ==========================================
TRACKER_FILE = "tracker_db.json"

def read_tracker():
    """Reads the central database. If it doesn't exist, returns an empty dict."""
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r") as f:
        try: 
            return json.load(f)
        except: 
            return {}

def write_tracker(data):
    """Saves updates to the central database."""
    with open(TRACKER_FILE, "w") as f:
        json.dump(data, f)

# ==========================================
# 2. THE LOCAL DEVICE STORAGE (P2P History)
# ==========================================
active_sessions = {} 
global_chat = []     
private_chats = {}   
MY_USERNAME = None
SERVER_PORT = None # Tracks the physical port this terminal is running on

def save_local_db():
    """Saves this peer's chat history to their own local hard drive."""
    if MY_USERNAME:
        with open(f"chat_db_{MY_USERNAME}.json", "w") as f:
            json.dump({"global": global_chat, "private": private_chats}, f)

def load_local_db(username):
    """Loads this peer's chat history from their local hard drive."""
    global global_chat, private_chats, MY_USERNAME
    MY_USERNAME = username
    fname = f"chat_db_{username}.json"
    if os.path.exists(fname):
        with open(fname, "r") as f:
            try:
                data = json.load(f)
                global_chat = data.get("global", [])
                private_chats = data.get("private", {})
            except:
                pass

def get_thread_id(user1, user2):
    """Sorts two usernames alphabetically to create a unique, shared vault key."""
    users = sorted([user1, user2])
    return f"{users[0]}_{users[1]}"

# ==========================================
# 3. THE SECURE BOUNCER
# ==========================================
def is_authenticated(headers):
    header_str = str(headers)
    if "session_id=" in header_str:
        try:
            parts = header_str.split("session_id=")
            extracted_id = parts[1].split(";")[0].strip(" '\"}")
            return active_sessions.get(extracted_id, False)
        except:
            return False
    return False

# ==========================================
# 4. THE HTTP WRAPPER
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
# 5. SECURE LOGIN ROUTE
# ==========================================
@app.route('/login', methods=['POST'])
async def login(headers="guest", body="anonymous"):
    try:
        credentials = json.loads(body)
        username = credentials.get("username")
        
        if username:
            session_id = str(uuid.uuid4())
            while session_id in active_sessions:
                session_id = str(uuid.uuid4())
            
            active_sessions[session_id] = username
            response_body = json.dumps({"status": "success", "message": f"Welcome, {username}"})
            
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
# 6. TRACKER MANAGEMENT (Central DB Writes)
# ==========================================
@app.route('/submit-info', methods=['POST'])
async def submit_info(headers="guest", body="anonymous"):
    current_user = is_authenticated(headers)
    if not current_user:
        return wrap_http({"status": "error", "message": "Unauthorized"})

    try:
        payload = json.loads(body)
        new_ip = payload.get("ip")
        new_port = str(payload.get("port"))
        
        if new_ip and new_port:
            active_peers = read_tracker()
            
            for peer, info in active_peers.items():
                if info["ip"] == new_ip and str(info["port"]) == new_port and peer != current_user:
                    return wrap_http({"status": "error", "message": "Address/Port already in use!"})
            
            active_peers[current_user] = {"ip": new_ip, "port": new_port}
            write_tracker(active_peers) 
            
            # Load this user's personal history from disk when they join
            load_local_db(current_user)
            
            return wrap_http({"status": "success", "message": f"{current_user} registered."})
        return wrap_http({"status": "error", "message": "Missing IP or Port"})
    except:
        return wrap_http({"status": "error", "message": "Invalid payload"})

@app.route('/get-list', methods=['GET'])
async def get_list(headers="guest", body="anonymous"):
    if not is_authenticated(headers):
        return wrap_http({"status": "error", "message": "Unauthorized"})
    
    active_peers = read_tracker() 
    return wrap_http({"status": "success", "active_peers": active_peers})

# ==========================================
# 7. RECEIVE FROM PEER (The Mailbox)
# ==========================================
@app.route('/send-peer', methods=['POST'])
async def send_peer(headers="guest", body="anonymous"):
    try:
        payload = json.loads(body)
        if not payload.get("message"):
            return wrap_http({"status": "error", "message": "Empty message"})

        # --- THE AUTO-RECOVERY FIX ---
        # If terminal is running but browser is closed, figure out who we are from the Tracker!
        if MY_USERNAME is None:
            active_peers = read_tracker()
            for peer, info in active_peers.items():
                if info.get("port") == SERVER_PORT:
                    load_local_db(peer)
                    break

        msg_obj = {
            "sender": payload.get("username", "Unknown"), 
            "message": payload.get("message", "")
        }

        if payload.get("is_direct"):
            target = payload.get("target_user")
            thread_id = get_thread_id(msg_obj["sender"], target)
            
            if thread_id not in private_chats:
                private_chats[thread_id] = []
            private_chats[thread_id].append(msg_obj)
        else:
            global_chat.append(msg_obj)

        save_local_db() # Save incoming message to local disk securely
        return wrap_http({"status": "delivered"})
    except:
        return wrap_http({"status": "error", "message": "Invalid format"})

# ==========================================
# 8. UPDATE FRONTEND SCREENS
# ==========================================
@app.route('/get-messages', methods=['GET'])
async def get_messages(headers="guest", body="anonymous"):
    return wrap_http({"status": "success", "messages": global_chat})

@app.route('/get-direct-messages', methods=['POST'])
async def get_direct_messages(headers="guest", body="anonymous"):
    current_user = is_authenticated(headers)
    if not current_user:
        return wrap_http({"status": "error", "message": "Unauthorized"})

    try:
        payload = json.loads(body)
        target_user = payload.get("target_user")
        
        if not target_user:
            return wrap_http({"status": "error", "message": "Missing target_user"})

        thread_id = get_thread_id(current_user, target_user)
        thread_history = private_chats.get(thread_id, [])
        
        return wrap_http({"status": "success", "messages": thread_history})
    except:
        return wrap_http({"status": "error", "message": "Invalid request"})

# ==========================================
# 9. THE BROADCASTER (Global)
# ==========================================
@app.route('/broadcast-peer', methods=['POST'])
async def broadcast_peer(headers="guest", body="anonymous"):
    current_user = is_authenticated(headers)
    if not current_user:
        return wrap_http({"status": "error", "message": "Unauthorized"})

    try:
        payload = json.loads(body)
        message = payload.get("message", "")
        
        if not message:
            return wrap_http({"status": "error", "message": "Empty message"})

        global_chat.append({"sender": current_user, "message": message})
        save_local_db() 

        broadcast_payload = json.dumps({
            "username": current_user, 
            "message": message, 
            "is_direct": False
        }).encode('utf-8')
        
        active_peers = read_tracker()
        for peer_name, info in active_peers.items():
            if peer_name == current_user:
                continue
            url = f"http://{info['ip']}:{info['port']}/send-peer"
            try:
                req = urllib.request.Request(url, data=broadcast_payload, method='POST')
                req.add_header('Content-Type', 'application/json')
                await asyncio.to_thread(urllib.request.urlopen, req, timeout=2)
            except Exception:
                pass 

        return wrap_http({"status": "broadcast complete"})
    except json.JSONDecodeError:
        return wrap_http({"status": "error", "message": "Invalid format"})

# ==========================================
# 10. DIRECT MESSAGE (Sniper Rifle)
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

        active_peers = read_tracker() 

        if target_user not in active_peers:
            return wrap_http({"status": "error", "message": "Target user not found on tracker"})

        thread_id = get_thread_id(current_user, target_user)
        if thread_id not in private_chats:
            private_chats[thread_id] = []
            
        private_chats[thread_id].append({
            "sender": current_user, 
            "message": message
        })
        save_local_db() 

        direct_payload = json.dumps({
            "username": current_user, 
            "target_user": target_user, 
            "message": message, 
            "is_direct": True
        }).encode('utf-8')
        
        target_info = active_peers[target_user]
        url = f"http://{target_info['ip']}:{target_info['port']}/send-peer"
        
        try:
            req = urllib.request.Request(url, data=direct_payload, method='POST')
            req.add_header('Content-Type', 'application/json')
            await asyncio.to_thread(urllib.request.urlopen, req, timeout=2)
            return wrap_http({"status": "success", "message": "Direct message sent"})
        except Exception as e:
            # THIS IS WHERE ALICE FINDS OUT CHARLIE'S TERMINAL IS OFF
            return wrap_http({"status": "error", "message": f"Peer offline or unreachable. (Target Terminal is off)"})

    except json.JSONDecodeError:
        return wrap_http({"status": "error", "message": "Invalid format"})

def create_sampleapp(ip, port):
    global SERVER_PORT
    SERVER_PORT = str(port) # Lock in the port so Auto-Recovery knows who it is!
    app.prepare_address(ip, port)
    app.run()