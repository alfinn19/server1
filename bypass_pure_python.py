import sys, os, time, random, logging, base64
from mitmproxy import http
from mitmproxy.tools.main import mitmdump
from curl_cffi import requests as curl_requests
import Login_pb2
from decrypt_pure import AESUtils
from proto_pure import ProtobufUtils

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
aesUtils = AESUtils()
protoUtils = ProtobufUtils()

# Ganti dengan IP publik Server 2 Mulia
SERVER2_URL = "http://93.115.101.182:2006"   # sesuaikan!

# Pool User-Agent HP asli
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.163 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; M2102J20SG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.111 Mobile Safari/537.36",
]

def get_random_ua():
    return random.choice(USER_AGENTS)

def get_android_fingerprint():
    return {
        "system_hardware": random.choice(["samsung/exynos2200", "qcom/sm8450"]),
        "device_model": random.choice(["SM-S918B", "SM-G998B"]),
        "screen_width": random.choice([1440, 1080]),
        "screen_height": 3200,
        "screen_dpi": "420",
        "cpu_hardware": "ARMv8",
        "memory_mb": 8192,
        "gl_renderer": random.choice(["Mali-G78 MP14", "Adreno 730"]),
        "gl_version": "OpenGL ES 3.2",
        "device_type": "phone",
        "network_type": random.choice(["LTE", "5G"]),
        "telecom_operator": random.choice(["Telkomsel", "XL"]),
    }

config_cache = None
config_cache_time = 0

def get_config_from_server2():
    global config_cache, config_cache_time
    now = time.time()
    if config_cache and (now - config_cache_time) < 3600:
        return config_cache
    try:
        resp = curl_requests.get(f"{SERVER2_URL}/api/game_config", impersonate="android_chrome_120", timeout=10)
        if resp.status_code == 200:
            config_cache = resp.json()
            config_cache_time = now
            return config_cache
    except Exception as e:
        logging.warning(f"Gagal ambil config dari server2: {e}")
    return {
        "deviceData": "KqsHTxnXXUCG8sxXFVB2j0AUs3+0cvY/WgLeTdfTE/KPENeJPpny2EPnJDs8C8cBVMcd1ApAoCmM9MhzDDXabISdK31SKSFSr06eVCZ4D2Yj/C7G",
        "reserved20_base64": "EwRSRkNHDg5cUQ==",
    }

session_fingerprints = {}

def get_or_create_fingerprint(client_ip):
    if client_ip not in session_fingerprints:
        session_fingerprints[client_ip] = get_android_fingerprint()
    return session_fingerprints[client_ip]

class AntiBanInterceptor:
    def request(self, flow: http.HTTPFlow) -> None:
        time.sleep(random.uniform(0.05, 0.3))
        flow.request.headers["User-Agent"] = get_random_ua()

        if flow.request.method.upper() == "POST" and "majorlogin" in flow.request.path.lower():
            try:
                enc_body = flow.request.content.hex()
                dec_body = aesUtils.decrypt_aes_cbc(enc_body)
                body = protoUtils.decode_protobuf(dec_body.hex(), Login_pb2.LoginReq)

                client_ip = flow.client_conn.address[0] if flow.client_conn.address else "unknown"
                fp = get_or_create_fingerprint(client_ip)

                for key, value in fp.items():
                    if hasattr(body, key):
                        setattr(body, key, value)

                cfg = get_config_from_server2()
                body.deviceData = cfg["deviceData"]
                reserved20_bytes = base64.b64decode(cfg["reserved20_base64"])
                body.reserved20 = reserved20_bytes

                if hasattr(body, 'osType'): body.osType = 1
                if hasattr(body, 'isEmulator'): body.isEmulator = False

                binary_data = body.SerializeToString()
                finalEncContent = aesUtils.encrypt_aes_cbc(bytes.fromhex(binary_data.hex()))
                flow.request.content = bytes.fromhex(finalEncContent.hex())

                logging.info(f"[✓] Anti-Ban: {fp['device_model']} injected for {client_ip}")
            except Exception as e:
                logging.error(f"Request error: {e}")

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.request.method.upper() == "POST" and "majorlogin" in flow.request.path.lower():
            try:
                respBody = flow.response.content.hex()
                decodedBody = protoUtils.decode_protobuf(respBody, Login_pb2.getUID)
                uid_str = str(decodedBody.uid)

                check_resp = curl_requests.post(
                    f"{SERVER2_URL}/validate_uid",
                    json={"uid": uid_str},
                    impersonate="android_chrome_120",
                    timeout=5
                )
                if check_resp.status_code == 200 and check_resp.json().get("allowed"):
                    logging.info(f"UID {uid_str} valid")
                else:
                    alert = (
                        "[FF00FF]╔════════════════════════════════════╗\n"
                        "[00FF00] INFORMASI LOGIN \n"
                        f"[FFFF33] ➜ UID: {uid_str}\n"
                        "[FF0000]✖️ STATUS: KADALUARSA / BELUM PREMIUM ✖️\n"
                        "[FF00FF]╚════════════════════════════════════╝\n"
                        "[FFFF33]Hubungi +6285730381889 untuk perpanjang\n"
                    )
                    flow.response.content = alert.encode()
                    flow.response.status_code = 403
                    logging.warning(f"UID {uid_str} ditolak")
            except Exception as e:
                logging.error(f"Response error: {e}")

addons = [AntiBanInterceptor()]

if __name__ == "__main__":
    mitmdump([
        "-s", "bypass_pure_python.py",
        "-p", "2005",
        "--set", "block_global=false",
        "--ssl-insecure"
    ])
