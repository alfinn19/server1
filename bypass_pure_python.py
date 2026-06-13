import sys
import os
import binascii
import requests
import time
from mitmproxy import http
from mitmproxy.tools.main import mitmdump
import threading
import logging

# Path untuk lingkungan Pterodactyl
sys.path.append(".local/lib/python3.13/site-packages")

import Login_pb2
from decrypt_pure import AESUtils
from proto_pure import ProtobufUtils

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

aesUtils = AESUtils()
protoUtils = ProtobufUtils()

def hexToOctetStream(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)

def fetchUIDsFromServer():
    """Live fetch UID dari server Alfin."""
    try:
        response = requests.get("http://47.130.154.248:2006/raw/uid", timeout=10)
        uids = [line.strip() for line in response.text.strip().split('\n') if line.strip().isdigit()]
        return uids
    except Exception as e:
        logging.warning(f"Failed to fetch UID from server: {e}")
        return []

class MajorLoginInterceptor:
    def request(self, flow: http.HTTPFlow) -> None:
        # Menangkap request MajorLogin secara presisi
        if flow.request.method.upper() == "POST" and "majorlogin" in flow.request.path.lower():
            try:
                enc_body = flow.request.content.hex()
                dec_body = aesUtils.decrypt_aes_cbc(enc_body)
                body = protoUtils.decode_protobuf(dec_body.hex(), Login_pb2.LoginReq)

                # --- SUNTIK DATA S21 ULTRA ANDALAN ALFIN ---
                # Menggunakan string yang kamu yakini 100% berhasil
                body.deviceData = "KqsHTxnXXUCG8sxXFVB2j0AUs3+0cvY/WgLeTdfTE/KPENeJPpny2EPnJDs8C8cBVMcd1ApAoCmM9MhzDDXabISdK31SKSFSr06eVCZ4D2Yj/C7G"
                
                # Update Reserved20 agar logo PC hilang total
                # Prefix \x13 (Decimal 19) adalah identitas Samsung murni
                body.reserved20 = b"\x13RFC\x07\x0e\\Q1"

                # Tambahan: Paksa Flag Environment ke Mobile
                if hasattr(body, 'osType'): body.osType = 1 # Android
                if hasattr(body, 'isEmulator'): body.isEmulator = False

                binary_data = body.SerializeToString()
                finalEncContent = aesUtils.encrypt_aes_cbc(hexToOctetStream(binary_data.hex()))
                flow.request.content = bytes.fromhex(finalEncContent.hex())

                logging.info("[✓] S21 ULTRA BYPASS: Identity Injected Successfully.")
            except Exception as e:
                logging.error(f"Request processing error: {e}")

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.request.method.upper() == "POST" and "majorlogin" in flow.request.path.lower():
            try:
                respBody = flow.response.content.hex()
                decodedBody = protoUtils.decode_protobuf(respBody, Login_pb2.getUID)
                uid_str = str(decodedBody.uid)

                valid_uids = fetchUIDsFromServer()
                if uid_str not in valid_uids:
                    # Pesan alert baru, dengan tambahan pesan premium
                    alert_message = (
                        "[FF00FF]╔════════════════════════════════════╗\n"
                        "[00FF00] INFORMASI LOGIN \n"
                        "[FF00FF]╠════════════════════════════════════╣\n"
                        f"[FFFF33] ➜ UID: [FFFFFF]{uid_str}\n"
                        "[FF0000]✖️ STATUS: KADALUARSA / BELUM PREMIUM✖️\n"
                        "[FF00FF]╚════════════════════════════════════╝\n"
                        "[FFFF33]PREMIUM DULU BRO WA ADMIN : 6285730381889\n"
                    )
                    flow.response.content = alert_message.encode()
                    flow.response.status_code = 400

                    # Log event
                    logging.warning(f"UID {uid_str} tidak terotorisasi. Akses ditolak.")
            except Exception as e:
                logging.error(f"Response processing error: {e}")

addons = [MajorLoginInterceptor()]

if __name__ == "__main__":
    mitmdump([
        "-s", "bypass_pure_python.py",
        "-p", "2005",
        "--set", "block_global=false",
        "--ssl-insecure"
    ])