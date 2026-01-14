from hidebot import *
import qrcode
import io
import random
from datetime import datetime, timedelta

# ====== Tabel penanda processed ======
def _ensure_processed_table(cursor, db):
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS processed_topup (reference TEXT PRIMARY KEY)")
        db.commit()
    except Exception:
        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS processed_topup (reference TEXT)")
            db.commit()
        except Exception:
            pass

def _has_been_processed(cursor, db, reference: str) -> bool:
    try:
        cursor.execute("SELECT reference FROM processed_topup WHERE reference = ?", (reference,))
        return cursor.fetchone() is not None
    except Exception:
        try:
            cursor.execute("SELECT reference FROM processed_topup WHERE reference = %s", (reference,))
            return cursor.fetchone() is not None
        except Exception:
            return False

async def send_admin_notification(user_id, user_name, amount):
    admin_id = 1316596937  # ganti dengan admin ID kamu
    await bot.send_message(
        admin_id,
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "       ☆ NOTIFIKASI TOPUP ☆\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**▪ID Pengguna:** {user_id}\n"
        f"**▪Nama Pengguna:** {user_name}\n"
        f"**▪Nominal Top-Up:** {amount}\n"
        f"**▪Waktu:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"**▪Metode Pembayaran:** OrderKuota\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

# ==========================================
# BAGIAN 1: LOGIKA DATABASE (ANTI TABRAKAN)
# ==========================================

def get_unique_nominal(user_id, username, nominal_asli):
    """
    Mencari nominal unik yang belum dipending orang lain.
    Return: (nominal_unik, kode_unik)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Kita cek transaksi 15 menit terakhir
    time_limit = datetime.now() - timedelta(minutes=15)
    
    try:
        # Coba generate sampai nemu slot kosong
        for _ in range(100): 
            kode_unik = random.randint(1, 50) # Acak 3 digit
            calon_nominal = int(nominal_asli) + kode_unik
            
            # Cek apakah angka ini sedang dipakai user lain?
            cursor.execute("""
                SELECT id FROM topup_riwayat 
                WHERE nominal_unik = %s AND status = 'pending' AND created_at > %s
            """, (calon_nominal, time_limit))
            
            if not cursor.fetchone():
                # Jika kosong, berarti AMAN. Kunci nominal ini.
                cursor.execute("""
                    INSERT INTO topup_riwayat (user_id, username, nominal_request, nominal_unik, kode_unik, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """, (user_id, username, nominal_asli, calon_nominal, kode_unik))
                conn.commit()
                return calon_nominal, kode_unik
                
        raise Exception("Server Penuh, gagal generate kode unik.")
        
    finally:
        cursor.close()
        conn.close()

def set_success_transaction(nominal_unik):
    """
    Update status pending -> success.
    Return True jika berhasil update. Return False jika sudah sukses duluan.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE topup_riwayat SET status = 'success' 
            WHERE nominal_unik = %s AND status = 'pending'
        """, (nominal_unik,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()

def set_expired_transaction(nominal_unik):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE topup_riwayat SET status = 'expired' WHERE nominal_unik = %s AND status = 'pending'", (nominal_unik,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def generate_qr_image(qris_string):
    """Ubah string QRIS jadi Gambar"""
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(qris_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = io.BytesIO()
    img.save(bio)
    bio.seek(0)
    return bio

async def request_dynamic_qris(nominal, qr_raw):
    """
    Request QRIS Dinamis ke API orkut.hidepulsa.com menggunakan aiohttp
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "action": "qris_generate",
        "nominal": str(nominal), # API butuh string/int, aman dikirim string
        "qr_string": qr_raw
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload, headers=headers, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Cek struktur respon JSON kamu:
                    # {"status":"success", "data": {"qris_content": "..."}}
                    if result.get("status") == "success" and "data" in result:
                        return result["data"]["qris_content"]
                    else:
                        logger.error(f"API Error Logic: {result}")
                        raise Exception("Gagal generate di sisi API")
                else:
                    logger.error(f"API HTTP Error: {response.status}")
                    raise Exception(f"HTTP Error {response.status}")
                    
    except Exception as e:
        logger.error(f"Koneksi API Gagal: {e}")
        raise e # Lempar error biar lari ke except di handler utama

API_URL = "https://orkut.hidepulsa.com/orkut/pg-hidepulsa"
API_KEY = "GATEWAYORKUT_BY_HIDEPULSA"

DATA_QRIS_ORKUT = "00020101021126670016COM.NOBUBANK.WWW01189360050300000879140214251231000005100303UMI51440014ID.CO.QRIS.WWW0215ID20254687178190303UMI5204481253033605802ID5919Hidepulsa Ok27472896008BANYUMAS61055311162070703A0163044346"
ORKUT_USERNAME = "rizkihidepulsa"
ORKUT_TOKEN = "2747289:uJI1oh4zWbG6wOmKiQgZyRjLnXcaA2NB"
ORKUT_MERCHANT = "2747289"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@bot.on(events.NewMessage(pattern='/topuporkut1'))
@bot.on(events.CallbackQuery(data=b'topuporkut1'))
async def toporkut1_handler(event):
    chat = event.chat_id
    sender = await event.get_sender()
    
    username = sender.username if sender.username else "NoUser"
    nama = f"{sender.first_name}".strip()

    status = await cek_status_orkut()
    
    if status != "ONLINE":
        # Tampilkan notifikasi popup (alert) di Telegram
        await event.answer("⚠️ Maaf, Gateway Orkut sedang OFFLINE / Maintenance.", alert=True)
        return

    # 1. Input Nominal
    async with bot.conversation(chat) as conv:
        try:
            msg_tanya = await event.respond("💬 **Topup Saldo**\n\nMasukkan nominal (Min. 25.000):\nContoh: `25.000`")
            buyer_msg = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id), timeout=60)
            
            nominal_str = buyer_msg.raw_text.strip().replace('.', '').replace(',', '')
            if not nominal_str.isdigit():
                await event.respond("❌ Nominal harus angka.")
                return
            
            nominal_int = int(nominal_str)
            if nominal_int < 25000:
                await event.respond("❌ Minimal topup Rp 25.000")
                return
            
            # Hapus chat agar bersih
            await msg_tanya.delete()
            await buyer_msg.delete()

        except asyncio.TimeoutError:
            await event.respond("❌ Waktu habis.")
            return

    try:
        # Fungsi ini otomatis INSERT ke database dengan status 'pending'
        # dan memastikan angka uniknya tidak dipake orang lain
        nominal_unik, kode_unik = get_unique_nominal(sender.id, username, nominal_int)
    except Exception as e:
        logger.error(f"DB Full: {e}")
        await event.respond("⚠️ Sistem sedang sibuk, coba nominal lain.")
        return

    try:
        qris_string_fix = await request_dynamic_qris(nominal_unik, DATA_QRIS_ORKUT)
        qr_image = generate_qr_image(qris_string_fix)
    except:
        # Fallback jika gagal inject, pakai QR biasa
        qr_image = generate_qr_image(DATA_QRIS_STATIC)

    formatted_rp = f"Rp {nominal_unik:,.0f}".replace(",", ".")
    formatted_salin = str(nominal_unik)
    
    msg_invoice = await bot.send_file(
        chat,
        qr_image,
        caption=(
            f"🧾 **INVOICE TOPUP ORDERKUOTA**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Nama** : {nama}\n"
            f"💰 **Total** : `{formatted_rp}`\n"
            f"💳 **Metode Pembayaran:** OrderKuota\n"
            f"🔢 **Kode Unik**: {kode_unik}\n\n"
            f"✅ **Scan QRIS di atas!**\n"
            f"Nominal otomatis muncul. Jika tidak, transfer manual ke:\n"
            f"`{formatted_salin}`\n\n"
        ),
        parse_mode='Markdown'
    )

    sukses = False
    start_time = datetime.now() # Kita pakai datetime object biar gampang compare

    logger.info(f"[START] Memulai Cek Mutasi untuk: {formatted_rp} (User: {sender.id})")
    
    # URL & Header Config (Bisa taruh di global variable sebenernya)
    sukses = False
    start_time = datetime.now()
    
    logger.info(f"[START] Memulai Cek Mutasi untuk: {formatted_rp} (User: {sender.id})")

    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # PERBAIKAN: Gunakan ORKUT_USERNAME (Akun Kamu), JANGAN username telegram user
    payload_mutasi = {
        "action": "mutasi_orkut",
        "username": ORKUT_USERNAME,    # <--- INI YG PENTING
        "auth_token": ORKUT_TOKEN,     # <--- INI JUGA
        "merchant": ORKUT_MERCHANT,
        "mutasi": "in"
    }

    # Loop 20x (Setiap 30 detik = 10 Menit)
    for i in range(20):
        await asyncio.sleep(15)
        print(f"\n[DEBUG] Request Mutasi ke-{i+1}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, json=payload_mutasi, headers=HEADERS, timeout=10) as response:
                    text_debug = await response.text() # Baca raw text dulu buat debug
                    
                    if response.status != 200:
                        print(f"[ERROR] HTTP Status: {response.status} | Body: {text_debug}")
                        continue
                    
                    try:
                        data = json.loads(text_debug)
                    except:
                        print(f"[ERROR] Gagal Parse JSON: {text_debug}")
                        continue

            # Ambil list hasil
            qris_data = data.get("data", {}).get("qris_history", {})
            results = qris_data.get("results", [])
            
            # DEBUG: Print jumlah data yg didapat
            print(f"[DEBUG] API Success: True. Ditemukan {len(results)} transaksi.")

            if qris_data.get("success") == True:
                for trx in results:
                    # Ambil data penting
                    trx_status = trx.get("status")
                    raw_kredit = str(trx.get("kredit", "0"))
                    clean_kredit = raw_kredit.replace(".", "").replace(",", "")
                    trx_amount = int(clean_kredit)
                    trx_time_str = trx.get("tanggal")
                    
                    # LOG DEBUG PER TRANSAKSI
                    # print(f" -> Cek TRX ID {trx.get('id')}: Rp {trx_amount} ({trx_status}) Tgl: {trx_time_str}")

                    # 1. Cek Status
                    if trx_status != "IN": 
                        continue
                    
                    # 2. Cek Tanggal
                    try:
                        trx_dt = datetime.strptime(trx_time_str, "%d/%m/%Y %H:%M")
                        # Toleransi: Transaksi harus setelah (waktu bot start - 5 menit)
                        # Ditambah toleransi 5 menit jaga2 jam server orkut kecepetan/telat dikit
                        if trx_dt < (start_time - timedelta(minutes=5)):
                            # print(f"    [SKIP] Transaksi lama ({trx_dt} < {start_time})")
                            continue
                    except Exception as e:
                        print(f"    [ERROR] Gagal parse tanggal: {e}")
                        continue

                    # 3. CEK NOMINAL (THE MOMENT OF TRUTH)
                    if trx_amount == nominal_unik:
                        print(f"[MATCH] DITEMUKAN! Rp {trx_amount} User: {sender.id}")
                        
                        # === EKSEKUSI DATABASE ===
                        reference = str(trx.get("id"))
                        user_id = sender.id

                        try:
                            db = get_db_connection()
                            cursor = db.cursor()
                            _ensure_processed_table(cursor, db)

                            if _has_been_processed(cursor, db, reference):
                                print(f"    [SKIP] Referensi {reference} sudah pernah masuk.")
                                sukses = True
                                break

                            cursor.execute("UPDATE user SET saldo = saldo + %s WHERE id_telegram = %s", (nominal_unik, str(user_id)))
                            cursor.execute("INSERT INTO processed_topup(reference) VALUES(%s)", (reference,))
                            set_success_transaction(nominal_unik)
                            
                            db.commit()
                            sukses = True
                            
                        except Exception as e:
                            print(f"[CRITICAL] Error DB: {e}")
                            if db: db.rollback()
                        finally:
                            if db: db.close()

                        break # Break loop trx
            
            if sukses: break # Break loop polling
            
        except Exception as e:
            logger.error(f"Error Polling Loop: {e}")
            continue

    # 6. Penanganan Hasil Akhir
    try:
        await msg_invoice.delete() # Hapus QR Code
    except: pass

    if sukses:
        await event.respond(
            f"✅ **Deposit Berhasil!**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 **Saldo Masuk**: {formatted_rp}\n"
            f"🆔 **No. Ref**: `{reference}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Terima kasih sudah topup.",
            buttons=[[Button.inline("🔙 Menu", b"menu")]]
        )
        # Lapor ke Admin
        await send_admin_notification(sender.id, sender.first_name, formatted_rp)
            
    else:
        # Set Expired di DB
        set_expired_transaction(nominal_unik)
        await event.respond(
            f"⚠️ **Waktu Habis / Belum Terdeteksi**\n"
            f"Jika sudah melakukan pembayaran saldo tidak masuk, hubungi admin dengan bukti transfer.",
            buttons=[[Button.url("💬 Admin", "https://t.me/@rizkihdyt")]]
        )