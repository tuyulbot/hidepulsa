from hidebot import *
from telethon import events, Button
import requests
import json
import time
import hmac
import hashlib
import asyncio
import sqlite3
import re
from datetime import datetime, timedelta

from hidebot.menu.fungsi_menu import *

# ====== Konfigurasi Tripay ======
TRIPAY_MERCHANT_CODE = "T31636"
TRIPAY_API_KEY       = "1AcH9hzNWgrWP3XfhXAsfdbeGJ3UIMMXZBWqIX5E"
TRIPAY_PRIVATE_KEY   = "egXFM-WDUw3-yA75X-8qK8X-VastB"
TRIPAY_MERCHANT_REF  = "VipTunnel"

TRIPAY_CREATE_URL    = "https://tripay.co.id/api/transaction/create"
TRIPAY_STATUS_URL    = "https://tripay.co.id/api/transaction/check-status"

RETURN_URL           = "https://viptunnel.id/"

# ====== Handler /topupp dan tombol 'topup1' ======
@bot.on(events.NewMessage(pattern=r"(?:\.topupp|/topupp)$"))
@bot.on(events.CallbackQuery(data=b'topup1'))
async def topup1(event):
    sender = await event.get_sender()
    nama = f"{sender.first_name}".strip()
    uid = str(sender.id)

    # Validasi role user
    if not (valid_admin(uid) or valid_reseller(uid) or valid_priority(uid) or valid_superreseller(uid)):
        await event.respond("**Anda tidak terdaftar dalam sistem.**")
        return

    amount = await get_topup_amount(sender)  # minimal 10.000
    if amount is None:
        return

    expiry = int(time.time() + 24*60*60)  # 24 jam

    # Signature HMAC-SHA256: merchant_code + merchant_ref + amount
    sign_str  = f"{TRIPAY_MERCHANT_CODE}{TRIPAY_MERCHANT_REF}{amount}"
    signature = hmac.new(TRIPAY_PRIVATE_KEY.encode("latin-1"),
                         sign_str.encode("latin-1"),
                         hashlib.sha256).hexdigest()

    # Request create transaksi (pakai method=QRIS sesuai versi code kamu)
    data = {
        "method": "QRIS",
        "amount": amount,
        "merchant_ref": TRIPAY_MERCHANT_REF,
        "customer_name": uid,
        "customer_email": "etimaylana@gmail.com",
        "return_url": RETURN_URL,
        "expired_time": expiry,
        "signature": signature
    }

    # order_items[*]
    order_items = [{
        "sku": "TopUp",
        "name": f"TopUp Saldo Nominal {amount}",
        "price": amount,
        "quantity": 1,
        "product_url": "https://viptunnel.id/product",
        "image_url": "null"
    }]
    for i, item in enumerate(order_items):
        for k, v in item.items():
            data[f'order_items[{i}][{k}]'] = v

    headers = {"Authorization": "Bearer " + TRIPAY_API_KEY}

    print("Data yang dikirim ke Tripay:", data)
    print("Signature yang dibuat:", signature)

    try:
        resp = requests.post(TRIPAY_CREATE_URL, data=data, headers=headers, timeout=25)
        resp_text = resp.text
        print("Respons dari Tripay:", resp_text)
        js = json.loads(resp_text)
    except Exception as e:
        await event.respond(f"**Gagal membuat transaksi:** {e}")
        return

    if resp.status_code != 200 or not js.get("success"):
        await event.respond(f"**Error:** {js.get('message', 'Gagal membuat transaksi / nominal tidak valid')}")
        return

    data_tripay   = js["data"]
    reference     = data_tripay["reference"]
    checkout_url  = data_tripay["checkout_url"]
    qr_url        = data_tripay.get("qr_url")

    # Nominal yang akan DIKREDITKAN: prioritas amount_received kalau ada
    #amount_received = int(data_tripay.get("amount_received") or data_tripay.get("amount") or amount)
    amount_received = int(data_tripay.get("amount"))

    # Download QR untuk dikirim
    qr_path = None
    if qr_url:
        try:
            qr_bytes = requests.get(qr_url, timeout=25).content
            qr_path = "qr.png"
            with open(qr_path, "wb") as f:
                f.write(qr_bytes)
        except Exception as e:
            print(f"Gagal unduh QR: {e}")

    message_text = (
            f"🧾 **INVOICE TOPUP QIOSPAY**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Nama** : {nama}\n"
            f"💰 **Total** : `{amount:,}`\n"
            f"💳 **Metode Pembayaran:** QiosPay\n"
            f"✅ **Scan QRIS di atas!**\n"
        )

    await event.reply(
        message_text,
        file=qr_path if qr_path else None,
        buttons=[[Button.url("Lanjutkan di TriPay", checkout_url)]],
    )

    # Mulai polling status
    await check_payment_status(
        reference=reference,
        user_id=sender.id,
        amount_used=int(data_tripay.get("amount") or amount),  # info saja
        sender=sender,
        amount_requested=amount_received  # ini yang akan dipakai sebagai kredit
    )

