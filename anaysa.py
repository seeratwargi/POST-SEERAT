from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import requests
import time
import random
import threading
import json
import os
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Global variables for task management
active_sessions = {}
session_tasks = {}
session_logs = {}

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,/;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
    'referer': 'www.google.com'
}

def generate_session_id():
    return secrets.token_hex(8)

def validate_facebook_token(token):
    """Facebook token validate karta hai"""
    try:
        url = f"https://graph.facebook.com/v15.0/me?access_token={token}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            user_data = response.json()
            return {'valid': True, 'name': user_data.get('name', 'Unknown User'), 'id': user_data.get('id')}
        return {'valid': False}
    except:
        return {'valid': False}

def extract_page_tokens(main_token, token_name="Main Token"):
    """Facebook pages ke tokens automatically extract karta hai"""
    try:
        url = f"https://graph.facebook.com/v15.0/me/accounts?access_token={main_token}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            page_tokens = []
            
            if 'data' in data:
                for page in data['data']:
                    page_info = {
                        'name': f"{page.get('name', 'Unknown Page')} (Page)",
                        'token': page.get('access_token', ''),
                        'id': page.get('id', ''),
                        'parent_token': main_token,
                        'parent_name': token_name,
                        'type': 'page'
                    }
                    page_tokens.append(page_info)
            
            return page_tokens
        return []
    except:
        return []

def add_log(session_id, message, log_type="info"):
    """Session ke logs add karta hai"""
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    log_entry = f"[{timestamp}] {message}"
    
    if session_id not in session_logs:
        session_logs[session_id] = []
    
    session_logs[session_id].append({"message": log_entry, "type": log_type})
    
    # Keep only last 1000 logs
    if len(session_logs[session_id]) > 1000:
        session_logs[session_id] = session_logs[session_id][-1000:]
    
    print(log_entry)

