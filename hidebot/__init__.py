import asyncio, os
import hypercorn.asyncio
from asgiref.wsgi import WsgiToAsgi
from hypercorn.config import Config
from telethon import *
import hmac, hashlib
import requests
import requests as req 
import os, requests, math, time, urllib3
import json
import datetime as DT
import datetime
from telethon.tl.types import InputMediaUploadedPhoto
import logging
import psutil
import platform
import mysql.connector
from mysql.connector import errorcode
from mysql.connector import pooling
import subprocess
from contextlib import contextmanager
from mysql.connector import pooling, Error
from threading import Lock
import re
import aiohttp
import random
import string
from io import BytesIO
import qrcode
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator
from dotenv import load_dotenv
import uuid
import secrets
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Coba muat file .env
dotenv_path = "/etc/hidebot/.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print(f"File .env tidak ditemukan di {dotenv_path}")


async def cek_status_orkut():
    url = "https://orkut.hidepulsa.com/orkut/pg-hidepulsa"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer GATEWAYORKUT_BY_HIDEPULSA" # Sesuaikan API KEY kamu
    }
    payload = {
        "action": "cekaktif",
        "username": "rizkihidepulsa",
        "auth_token": "2747289:uJI1oh4zWbG6wOmKiQgZyRjLnXcaA2NB",
        "merchant": "2747289"
    }
    
    try:
        # Menggunakan session dari hidebot atau aiohttp langsung
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("account_status", "OFFLINE")
                return "OFFLINE"
    except Exception:
        return "OFFLINE"

async def cek_status_qiospay():
    # Ganti dengan Kredensial QiosPay milikmu
    merchant_code = "QP042742"
    api_key = "9a1a701ead6007d2c08dff3156f88ff5b0528ff7955473894051be371f9df727"
    url = f"https://qiospay.id/api/mutasi/qris/{merchant_code}/{api_key}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Sesuai doc: status "success" berarti API jalan
                    if data.get("status") == "success":
                        return "ONLINE"
                return "OFFLINE"
    except Exception:
        return "OFFLINE"

async def cek_status_tripay():
    # Gunakan API Key yang sudah terbukti sukses di curl tadi
    api_key = "1AcH9hzNWgrWP3XfhXAsfdbeGJ3UIMMXZBWqIX5E"
    url = "https://tripay.co.id/api/merchant/payment-channel"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Kita cek field 'success' sesuai respon curl kamu
                    if data.get("success") is True:
                        return "ONLINE"
                return "OFFLINE"
    except Exception as e:
        logger.error(f"Error Cek Tripay: {e}")
        return "OFFLINE"

# XL
AKRAB = os.getenv("AKRAB")
CIRCLE = os.getenv("CIRCLE")
BUY_URL = os.getenv("DOR")
API_KEY = os.getenv("API_KEY")
ID_TELEGRAM = os.getenv("IDTELE")
PASSWORD_PANEL = os.getenv("PWAPI")
API_PRODUK = os.getenv("PRODUK")
API_TOOLS= os.getenv("TOOLS")
API_CEKLOGIN = os.getenv("API_CEKLOGIN")

# Indosat & Tri
API_TOOLS_ISATRI = os.getenv("API_TOOLS_ISATRI")
API_BUY_ISATRI = os.getenv("API_BUY_ISATRI")

# API PPOB
API_PPOB = os.getenv("API_PPOB")

EMOJI_PAYMENT = {
    "pulsa": "📲",
    "shopee": "🛍️",
    "gopay": "💳",
    "dana": "💰",
    "qris": "📷"
}

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": API_KEY,
    ":": ""            # agar sama persis dengan contoh curl
}

def rupiah(n: int) -> str:
    try:
        return f"Rp {int(n):,}"
    except Exception:
        return str(n)

async def cek_login_api(id_telegram: str, password: str, nomor_hp: str) -> dict:
    """Cek apakah nomor sudah login via API eksternal (POST)"""
    url = "http://127.0.0.1:5000/api/v1/cek-login"
    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "id_telegram": id_telegram,
        "password": password,
        "nomor_hp": nomor_hp
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                return {
                    "status": "error",
                    "message": f"API error: {resp.status}"
                }
            return await resp.json()