# ====== Polling status ======
async def check_payment_status(reference, user_id, amount_used, sender, amount_requested):
    headers = {"Authorization": "Bearer " + TRIPAY_API_KEY}
    params  = {"reference": reference}

    for _ in range(10):  # coba 10x, jeda 30s
        try:
            r = requests.get(TRIPAY_STATUS_URL, params=params, headers=headers, timeout=20)
            response = r.json()
            print("Respons dari Tripay:", response)

            data    = response.get("data") or {}
            status  = (data.get("status") or "").strip().upper()
            message = (response.get("message") or "").strip()

            # Fallback: parse status dari message jika data.status kosong
            if not status and message:
                m = re.search(r"status\s+transaksi\s+saat\s+ini\s+([A-Za-z_]+)", message, flags=re.I)
                if m:
                    status = m.group(1).upper()
                else:
                    msg_up = message.upper()
                    if "UNPAID" in msg_up:
                        status = "UNPAID"
                    elif re.search(r'\bPAID\b', msg_up):
                        status = "PAID"

            PAID_STATUSES = {"PAID", "SETTLED", "SUCCESS", "PAID_OFF"}
            is_paid = status in PAID_STATUSES

            print(f"[Tripay] parsed_status={status!r} raw_message={message!r}")

            if is_paid:
                credit_amount = int(
                    (data.get("amount_received")
                     or data.get("amount")
                     or amount_requested)
                )

                # === Update saldo + anti double credit ===
                db = get_db_connection()  # kamu sebelumnya pakai get_db_connection() di versi ini
                cursor = db.cursor()

                _ensure_processed_table(cursor, db)

                if _has_been_processed(cursor, db, reference):
                    print(f"[Topup] Reference {reference} sudah diproses, skip.")
                    break

                is_sqlite = isinstance(db, sqlite3.Connection)

                # Tabel saldo: 'user' (versi kamu ini pakai tabel user, bukan ress)
                if is_sqlite:
                    cursor.execute(
                        "UPDATE user SET saldo = saldo + ? WHERE id_telegram = ?",
                        (credit_amount, str(user_id))
                    )
                    cursor.execute(
                        "INSERT INTO processed_topup(reference) VALUES(?)",
                        (reference,)
                    )
                else:
                    cursor.execute(
                        "UPDATE user SET saldo = saldo + %s WHERE id_telegram = %s",
                        (credit_amount, str(user_id))
                    )
                    try:
                        cursor.execute(
                            "INSERT INTO processed_topup(reference) VALUES(%s)",
                            (reference,)
                        )
                    except Exception:
                        cursor.execute(
                            "CREATE TABLE IF NOT EXISTS processed_topup (reference TEXT PRIMARY KEY)"
                        )
                        cursor.execute(
                            "INSERT INTO processed_topup(reference) VALUES(%s)",
                            (reference,)
                        )

                db.commit()
                print(f"Saldo user {user_id} ditambah Rp {credit_amount:,} (ref: {reference})")

                # Notif user
                await bot.send_message(
                    user_id,
                    f"**Top-up berhasil!**\n\n"
                    f"Saldo Anda telah ditambahkan Rp. {credit_amount:,}.\n\n"
                    f"Terima kasih telah menggunakan layanan kami!"
                )

                # Notif admin
                await send_admin_notification(sender.id, sender.first_name, credit_amount)
                break
            else:
                shown = status if status else (message.upper() if message else "UNKNOWN")
                print(f"Pembayaran {reference} belum berhasil (status='{shown}'), coba lagi...")

        except Exception as e:
            print(f"Error cek status {reference}: {e}")

        await asyncio.sleep(30)
    else:
        await bot.send_message(
            user_id,
            "**TopUp gagal atau belum dibayar. Mohon coba lagi.**"
        )

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

# ====== Input nominal (MIN 10k) ======
async def get_topup_amount(sender):
    async with bot.conversation(sender.id) as conv:
        await conv.send_message("**Exit = back to menu**\n\n**Masukkan jumlah top-up (Minimal 25.000):**")
        try:
            resp = await conv.wait_event(events.NewMessage(incoming=True, from_users=sender.id))
            amount_txt = (resp.message.message or "").replace(".", "").strip()

            if amount_txt.lower() == "exit":
                await conv.send_message(
                    "**Pembatalan top-up. Kembali ke menu.**",
                    buttons=[[Button.inline("🔙ᴍᴇɴᴜ", b"menu")]]
                )
                return None

            if amount_txt.isdigit() and int(amount_txt) >= 25_000:
                return int(amount_txt)

            await conv.send_message("**Jumlah top-up harus berupa angka dan minimal 25.000.**")
            return None

        except asyncio.TimeoutError:
            await conv.send_message("**Waktu habis, harap coba lagi.**")
            return None

# ====== Notifikasi admin ======
async def send_admin_notification(user_id, user_name, amount):
    #admin_id = -1002345639504  # channel/group kamu; pastikan bot punya permission
    admin_id = 1316596937    # contoh kirim ke admin personal
    await bot.send_message(
        admin_id,
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "       ☆ NOTIFIKASI TOPUP ☆\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**▪ID Pengguna:** {user_id}\n"
        f"**▪Nama Pengguna:** {user_name}\n"
        f"**▪Nominal Top-Up:** Rp. {amount:,}\n"
        f"**▪Waktu:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"**▪Metode Pembayaran:** Tripay\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
