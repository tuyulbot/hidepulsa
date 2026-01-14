from hidebot import *
import qrcode
import io
import random
from datetime import datetime, timedelta


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
        f"**▪Metode Pembayaran:** QiosPay\n"
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
            kode_unik = random.randint(1, 999) # Acak 3 digit
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

# ==========================================
# BAGIAN 2: LOGIKA QRIS DINAMIS (INJECT NOMINAL)
# ==========================================

def crc16_ccitt(data):
    """
    Rumus Wajib untuk menghitung 4 digit terakhir QRIS.
    Tanpa ini, QRIS dianggap rusak (Invalid).
    """
    crc = 0xFFFF
    if isinstance(data, str):
        data = data.encode('utf-8')
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if (crc & 0x8000):
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
        crc &= 0xFFFF
    return f"{crc:04X}"

def create_dynamic_qris(raw_qris, nominal):
    """
    Hanya Menambahkan Nominal (Tag 54).
    Tidak mengubah header Static (010211).
    """
    str_nominal = str(nominal)
    
    # 1. HAPUS 4 DIGIT TERAKHIR (CRC LAMA)
    # Kita harus buang checksum lama (77A1) karena isinya akan berubah
    # QRIS Nobu anda: ...630477A1. Kita potong 8 char dari belakang (Tag 6304 + Value)
    qris_body = raw_qris[:-8] 
    
    # 2. BUAT TAG NOMINAL (Tag 54)
    # Format: 54 + Panjang + Nominal
    # Contoh: 540515000
    tag_amount = f"54{len(str_nominal):02d}{str_nominal}"
    
    # 3. SELIPKAN TAG NOMINAL
    # Aturan QRIS: Tag 54 harus ada SETELAH Tag 53 (Currency)
    # Di string anda ada: '5303360' (Mata Uang Rupiah)
    # Kita ganti '5303360' menjadi '5303360' + Tag Nominal
    
    if '5303360' in qris_body:
        qris_inject = qris_body.replace('5303360', '5303360' + tag_amount)
    else:
        # Jaga-jaga kalau string beda, tempel sebelum negara (5802ID)
        qris_inject = qris_body.replace('5802ID', tag_amount + '5802ID')

    # 4. HITUNG CRC BARU
    # Tambahkan header CRC (6304)
    qris_final_raw = qris_inject + "6304"
    
    # Hitung rumusnya
    new_crc = crc16_ccitt(qris_final_raw)
    
    # 5. GABUNGKAN
    return qris_final_raw + new_crc

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