async def ambil_produk(keyword: str, api_key: str):
    headers = {"Authorization": api_key}
    async with aiohttp.ClientSession() as ses:
        async with ses.get(API_PRODUK, headers=headers) as resp:
            if resp.status != 200:
                raise ValueError(f"Gagal ambil produk: {resp.status}")
            data = await resp.json()

    if data.get("status") != "success":
        raise ValueError("Respon API gagal")

    # Filter produk yang mengandung keyword di nama_paket
    hasil = [
        p for p in data.get("data", [])
        if keyword.lower() in p["nama_paket"].lower()
    ]
    return hasil

"""async def ngundang_api(base_url: str, payload: dict) -> dict:
    async with aiohttp.ClientSession() as ses:
        async with ses.post(
            base_url,
            json=payload,
            headers={k: v for k, v in HEADERS.items() if v or k != ":"}
        ) as resp:

            txt = await resp.text()
            if resp.status != 200:
                raise ValueError(
                    f"API error {resp.status}. Body ↓\n{txt[:500]}"
                )
            if "application/json" not in resp.headers.get("Content-Type", ""):
                raise ValueError(
                    f"Respon bukan JSON (type={resp.headers.get('Content-Type')}):\n{txt[:300]}"
                )
            return json.loads(txt)"""
# contoh pola; sesuaikan dgn implementasi kamu
async def ngundang_api(base_url: str, payload: dict) -> dict:
    async with aiohttp.ClientSession() as ses:
        async with ses.post(
            base_url,
            json=payload,
            headers={k: v for k, v in HEADERS.items() if v or k != ":"}
        ) as resp:

            txt = await resp.text()

            # ✅ terima juga 201 & 202 sebagai "berhasil diterima"
            if resp.status not in (200, 201, 202):
                raise ValueError(
                    f"API error {resp.status}. Body ↓\n{txt[:500]}"
                )

            if "application/json" not in resp.headers.get("Content-Type", ""):
                raise ValueError(
                    f"Respon bukan JSON (type={resp.headers.get('Content-Type')}):\n{txt[:300]}"
                )

            try:
                return json.loads(txt)
            except Exception:
                # fallback kalau JSON rusak
                return {"status": "raw", "body": txt, "http_status": resp.status}

async def ngundang_apii(
    base_url: str,
    payload: dict,
    headers: Optional[Dict[str, str]] = None,
    api_key: Optional[str] = None
) -> dict:

    # 1️⃣ copy headers default
    final_headers = HEADERS.copy()

    # 2️⃣ override Authorization jika api_key dikirim
    if api_key:
        final_headers["Authorization"] = api_key

    # 3️⃣ merge headers tambahan (kalau ada)
    if headers:
        final_headers.update(headers)

    # 4️⃣ buang header aneh (":" atau value kosong)
    final_headers = {
        k: v for k, v in final_headers.items()
        if v and k != ":"
    }

    async with aiohttp.ClientSession() as ses:
        async with ses.post(
            base_url,
            json=payload,
            headers=final_headers
        ) as resp:

            txt = await resp.text()

            if resp.status not in (200, 201, 202):
                raise ValueError(
                    f"API error {resp.status}. Body ↓\n{txt[:500]}"
                )

            if "application/json" not in resp.headers.get("Content-Type", ""):
                raise ValueError(
                    f"Respon bukan JSON "
                    f"(type={resp.headers.get('Content-Type')}):\n{txt[:300]}"
                )

            try:
                return json.loads(txt)
            except Exception:
                return {
                    "status": "raw",
                    "body": txt,
                    "http_status": resp.status
                }

# Simpan state pesan + data produk per user
user_messages = {}   # buat nyimpen message terakhir
user_sessions = {}   # buat nyimpen data produk yang dipilih user

async def expire_session(user_id, key, ttl=300):
    """Auto hapus session setelah TTL (detik)."""
    await asyncio.sleep(ttl)
    if user_id in user_sessions and key in user_sessions[user_id]:
        for msg in user_sessions[user_id][key].get("messages", []):
            try:
                await msg.delete()
            except:
                pass
        del user_sessions[user_id][key]
        logger.info(f"[SESSION] {key} expired untuk user {user_id}")

"""async def clear_session(user_id, key):
    # cek apakah user_id ada
    if user_id not in user_sessions:
        logger.info(f"[SESSION] clear_session gagal: user {user_id} tidak ada")
        return  

    # hapus key session kalau ada
    user_sessions[user_id].pop(key, None)
    logger.info(f"[SESSION] key '{key}' dihapus untuk user {user_id}")

    # kalau session user udah kosong, hapus user_id dari dict
    if not user_sessions[user_id]:
        user_sessions.pop(user_id, None)
        logger.info(f"[SESSION] semua session user {user_id} sudah kosong, user dihapus")"""

