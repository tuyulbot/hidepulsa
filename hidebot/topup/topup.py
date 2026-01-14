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

# kalau kamu pakai helper ini dari project-mu, biarkan apa adanya
from hidebot.menu.fungsi_menu import *

TRIPAY_MERCHANT_CODE = "T31636"
TRIPAY_API_KEY       = "1AcH9hzNWgrWP3XfhXAsfdbeGJ3UIMMXZBWqIX5E"
TRIPAY_PRIVATE_KEY   = "egXFM-WDUw3-yA75X-8qK8X-VastB"
TRIPAY_MERCHANT_REF  = "VipTunnel"

TRIPAY_CREATE_URL    = "https://tripay.co.id/api/transaction/create"
TRIPAY_STATUS_URL    = "https://tripay.co.id/api/transaction/check-status"

CALLBACK_RETURN_URL  = "https://viptunnel.id/"  # kembali ke webmu setelah bayar

# =========================
# /topupp handler
# =========================
@bot.on(events.NewMessage(pattern=r"(?:\.topupp|/topupp)$"))
@bot.on(events.CallbackQuery(data=b'topup'))
async def topup(event):
    sender = await event.get_sender()
    nama = f"{sender.first_name}".strip()
    uid = str(sender.id)

    # validasi role
    if not (valid_admin(uid) or valid_reseller(uid) or valid_priority(uid) or valid_superreseller(uid)):
        await event.respond("**Anda tidak terdaftar dalam sistem.**")
        return

    amount = await get_topup_amount(sender)
    if amount is None:
        return

    # expired invoice 24 jam
    expiry = int(time.time() + (24 * 60 * 60))

    # signature Tripay = HMAC-SHA256(privateKey, merchant_code + merchant_ref + amount)
    sign_str = f"{TRIPAY_MERCHANT_CODE}{TRIPAY_MERCHANT_REF}{amount}"
    signature = hmac.new(TRIPAY_PRIVATE_KEY.encode("latin-1"), sign_str.encode("latin-1"), hashlib.sha256).hexdigest()

    # payload form-encoded
    data = {
        "method": "QRIS2",
        "amount": amount,
        "merchant_ref": TRIPAY_MERCHANT_REF,
        "customer_name": uid,
        "customer_email": "etimaylana@gmail.com",
        "return_url": CALLBACK_RETURN_URL,
        "expired_time": expiry,
        "signature": signature
    }

    # order_items[*] sesuai format Tripay
    order_items = [{
        "sku": "TopUp",
        "name": f"TopUp Saldo Nominal {amount}",
        "price": amount,
        "quantity": 1,
        "product_url": "https://viptunnel.id/product",
        "image_url": "null"
    }]
    i = 0
    for item in order_items:
        for k, v in item.items():
            data[f'order_items[{i}][{k}]'] = v
        i += 1

    head = {"Authorization": "Bearer " + TRIPAY_API_KEY}

    print("Data yang dikirim ke Tripay:", data)
    print("Signature yang dibuat:", signature)

    try:
        result = requests.post(TRIPAY_CREATE_URL, data=data, headers=head, timeout=25)
        resp_text = result.text
        print("Respons dari Tripay:", resp_text)
        js = json.loads(resp_text)
    except Exception as e:
        await event.respond(f"**Gagal membuat transaksi:** {e}")
        return

    if result.status_code != 200 or not js.get("success"):
        await event.respond(f"**Error:** {js.get('message', 'Nominal TopUp Kurang / gagal membuat transaksi')}")
        return

    data_tripay = js["data"]
    reference   = data_tripay["reference"]
    checkout    = data_tripay["checkout_url"]
    qr_url      = data_tripay.get("qr_url")
    # yang masuk saldo user adalah amount_received; fallback ke amount (atau amount user)
    #amount_received = int(data_tripay.get("amount_received") or data_tripay.get("amount") or amount)
    amount_received = int(data_tripay.get("amount"))

    # download QR biar bisa dikirim sebagai gambar
    qr_path = None
    if qr_url:
        try:
            qr_bytes = requests.get(qr_url, timeout=25).content
            qr_path = "qr.png"
            with open(qr_path, "wb") as w:
                w.write(qr_bytes)
        except Exception as e:
            print(f"Gagal unduh QR: {e}")

    msg = (
            f"🧾 **INVOICE TOPUP QIOSPAY**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Nama** : {nama}\n"
            f"💰 **Total** : `{amount:,}`\n"
            f"💳 **Metode Pembayaran:** QiosPay\n"
            f"✅ **Scan QRIS di atas!**\n"
        )

    buttons = [[Button.url("Lanjutkan di TriPay", checkout)]]

    await event.reply(msg, file=qr_path if qr_path else None, buttons=buttons)

    # mulai polling status
    await check_payment_status(
        reference=reference,
        user_id=sender.id,
        amount_used=int(data_tripay.get("amount") or amount),  # info saja
        sender=sender,
        amount_requested=amount_received  # ini yang akan dipakai sebagai kredit
    )