def run_commenting_task(session_id, data):
    """Main commenting task run karta hai with loop shifting"""
    thread_id = data['thread_id']
    haters_name = data['haters_name']
    speed = data['speed']
    normal_tokens = data['normal_tokens']
    shifting_tokens = data.get('shifting_tokens', [])
    shifting_time = data.get('shifting_time', 0)
    messages = data['messages']
    
    add_log(session_id, f"🚀 Task started for Post ID: {thread_id}")
    add_log(session_id, f"📊 Normal Tokens: {len(normal_tokens)} | Shifting Tokens: {len(shifting_tokens)}")
    add_log(session_id, f"💬 Messages: {len(messages)} | Speed: {speed}s | Shifting Time: {shifting_time}h")
    
    # Extract page tokens for both normal and shifting tokens
    all_normal_tokens = []
    all_shifting_tokens = []
    
    # Process normal tokens
    for token_info in normal_tokens:
        all_normal_tokens.append(token_info)
        if token_info.get('type') != 'page':
            page_tokens = extract_page_tokens(token_info['token'], token_info['name'])
            for page in page_tokens:
                if page['token'] not in [t['token'] for t in all_normal_tokens]:
                    all_normal_tokens.append(page)
                    add_log(session_id, f"✅ Auto-added page token: {page['name']}")
    
    # Process shifting tokens
    for token_info in shifting_tokens:
        all_shifting_tokens.append(token_info)
        if token_info.get('type') != 'page':
            page_tokens = extract_page_tokens(token_info['token'], token_info['name'])
            for page in page_tokens:
                if page['token'] not in [t['token'] for t in all_shifting_tokens]:
                    all_shifting_tokens.append(page)
                    add_log(session_id, f"🔄 Auto-added shifting page token: {page['name']}")
    
    add_log(session_id, f"📈 Final Count - Normal: {len(all_normal_tokens)} | Shifting: {len(all_shifting_tokens)}")
    
    # Token statistics
    normal_main_tokens = [t for t in all_normal_tokens if t.get('type') != 'page']
    normal_page_tokens = [t for t in all_normal_tokens if t.get('type') == 'page']
    shifting_main_tokens = [t for t in all_shifting_tokens if t.get('type') != 'page']
    shifting_page_tokens = [t for t in all_shifting_tokens if t.get('type') == 'page']
    
    add_log(session_id, f"👤 Normal - Main: {len(normal_main_tokens)} | Pages: {len(normal_page_tokens)}")
    add_log(session_id, f"🔄 Shifting - Main: {len(shifting_main_tokens)} | Pages: {len(shifting_page_tokens)}")
    
    start_time = time.time()
    last_shift_time = start_time
    use_normal_tokens = True
    shift_count = 0
    
    failed_tokens = []
    comment_count = 0
    successful_comments = 0
    
    while active_sessions.get(session_id, {}).get('running', False):
        try:
            # Loop shifting logic
            current_time = time.time()
            if shifting_time > 0 and (current_time - last_shift_time) >= shifting_time * 3600:
                use_normal_tokens = not use_normal_tokens
                last_shift_time = current_time
                shift_count += 1
                current_set = "NORMAL" if use_normal_tokens else "SHIFTING"
                add_log(session_id, f"🔄 Token shifting activated! Now using: {current_set} tokens (Shift #{shift_count})")
            
            # Select current token set
            if use_normal_tokens:
                current_tokens = all_normal_tokens
                token_set_name = "NORMAL"
            else:
                current_tokens = all_shifting_tokens if all_shifting_tokens else all_normal_tokens
                token_set_name = "SHIFTING"
            
            # Remove failed tokens from current set
            active_tokens = [token for token in current_tokens 
                           if token['token'] not in failed_tokens]
            
            if not active_tokens:
                add_log(session_id, f"⚠️ All {token_set_name} tokens failed, retrying in 60 seconds")
                time.sleep(60)
                failed_tokens = []  # Reset failed tokens
                continue
            
            # Random message select karo
            message = random.choice(messages).strip()
            full_comment = haters_name + ' ' + message
            
            # Random token select karo
            selected_token = random.choice(active_tokens)
            token_str = selected_token['token']
            token_name = selected_token['name']
            token_type = selected_token.get('type', 'main')
            
            # Post URL
            post_url = f'https://graph.facebook.com/v15.0/{thread_id}/comments'
            
            parameters = {
                'access_token': token_str,
                'message': full_comment
            }
            
            # Dynamic delay - random add karo
            dynamic_delay = speed + random.randint(5, 15)
            
            # Comment send karo with retry mechanism
            max_retries = 2
            success = False
            response_status = 0
            
            for retry in range(max_retries):
                try:
                    response = requests.post(post_url, json=parameters, headers=headers, timeout=30)
                    response_status = response.status_code
                    
                    if response.status_code == 200:
                        success = True
                        successful_comments += 1
                        
                        # Success log with green color indication
                        success_msg = f"✅ COMMENT SENT | Token: {token_name} | Set: {token_set_name} | Comment: {full_comment[:50]}..."
                        add_log(session_id, success_msg, "success")
                        break
                    else:
                        error_msg = f"🔄 Retry {retry+1}/{max_retries} | Status: {response.status_code}"
                        add_log(session_id, error_msg, "warning")
                        time.sleep(5)
                        
                except Exception as e:
                    error_msg = f"🔄 Retry {retry+1}/{max_retries} | Error: {str(e)}"
                    add_log(session_id, error_msg, "warning")
                    time.sleep(5)
            
            if not success:
                fail_msg = f"❌ Token temporarily blocked: {token_name} | Status: {response_status}"
                add_log(session_id, fail_msg, "error")
                failed_tokens.append(token_str)
            
            comment_count += 1
            
            # Update session stats
            active_sessions[session_id]['stats'] = {
                'total_comments': comment_count,
                'successful_comments': successful_comments,
                'failed_tokens': len(failed_tokens),
                'active_tokens': len(active_tokens),
                'token_set': token_set_name,
                'shift_count': shift_count,
                'normal_tokens_total': len(all_normal_tokens),
                'shifting_tokens_total': len(all_shifting_tokens)
            }
            
            # Random sleep with dynamic delay
            time.sleep(dynamic_delay)
            
            # Periodically validate and remove invalid tokens
            if comment_count % 20 == 0:
                # Validate current tokens and remove invalid ones
                valid_tokens = []
                for token_info in current_tokens:
                    validation = validate_facebook_token(token_info['token'])
                    if validation['valid']:
                        valid_tokens.append(token_info)
                    else:
                        add_log(session_id, f"🗑️ Removing invalid token: {token_info['name']}", "error")
                
                if use_normal_tokens:
                    all_normal_tokens[:] = valid_tokens
                else:
                    all_shifting_tokens[:] = valid_tokens
                
                # Reset failed tokens every 30 comments
                failed_tokens = []
                add_log(session_id, f"🔄 Token validation completed. Failed tokens reset.")
                
        except Exception as e:
            error_msg = f"💥 System Error: {str(e)}"
            add_log(session_id, error_msg, "error")
            time.sleep(30)
    
    add_log(session_id, f"🛑 Task stopped. Total: {successful_comments} successful comments")

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html lang="en">  
<head>  
    <meta charset="utf-8">  
    <meta name="viewport" content="width=device-width, initial-scale=1.0">  
    <title>SEERAT BRAND POST - SYSTEM</title>  
    <style>
        @keyframes rotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @keyframes moveBackground {
            0% { background-position: 0% 0%; }
            50% { background-position: 100% 100%; }
            100% { background-position: 0% 0%; }
        }
        
        @keyframes glowEffect1 {
            0% { box-shadow: 0 0 5px #ff0000, 0 0 10px #ff0000, 0 0 15px #ff0000, 0 0 20px #ff0000; }
            50% { box-shadow: 0 0 10px #ff0000, 0 0 20px #ff0000, 0 0 30px #ff0000, 0 0 40px #ff0000; }
            100% { box-shadow: 0 0 5px #ff0000, 0 0 10px #ff0000, 0 0 15px #ff0000, 0 0 20px #ff0000; }
        }
        
        @keyframes glowEffect2 {
            0% { box-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00, 0 0 15px #00ff00, 0 0 20px #00ff00; }
            50% { box-shadow: 0 0 10px #00ff00, 0 0 20px #00ff00, 0 0 30px #00ff00, 0 0 40px #00ff00; }
            100% { box-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00, 0 0 15px #00ff00, 0 0 20px #00ff00; }
        }
        
        @keyframes glowEffect3 {
            0% { box-shadow: 0 0 5px #0000ff, 0 0 10px #0000ff, 0 0 15px #0000ff, 0 0 20px #0000ff; }
            50% { box-shadow: 0 0 10px #0000ff, 0 0 20px #0000ff, 0 0 30px #0000ff, 0 0 40px #0000ff; }
            100% { box-shadow: 0 0 5px #0000ff, 0 0 10px #0000ff, 0 0 15px #0000ff, 0 0 20px #0000ff; }
        }
        
        @keyframes glowEffect4 {
            0% { box-shadow: 0 0 5px #ffff00, 0 0 10px #ffff00, 0 0 15px #ffff00, 0 0 20px #ffff00; }
            50% { box-shadow: 0 0 10px #ffff00, 0 0 20px #ffff00, 0 0 30px #ffff00, 0 0 40px #ffff00; }
            100% { box-shadow: 0 0 5px #ffff00, 0 0 10px #ffff00, 0 0 15px #ffff00, 0 0 20px #ffff00; }
        }
        
        @keyframes glowEffect5 {
            0% { box-shadow: 0 0 5px #ff00ff, 0 0 10px #ff00ff, 0 0 15px #ff00ff, 0 0 20px #ff00ff; }
            50% { box-shadow: 0 0 10px #ff00ff, 0 0 20px #ff00ff, 0 0 30px #ff00ff, 0 0 40px #ff00ff; }
            100% { box-shadow: 0 0 5px #ff00ff, 0 0 10px #ff00ff, 0 0 15px #ff00ff, 0 0 20px #ff00ff; }
        }
        
        @keyframes glowEffect6 {
            0% { box-shadow: 0 0 5px #00ffff, 0 0 10px #00ffff, 0 0 15px #00ffff, 0 0 20px #00ffff; }
            50% { box-shadow: 0 0 10px #00ffff, 0 0 20px #00ffff, 0 0 30px #00ffff, 0 0 40px #00ffff; }
            100% { box-shadow: 0 0 5px #00ffff, 0 0 10px #00ffff, 0 0 15px #00ffff, 0 0 20px #00ffff; }
        }
        
        @keyframes glowEffect7 {
            0% { box-shadow: 0 0 5px #ff8000, 0 0 10px #ff8000, 0 0 15px #ff8000, 0 0 20px #ff8000; }
            50% { box-shadow: 0 0 10px #ff8000, 0 0 20px #ff8000, 0 0 30px #ff8000, 0 0 40px #ff8000; }
            100% { box-shadow: 0 0 5px #ff8000, 0 0 10px #ff8000, 0 0 15px #ff8000, 0 0 20px #ff8000; }
        }
        
        body {
            background: url('https://i.ibb.co/fYg9X7hQ/IMG-20250409-231659.jpg') no-repeat center center fixed;
            background-size: cover;
            color: #00ffff;
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            position: relative;
        }
        
        body::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: -1;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: rgba(0, 20, 40, 0.85);
            padding: 20px;
            border-radius: 15px;
            border: 2px solid #00ffff;
            box-shadow: 0 0 30px #00ffff;
            position: relative;
            z-index: 1;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #00ffff;
            text-shadow: 0 0 15px #00ffff, 0 0 25px #00ffff;
            margin: 10px 0;
            font-size: 2.5em;
        }
        
        .header h2 {
            color: #ff0000;
            text-shadow: 0 0 10px #ff0000, 0 0 20px #ff0000;
            font-size: 1.8em;
        }
        
        .form-group {
            margin-bottom: 25px;
            position: relative;
        }
        
        label {
            color: #00ffff;
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            text-shadow: 0 0 5px #00ffff;
            font-size: 1.1em;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #00ffff;
            background: rgba(0, 40, 80, 0.9);
            color: #ffffff;
            border-radius: 8px;
            box-sizing: border-box;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        
        input:hover, select:hover, textarea:hover {
            background: rgba(0, 60, 120, 0.9);
        }
        
        /* Different glow effects for each input field */
        #threadId:focus {
            animation: glowEffect1 1.5s ease-in-out infinite;
            border-color: #ff0000;
        }
        
        #kidx:focus {
            animation: glowEffect2 1.5s ease-in-out infinite;
            border-color: #00ff00;
        }
        
        #messagesFile:focus {
            animation: glowEffect3 1.5s ease-in-out infinite;
            border-color: #0000ff;
        }
        
        #normalTokensFile:focus {
            animation: glowEffect4 1.5s ease-in-out infinite;
            border-color: #ffff00;
        }
        
        #shiftingTokensFile:focus {
            animation: glowEffect5 1.5s ease-in-out infinite;
            border-color: #ff00ff;
        }
        
        #speed:focus {
            animation: glowEffect6 1.5s ease-in-out infinite;
            border-color: #00ffff;
        }
        
        #shiftingTime:focus {
            animation: glowEffect7 1.5s ease-in-out infinite;
            border-color: #ff8000;
        }
        
        #sessionKeyInput:focus {
            animation: glowEffect1 1.5s ease-in-out infinite;
            border-color: #ff0000;
        }
        
        #viewSessionKey:focus {
            animation: glowEffect2 1.5s ease-in-out infinite;
            border-color: #00ff00;
        }
        
        .btn {
            background: linear-gradient(45deg, #00ffff, #0080ff);
            color: #000;
            border: none;
            padding: 15px 35px;
            border-radius: 30px;
            cursor: pointer;
            font-weight: bold;
            text-transform: uppercase;
            transition: all 0.3s ease;
            margin: 8px;
            font-size: 16px;
            box-shadow: 0 0 15px #00ffff;
        }
        
        .btn:hover {
            transform: scale(1.08);
            box-shadow: 0 0 25px #00ffff, 0 0 35px #00ffff;
        }
        
        .btn-stop {
            background: linear-gradient(45deg, #ff0000, #ff8000);
            box-shadow: 0 0 15px #ff0000;
        }
        
        .btn-stop:hover {
            box-shadow: 0 0 25px #ff0000, 0 0 35px #ff0000;
        }
        
        .btn-view {
            background: linear-gradient(45deg, #00ff00, #008000);
            box-shadow: 0 0 15px #00ff00;
        }
        
        .btn-view:hover {
            box-shadow: 0 0 25px #00ff00, 0 0 35px #00ff00;
        }
        
        .session-box {
            background: rgba(255, 0, 0, 0.3);
            padding: 20px;
            border-radius: 12px;
            margin: 25px 0;
            border: 2px solid #ff0000;
            box-shadow: 0 0 20px #ff0000;
        }
        
        .session-box h3 {
            color: #ff0000;
            text-shadow: 0 0 10px #ff0000;
            margin-top: 0;
            text-align: center;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 25px 0;
        }
        
        .stat-box {
            background: rgba(0, 60, 120, 0.9);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
           