async def clear_session(user_id):
    if user_id in user_sessions:
        user_sessions.pop(user_id, None)
        logger.info(f"[SESSION] semua session user {user_id} sudah dihapus")
    else:
        logger.info(f"[SESSION] clear_session gagal: user {user_id} tidak ada")


async def auto_delete_multi(user_id, delay, *msgs):
    """Auto hapus banyak pesan setelah delay"""
    await asyncio.sleep(delay)
    for msg in msgs:
        try:
            if msg:
                await msg.delete()
        except Exception as e:
            print(f"Error hapus pesan: {e}")
    if user_id in user_messages:
        del user_messages[user_id]


def mask_number(nomor):
    """Menyamarkan nomor HP dengan menampilkan 4 digit awal & akhir, serta mengganti bagian tengah dengan 'xxx'."""
    if len(nomor) > 8:
        return nomor[:4] + "xxxx" + nomor[-4:]  # Format: 6287xxx4614
    return nomor

def generate_kode_hidepulsa(length: int = 8) -> str:
    # kombinasi huruf besar + angka
    chars = string.ascii_uppercase + string.digits
    rand_code = ''.join(random.choices(chars, k=length))
    return f"HIDEPULSA_{rand_code}"

CHANNEL_USERNAME = os.getenv("CHANEL")
GROUP_USERNAME = os.getenv("GROUP")
admin = os.getenv("ADMIN")

# Fungsi untuk mengecek apakah pengguna sudah join channel
async def check_membership(client, user_id):
    try:
        entity = await client.get_entity(f"t.me/{CHANNEL_USERNAME}")
        logger.info(f"✅ Bot berhasil membaca channel: {entity.id}")
        participant = await client(GetParticipantRequest(entity, user_id))
        logger.info(f"✅ User {user_id} terdeteksi sebagai anggota channel.")
        return True
    except Exception as e:
        logger.error(f"❌ Error saat cek membership: {e}")
        return False
    
async def check_group_membership(client, user_id):
    try:
        entity = await client.get_entity(f"t.me/{GROUP_USERNAME}")
        participant = await client(GetParticipantRequest(entity, user_id))
        logger.info(f"✅ User {user_id} adalah anggota grup.")
        return True
    except Exception as e:
        logger.warning(f"❌ User {user_id} bukan anggota grup: {e}")
        return False

bot_start_time = datetime.datetime.now()
def get_uptime():
    current_time = datetime.datetime.now()
    uptime = current_time - bot_start_time  # Anda perlu mendefinisikan `bot_start_time` sesuai dengan saat bot Anda dimulai
    days, seconds = uptime.days, uptime.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    formatted_uptime = f"{days}d, {hours}h, {minutes}m, {seconds}s"
    return formatted_uptime

logging.basicConfig(level=logging.INFO)
uptime = DT.datetime.now()

TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
bot = TelegramClient("hidebot", API_ID, API_HASH).start(bot_token=TOKEN)

CHAT_ID1 = os.getenv("CHAT_ID1")
THREAD_GROUP = os.getenv("THREAD_GROUP")
        
"""async def kirim_notifikasi_group(nomor_buyer, nama_paket, harga, method, ref_trx):
    url = f'http://api.telegram.org/bot{TOKEN}/sendMessage'

    pesan = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "      ✅ *TRANSAKSI SUKSES*\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"📌 *Detail Transaksi {method}:*\n"
        f"├ 👤 Nomor : `{nomor_buyer}`\n"
        f"├ 🧷 Ref Trx : `{ref_trx}`\n"
        f"├ 📦 Nama Paket : `{nama_paket}`\n"
        f"└ 💰 Harga : `Rp {int(harga):,}`\n\n"
        "🚀 *Transaksi berhasil diproses!*"
    ).replace(",", ".")

    payload = {
        'chat_id': CHAT_ID1,
        'text': pesan,
        'parse_mode': 'Markdown',
    }

    if THREAD_GROUP:
        payload['message_thread_id'] = THREAD_GROUP

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, data=payload) as resp:
                if resp.status == 200:
                    print("✅ Notifikasi sukses berhasil dikirim!")
                else:
                    print(f"❌ Gagal kirim notifikasi: {resp.status}, {await resp.text()}")
        except Exception as e:
            print(f"❌ Error saat kirim notifikasi: {str(e)}")"""