# =========================
# Polling status Tripay
# =========================
async def check_payment_status(reference, user_id, amount_used, sender, amount_requested):
    """
    reference        : kode referensi Tripay
    user_id          : Telegram user id
    amount_used      : nilai 'amount' dari create (informasi—biasanya termasuk fee customer)
    amount_requested : nominal yang seharusnya dikreditkan (pakai amount_received jika ada)
    """
    headers = {"Authorization": "Bearer " + TRIPAY_API_KEY}
    params  = {"reference": reference}

    # cek max 10x, jeda 30s
    for _ in range(10):
        try:
            r = requests.get(TRIPAY_STATUS_URL, params=params, headers=headers, timeout=20)
            response = r.json()
            print("Respons dari Tripay:", response)

            data     = response.get("data") or {}
            status   = (data.get("status") or "").strip().upper()
            message  = (response.get("message") or "").strip()

            # fallback: parse status dari message jika data.status kosong
            if not status and message:
                m = re.search(r"status\s+transaksi\s+saat\s+ini\s+([A-Za-z_]+)", message, flags=re.I)
                if m:
                    status = m.group(1).upper()
                else:
                    # fallback kedua: hard check UNPAID/PAID
                    msg_up = message.upper()
                    if "UNPAID" in msg_up:
                        status = "UNPAID"
                    elif re.search(r'\bPAID\b', msg_up):
                        status = "PAID"

            PAID_STATUSES = {"PAID", "SETTLED", "SUCCESS", "PAID_OFF"}
            is_paid = status in PAID_STATUSES

            print(f"[Tripay] parsed_status={status!r} raw_message={message!r}")

            if is_paid:
                # tentukan nominal kredit (prioritas: amount_received)
                credit_amount = int(
                    (data.get("amount_received")
                     or data.get("amount")
                     or amount_requested)
                )

                db = get_db_connection2()
                cursor = db.cursor()

                # buat tabel penanda agar tidak double-credit
                _ensure_processed_table(cursor, db)

                if _has_been_processed(cursor, db, reference):
                    print(f"[Topup] Reference {reference} sudah pernah diproses, skip.")
                    break

                # deteksi sqlite vs lainnya untuk placeholder
                is_sqlite = isinstance(db, sqlite3.Connection)

                if is_sqlite:
                    # kredit saldo
                    cursor.execute(
                        "UPDATE ress SET saldo = saldo + ? WHERE id_telegram = ?",
                        (credit_amount, str(user_id))
                    )
                    # simpan reference
                    cursor.execute(
                        "INSERT INTO processed_topup(reference) VALUES(?)",
                        (reference,)
                    )
                else:
                    cursor.execute(
                        "UPDATE ress SET saldo = saldo + %s WHERE id_telegram = %s",
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
                        # ulangi insert
                        cursor.execute(
                            "INSERT INTO processed_topup(reference) VALUES(%s)",
                            (reference,)
                        )

                db.commit()
                print(f"Saldo user {user_id} ditambah Rp {credit_amount:,} (ref: {reference})")

                # notifikasi user
                await bot.send_message(
                    user_id,
                    f"**Top-up berhasil!**\n\n"
                    f"Saldo Anda telah ditambahkan Rp. {credit_amount:,}.\n\n"
                    f"Terima kasih telah menggunakan layanan kami!"
                )

                # notifikasi admin
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


def _ensure_processed_table(cursor, db):
    """Buat tabel processed_topup kalau belum ada (cocok untuk sqlite & lainnya)."""
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS processed_topup (reference TEXT PRIMARY KEY)")
        db.commit()
    except Exception:
        # untuk engine tertentu, PRIMARY KEY TEXT mungkin error—biarkan tanpa PK
        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS processed_topup (reference TEXT)")
            db.commit()
        except Exception:
            pass


def _has_been_processed(cursor, db, reference: str) -> bool:
    """Cek apakah reference sudah pernah diproses. Coba '?' lalu '%s'."""
    try:
        cursor.execute("SELECT reference FROM processed_topup WHERE reference = ?", (reference,))
        return cursor.fetchone() is not None
    except Exception:
        try:
            cursor.execute("SELECT reference FROM processed_topup WHERE reference = %s", (reference,))
            return cursor.fetchone() is not None
        except Exception:
            return False


# =========================
# Prompt input nominal
# =========================
async def get_topup_amount(sender):
    async with bot.conversation(sender.id) as conv:
        await conv.send_message("**Exit = back to menu**\n\n**Masukkan jumlah top-up (Minimal 10.000):**")

        try:
            response = await conv.wait_event(events.NewMessage(incoming=True, from_users=sender.id))
            amount_txt = (response.message.message or "").replace(".", "").strip()

            if amount_txt.lower() == "exit":
                await conv.send_message(
                    "**Pembatalan top-up. Kembali ke menu.**",
                    buttons=[[Button.inline("🔙ᴍᴇɴᴜ", b"menu")]]
                )
                return None

            if amount_txt.isdigit() and int(amount_txt) >= 10_000:
                return int(amount_txt)

            await conv.send_message("**Jumlah top-up harus berupa angka dan minimal 10.000.**")
            return None

        except asyncio.TimeoutError:
            await conv.send_message("**Waktu habis, harap coba lagi.**")
            return None


# =========================
# Notifikasi admin
# =========================
async def send_admin_notification(user_id, user_name, amount):
    admin_id = 1316596937  # ganti dengan admin ID kamu
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