# Konfigurasi
DATA_QRIS_STATIC = "00020101021126670016COM.NOBUBANK.WWW01189360050300000907180214804079506613940303UMI51440014ID.CO.QRIS.WWW0215ID20254684996400303UMI5204541153033605802ID5925Warung Kelontong Biunge M6008BANYUMAS61055311162070703A016304C9DF"
API_KEY = "9a1a701ead6007d2c08dff3156f88ff5b0528ff7955473894051be371f9df727"
MERCHANT_ID = "QP042742"
ADMIN_ID = "1316596937" # ID Telegram Admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@bot.on(events.NewMessage(pattern='/topp'))
@bot.on(events.CallbackQuery(data=b'topp'))
async def topp_handler(event):
    chat = event.chat_id
    sender = await event.get_sender()
    
    username = sender.username if sender.username else "NoUser"
    nama = f"{sender.first_name}".strip()

    # 1. Input Nominal
    async with bot.conversation(chat) as conv:
        try:
            msg_tanya = await event.respond("💬 **Topup Saldo**\n\nMasukkan nominal (Min. 1000):\nContoh: `50000`")
            buyer_msg = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id), timeout=60)
            
            nominal_str = buyer_msg.raw_text.strip().replace('.', '').replace(',', '')
            if not nominal_str.isdigit():
                await event.respond("❌ Nominal harus angka.")
                return
            
            nominal_int = int(nominal_str)
            if nominal_int < 500:
                await event.respond("❌ Minimal topup Rp 1.000")
                return
            
            # Hapus chat agar bersih
            await msg_tanya.delete()
            await buyer_msg.delete()

        except asyncio.TimeoutError:
            await event.respond("❌ Waktu habis.")
            return

    # 2. Generate Nominal Unik & Simpan ke DB
    try:
        # Fungsi ini otomatis INSERT ke database dengan status 'pending'
        # dan memastikan angka uniknya tidak dipake orang lain
        nominal_unik, kode_unik = get_unique_nominal(sender.id, username, nominal_int)
    except Exception as e:
        logger.error(f"DB Full: {e}")
        await event.respond("⚠️ Sistem sedang sibuk, coba nominal lain.")
        return

    # 3. Buat QRIS Dinamis (Ada Nominalnya)
    try:
        qris_string_fix = create_dynamic_qris(DATA_QRIS_STATIC, nominal_unik)
        qr_image = generate_qr_image(qris_string_fix)
    except:
        # Fallback jika gagal inject, pakai QR biasa
        qr_image = generate_qr_image(DATA_QRIS_STATIC)

    # 4. Kirim Invoice
    formatted_rp = f"Rp {nominal_unik:,.0f}".replace(",", ".")
    formatted_salin = str(nominal_unik)
    
    msg_invoice = await bot.send_file(
        chat,
        qr_image,
        caption=(
            f"🧾 **INVOICE TOPUP QIOSPAY**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Nama** : {nama}\n"
            f"💰 **Total** : `{formatted_rp}`\n"
            f"💳 **Metode Pembayaran:** QiosPay\n"
            f"🔢 **Kode Unik**: {kode_unik}\n\n"
            f"✅ **Scan QRIS di atas!**\n"
            f"Nominal otomatis muncul. Jika tidak, transfer manual ke:\n"
            f"`{formatted_salin}`\n\n"
        ),
        parse_mode='Markdown'
    )

    # 5. Loop Pengecekan Mutasi (Polling)
    sukses = False
    start_time = int(time.time())
    
    # Cek selama 10 menit (20 x 30 detik)
    for i in range(20):
        await asyncio.sleep(30)
        
        try:
            # Request ke API QiosPay
            res = requests.get(
                f"https://qiospay.id/api/mutasi/qris/{MERCHANT_ID}/{API_KEY}", 
                timeout=10
            )
            data = res.json()

            if data.get("status") == "success":
                for trx in data.get("data", []):
                    # Filter Validasi
                    if trx.get("type") != "CR": continue # Harus Kredit/Masuk
                    
                    # Parse Waktu Transaksi
                    try:
                        trx_time = time.mktime(time.strptime(trx.get("date"), "%Y-%m-%d %H:%M:%S"))
                    except: continue

                    # Transaksi harus LEBIH BARU dari waktu request bot
                    if trx_time < start_time: continue

                    # Cek Nominal
                    trx_amount = int(float(trx.get("amount", 0)))
                    
                    if trx_amount == nominal_unik:
                        # === KUNCI SUKSES (PENTING) ===
                        # Update DB dulu. Jika return True, berarti belum ada yang proses.
                        if set_success_transaction(nominal_unik):
                            sukses = True
                            
                            # +++++ AREA TAMBAH SALDO +++++
                            # Panggil fungsi tambah saldo kamu di sini
                            # contoh: add_saldo(sender.id, nominal_unik)
                            # +++++++++++++++++++++++++++++
                            
                            logger.info(f"Topup Sukses: {sender.id} - {formatted_rp}")
                        break
            
            if sukses: break
            
        except Exception as e:
            logger.error(f"Error Polling: {e}")
            continue

    # 6. Penanganan Hasil Akhir
    try:
        await msg_invoice.delete() # Hapus QR Code
    except: pass

    if sukses:
        await event.respond(
            f"✅ **Deposit Berhasil!**\n\n"
            f"💰 Saldo Masuk: {formatted_rp}\n"
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