async def kirim_notifikasi_group(nomor_buyer, nama_paket, harga, method, ref_trx):
    # WAJIB pakai HTTPS
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'

    # amankan konversi harga
    try:
        harga_int = int(harga)
    except (TypeError, ValueError):
        harga_int = 0

    pesan = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "      ✅ TRANSAKSI SUKSES\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"📌 Detail Transaksi {method}:\n"
        f"├ 👤 Nomor : {nomor_buyer}\n"
        f"├ 🧷 Ref Trx : {ref_trx}\n"
        f"├ 📦 Nama Paket : {nama_paket}\n"
        f"└ 💰 Harga : Rp {harga_int:,}\n\n"
        "🚀 Transaksi berhasil diproses!"
    ).replace(",", ".")

    # 🔍 DEBUG
    print("=== DEBUG KIRIM_NOTIF ===")
    print("len(pesan):", len(pesan))
    print("pesan repr:", repr(pesan))
    print("nomor_buyer:", repr(nomor_buyer))
    print("nama_paket:", repr(nama_paket))
    print("harga:", repr(harga))
    print("method:", repr(method))
    print("ref_trx:", repr(ref_trx))

    # pastikan chat_id dan thread_id integer kalau bisa
    chat_id = CHAT_ID1
    try:
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            chat_id = int(chat_id)
    except Exception:
        pass

    payload = {
        "chat_id": chat_id,
        "text": pesan,
    }

    if THREAD_GROUP:
        try:
            thread_id = int(THREAD_GROUP)
            payload["message_thread_id"] = thread_id
        except Exception:
            # kalau gagal cast, mending nggak usah kirim thread_id daripada error
            pass

    async with aiohttp.ClientSession() as session:
        try:
            # pakai JSON biar jelas
            async with session.post(url, json=payload) as resp:
                body = await resp.text()
                if resp.status == 200:
                    print("✅ Notifikasi sukses berhasil dikirim!")
                else:
                    print("❌ Gagal kirim notifikasi:", resp.status, body)
                    print("Payload yang dikirim:", payload)
        except Exception as e:
            print(f"❌ Error saat kirim notifikasi: {str(e)}")


db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
    "connection_timeout": int(os.getenv("DB_CONN_TIMEOUT")),
    "pool_reset_session": os.getenv("DB_POOL_RESET_SESSION") == "True"
}

connection_pool = None
pool_lock = Lock()

def reset_connection_pool():
    global connection_pool
    try:
        with pool_lock:  # Gunakan lock untuk memastikan hanya satu thread yang membuat ulang pool
            connection_pool = pooling.MySQLConnectionPool(
                pool_name="mypool",
                pool_size=30,  # Sesuaikan dengan kebutuhan aplikasi
                **db_config
            )
            #print("Pool koneksi berhasil dibuat ulang.")
    except Error as e:
        print(f"Error saat mencoba reset pool koneksi: {e}")
        connection_pool = None

def get_db_connection():
    global connection_pool

    if connection_pool is None:
        print("Pool tidak tersedia. Mencoba membuat ulang pool...")
        reset_connection_pool()

    try:
        # Coba mendapatkan koneksi dari pool
        connection = connection_pool.get_connection()
        #print("Koneksi berhasil diperoleh dari pool.")
        return connection
    except Error as e:
        print(f"Pool habis atau error: {e}")
        print("Mencoba membuat ulang pool...")
        reset_connection_pool()

        # Setelah reset, coba lagi mendapatkan koneksi
        try:
            connection = connection_pool.get_connection()
            #print("Koneksi berhasil diperoleh dari pool yang baru.")
            return connection
        except Error as retry_error:
            print(f"Error setelah mencoba reset pool: {retry_error}")
            return None

def get_harga_real_db(nama_paket):
    """Mengambil harga_paket_isatttri dari tabel produkIsatTri berdasarkan nama_paket"""
    try:
        # ⚙️ KONFIGURASI DATABASE (Sesuaikan dengan VPS kamu)
        mydb = mysql.connector.connect(
            host="127.0.0.1",
            user="root",         # Username database
            password="RizKi12@R",         # Password database
            database="indosat"   # Nama database
        )
        
        mycursor = mydb.cursor()
        # Query mengambil harga
        sql = "SELECT harga_paket_isatttri FROM produkIsatTri WHERE nama_paket = %s LIMIT 1"
        val = (nama_paket,)
        
        mycursor.execute(sql, val)
        result = mycursor.fetchone()
        
        mydb.close() # Penting: Tutup koneksi biar ga numpuk
        
        if result:
            return int(result[0]) # Mengembalikan harga (integer)
        return 0
        
    except Exception as e:
        # print(f"Error DB: {e}") # Debugging jika perlu
        return 0

# Konfigurasi database untuk pool kedua
db_config1 = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME2"),
    "connection_timeout": int(os.getenv("DB_CONN_TIMEOUT")),
    "pool_reset_session": os.getenv("DB_POOL_RESET_SESSION") == "True"
}

connection_pool1 = None
pool_lock1 = Lock()

def reset_connection_pool1():
    global connection_pool1
    try:
        with pool_lock1:  # Gunakan lock untuk memastikan hanya satu thread yang membuat ulang pool
            connection_pool1 = pooling.MySQLConnectionPool(
                pool_name="mypool1",
                pool_size=30,  # Sesuaikan dengan kebutuhan aplikasi
                **db_config1
            )
            #print("Pool koneksi berhasil dibuat ulang.")
    except Error as e:
        print(f"Error saat mencoba reset pool koneksi: {e}")
        connection_pool1 = None

def get_db_connection2():
    global connection_pool1

    if connection_pool1 is None:
        print("Pool tidak tersedia. Mencoba membuat ulang pool...")
        reset_connection_pool1()

    try:
        # Coba mendapatkan koneksi dari pool
        connection = connection_pool1.get_connection()
        #print("Koneksi berhasil diperoleh dari pool.")
        return connection
    except Error as e:
        print(f"Pool habis atau error: {e}")
        print("Mencoba membuat ulang pool...")
        reset_connection_pool1()

        # Setelah reset, coba lagi mendapatkan koneksi
        try:
            connection = connection_pool1.get_connection()
            #print("Koneksi berhasil diperoleh dari pool yang baru.")
            return connection
        except Error as retry_error:
            print(f"Error setelah mencoba reset pool: {retry_error}")
            return None

def get_api_credentials(id_telegram: str):
    """
    Ambil api_key & password berdasarkan id_telegram.
    Prioritas: DB1 (data.user), kalau tidak ada → DB2 (sys.ress).
    """
    # --- Cek di DB1 ---
    conn1 = get_db_connection()
    cursor1 = conn1.cursor(dictionary=True)
    cursor1.execute(
        "SELECT api_key, password FROM user WHERE id_telegram = %s",
        (id_telegram,)
    )
    result1 = cursor1.fetchone()
    cursor1.close()
    conn1.close()

    if result1:  # kalau ketemu di DB1 langsung return
        return result1

    # --- Kalau tidak ada di DB1, cek DB2 ---
    conn2 = get_db_connection2()
    cursor2 = conn2.cursor(dictionary=True)
    cursor2.execute(
        "SELECT api_key, password FROM ress WHERE id_telegram = %s",
        (id_telegram,)
    )
    result2 = cursor2.fetchone()
    cursor2.close()
    conn2.close()

    return result2  # bisa None kalau tetap tidak ada

async def get_api_generate(id_telegram: str):
    """
    Ambil api_key & password berdasarkan id_telegram.
    Kalau api_key tidak ada → generate lewat API.
    """
    # --- Cek DB1 ---
    conn1 = get_db_connection()
    cursor1 = conn1.cursor(dictionary=True)
    cursor1.execute(
        "SELECT api_key, password FROM user WHERE id_telegram = %s",
        (id_telegram,)
    )
    result1 = cursor1.fetchone()
    cursor1.close()
    conn1.close()

    if result1:
        if result1.get("api_key"):  # sudah ada api_key
            return result1
        elif result1.get("password"):  # generate api_key baru
            return await generate_api_key(id_telegram, result1["password"])

    # --- Cek DB2 ---
    conn2 = get_db_connection2()
    cursor2 = conn2.cursor(dictionary=True)
    cursor2.execute(
        "SELECT api_key, password FROM ress WHERE id_telegram = %s",
        (id_telegram,)
    )
    result2 = cursor2.fetchone()
    cursor2.close()
    conn2.close()

    if result2:
        if result2.get("api_key"):
            return result2
        elif result2.get("password"):
            return await generate_api_key(id_telegram, result2["password"])

    return None


async def generate_api_key(id_telegram: str, password: str):
    payload = {"idtelegram": str(id_telegram), "password": password}
    resp = await ngundang_api("http://127.0.0.1:5000/generate-api-key", payload)
    return resp  # sudah ada api_key & password dari API


"""def valid_admin(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT COUNT(*) FROM admin WHERE telegram_id = %s"
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return "true" if result[0] > 0 else "false"
    """

# Koneksi ke database MySQL
try:
    conn = get_db_connection()
    cursor = conn.cursor()

    # SQL untuk membuat tabel
    create_tables = [
        """
        CREATE TABLE IF NOT EXISTS user (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            id_telegram BIGINT UNIQUE NOT NULL,
            role ENUM('admin', 'reseller', 'super_reseller', 'priority') NOT NULL,
            saldo INT NOT NULL DEFAULT 0,
            password VARCHAR(128) NOT NULL,
            otp VARCHAR(10),
            otp_expiry DATETIME,
            api_key VARCHAR(128) NULL,
            tipe ENUM('basic', 'premium') NOT NULL DEFAULT 'basic',
            premium_expires_at DATETIME NULL,
            key_access VARCHAR(255) NULL,
            INDEX idx_key_access (key_access)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS by_id (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            id_telegram BIGINT UNIQUE NOT NULL,
            role ENUM('admin', 'reseller', 'super_reseller', 'priority') NOT NULL,
            saldo INT NOT NULL DEFAULT 0
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sys_id (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            id_telegram BIGINT UNIQUE NOT NULL,
            role ENUM('admin', 'reseller', 'super_reseller', 'priority') NOT NULL,
            saldo INT NOT NULL DEFAULT 0
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS slot5 (
        nomor_hp VARCHAR(15) NOT NULL,
        member_id VARCHAR(255) NOT NULL,
        slot_id INT NOT NULL,
        exp DATETIME NOT NULL,
        PRIMARY KEY (nomor_hp)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            kuota VARCHAR(255),
            id_tele BIGINT,
            no_hp VARCHAR(15),
            waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS harga (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama VARCHAR(255),
            kode VARCHAR(255) UNIQUE,
            idproduk INT,
            plp VARCHAR(255),
            harga INT,
            harga_produk INT,
            nama_paket VARCHAR(255)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS produk (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama VARCHAR(255),
            kode VARCHAR(255) UNIQUE,
            idproduk INT,
            plp VARCHAR(255),
            harga INT,
            harga_produk INT,
            nama_paket VARCHAR(255)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS xl (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama VARCHAR(255),
            kode VARCHAR(255) UNIQUE,
            harga INT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS indosat (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama VARCHAR(255),
            kode VARCHAR(255) UNIQUE,
            harga INT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS tri (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama VARCHAR(255),
            kode VARCHAR(255) UNIQUE,
            harga INT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS axis (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama VARCHAR(255),
            kode VARCHAR(255) UNIQUE,
            harga INT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS telkomsel (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nama VARCHAR(255),
            kode VARCHAR(255) UNIQUE,
            harga INT
        );
        """
    ]

    # Menjalankan semua query untuk membuat tabel
    for create_table_query in create_tables:
        cursor.execute(create_table_query)

    admin_list = [
    {"username": "𝙏𝙐𝙔𝙐𝙇 𝘽𝙊𝙏", "id_telegram": 1316596937, "role": "admin"},
    {"username": "Mpussitem", "id_telegram": 5779832686, "role": "admin"},
    {"username": "No", "id_telegram": 6863995486, "role": "admin"}
    ]

    for admin in admin_list:
        cursor.execute("SELECT * FROM user WHERE id_telegram = %s", (admin['id_telegram'],))
        result = cursor.fetchone()
    
        if result:
            print(f"Pengguna dengan id_telegram {admin['id_telegram']} sudah ada dengan username {result[1]} sebagai {result[3]}. Tidak menambahkan admin.")
        else:
            cursor.execute("INSERT INTO user (username, id_telegram, role, saldo) VALUES (%s, %s, %s, %s)",
                       (admin['username'], admin['id_telegram'], admin['role'], 0))
            conn.commit()
            print(f"Admin {admin['username']} dengan id_telegram {admin['id_telegram']} berhasil ditambahkan.")

    # Commit perubahan
    conn.commit()
    print("Tabel berhasil dibuat dan data dimasukkan.")

except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("Username atau password salah.")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print("Database tidak ditemukan.")
    else:
        print(f"Terjadi kesalahan: {err}")
finally:
    # Menutup cursor dan koneksi
    cursor.close()
    conn.close()