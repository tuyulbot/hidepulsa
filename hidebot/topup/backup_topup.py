from hidebot import *
from telethon import events, Button
import requests
import json
import time
import hmac
import hashlib
import asyncio
import sqlite3
from hidebot.menu.fungsi_menu import *

@bot.on(events.NewMessage(pattern=r"(?:.topupp|/topupp)$"))
@bot.on(events.CallbackQuery(data=b'topup'))
async def topup(event):
    sender = await event.get_sender()
    val = valid_admin(str(sender.id))
    val1 = valid_reseller(str(sender.id))
    val2 = valid_priority(str(sender.id))
    val3 = valid_superreseller(str(sender.id))

    # Ensure the user is valid
    if val or val1 or val2 or val3:
        amount = await get_topup_amount(sender)
        
        if amount is None:
            #await event.respond("**Jumlah top-up tidak valid atau tidak diterima.**")
            return
        
        merchant_code = "T31636"
        apiKey = "1AcH9hzNWgrWP3XfhXAsfdbeGJ3UIMMXZBWqIX5E"
        privateKey = "egXFM-WDUw3-yA75X-8qK8X-VastB"
        merchant_ref = "VipTunnel"
        expiry = int(time.time() + (24*60*60))

        signStr = "{}{}{}".format(merchant_code, merchant_ref, amount)
        signature = hmac.new(bytes(privateKey, 'latin-1'), bytes(signStr, 'latin-1'), hashlib.sha256).hexdigest()

        url = "https://tripay.co.id/api/transaction/create"
        head = {"Authorization": "Bearer " + apiKey}
        data = {
            "method": "QRIS2",
            "amount": amount,
            "merchant_ref": merchant_ref,
            "customer_name": str(sender.id),
            "customer_email": "etimaylana@gmail.com",
            "return_url": "https://viptunnel.id/",
            "expired_time": expiry,
            "signature": signature
        }

        order_items = [
            {
                'sku': 'TopUp',
                'name': f'TopUp Saldo Nominal {amount}',
                'price': amount,
                'quantity': 1,
                'product_url': 'https://viptunnel.id/product',
                'image_url': 'null'
            }
        ]
        i = 0
        for item in order_items:
            for k in item:
                data[f'order_items[{i}][{k}]'] = item[k]
            i += 1

        print("Data yang dikirim ke Tripay:", data)
        print("Signature yang dibuat:", signature)

        result = requests.post(url, data=data, headers=head)
        response = result.text
        print("Respons dari Tripay:", response)

        try:
            js = json.loads(response)

            if result.status_code == 200:
                amount_used = js["data"]["amount"]
                print(f"Jumlah TopUp yang digunakan: {amount_used}")
                qr = requests.get(js["data"]["qr_url"]).content
                with open("qr.png", "wb") as w:
                    w.write(qr)
                await event.reply(
                    f"""
╭───────────────────────╮
│          TOP UP SALDO
├───────────────────────┤
│
│  Nominal TopUp: Rp {amount:,}
│  Metode pembayaran: QRIS
│
│   Silahkan scan QR diatas
│   Atau Klik link dibawah
│
│   Noted :
│    - Jika saldo tidak masuk kontak admin dan kirimkan bukti pembayaran.
│
╰───────────────────────╯""",
                file="qr.png",
                buttons=[[Button.url("Lanjutkan di TriPay", js["data"]["checkout_url"])]])
                

                # Simpan referensi transaksi di database
                reference = js["data"]["reference"]
                ##cursor.execute("UPDATE user SET transaction_reference = ? WHERE member = ?", (reference, sender.id))

                # Panggil fungsi untuk memeriksa status pembayaran
                await check_payment_status(reference, sender.id, amount_used, sender, amount)
            else:
                await event.respond(f"**Error: {js.get('message', 'Nominal TopUp Kurang')}**")
        except json.JSONDecodeError:
            await event.respond("**Gagal memproses respons dari Tripay.**")
    else:
        await event.respond("**Anda tidak terdaftar dalam sistem.**")
 
async def check_payment_status(reference, user_id, amount, sender, amount1):
    apiKey = "1AcH9hzNWgrWP3XfhXAsfdbeGJ3UIMMXZBWqIX5E"
    url = "https://tripay.co.id/api/transaction/check-status"
    payload = {"reference": reference}
    headers = {"Authorization": "Bearer " + apiKey}

    for _ in range(10):  # Coba cek status hingga 10 kali
        try:
            # Kirimkan permintaan GET ke API Tripay
            print(f"Memeriksa status untuk referensi: {reference}")
            result = requests.get(url, params=payload, headers=headers)
            response = result.json()

            # Debug print untuk memeriksa struktur respons
            print("Respons dari Tripay:", response)

            # Cek status success dan pesan dari respons
            success = response.get('success', False)
            message = response.get('message', '')

            # Tambahkan saldo hanya jika status success adalah False dan pesan mengandung PAID
            if not success and "PAID" in message.upper():
                print(f"Status untuk referensi {reference}: PAID")

                # Update saldo pengguna di database yang sesuai
                db = get_db_connection2()
                cursor = db.cursor()
                cursor.execute("UPDATE ress SET saldo = saldo + %s WHERE id_telegram = %s", (amount, user_id))

                db.commit()
                print(f"Saldo untuk user {user_id} berhasil diperbarui sebesar {amount}")

                # Kirimkan pesan notifikasi ke pengguna Telegram
                user = await bot.get_entity(user_id)
                message = (
    f"**Top-up berhasil!**\n\n"
    f"Saldo Anda telah ditambahkan Rp. {amount:,}.\n\n"
    f"Terima kasih telah menggunakan layanan kami!"
)

                await bot.send_message(user_id, message)

                await send_admin_notification(sender.id, sender.first_name, amount1)
                break
            else:
                print(f"Pembayaran untuk referensi {reference} belum berhasil, mencoba lagi...")

        except Exception as e:
            print(f"Error memeriksa status pembayaran untuk referensi {reference}: {str(e)}")

        # Tunggu 30 detik sebelum mencoba lagi
        await asyncio.sleep(30)
    
    else:
        # Jika loop selesai tanpa status PAID, anggap gagal
        print(f"Pembayaran gagal untuk referensi {reference}")
        await bot.send_message(
            user_id,
            f"**TopUp gagal anda blom membayar. Mohon coba lagi.**"
        )


async def get_topup_amount(sender):
    async with bot.conversation(sender.id) as conv:
        await conv.send_message("**Exit = back to menu \n\nMasukkan jumlah top-up (Minimal 10.000):**")
        
        try:
            response = await conv.wait_event(events.NewMessage(incoming=True, from_users=sender.id))
            amount = response.message.message.replace(".", "").strip()
            
            # Memeriksa jika input adalah "exit"
            if amount.lower() == "exit":
                await conv.send_message("**Pembatalan top-up. Kembali ke menu.**", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "menu")]])
                return None
            
            if amount.isdigit() and int(amount) >= 10000:
                return int(amount)
            else:
                await conv.send_message("**Jumlah top-up harus berupa angka dan minimal 10.000.**")
                return None
        except asyncio.TimeoutError:
            await conv.send_message("**Waktu habis, harap coba lagi.**")
            return None

async def send_admin_notification(user_id, user_name, amount):
    admin_id = 1316596937  # Gantilah dengan ID Telegram admin
    await bot.send_message(
        admin_id,
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"       ☆ NOTIFIKASI TOPUP ☆:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**▪ID Pengguna:** {user_id}\n"
        f"**▪Nama Pengguna:** {user_name}\n"
        f"**▪Nominal Top-Up:** Rp. {amount:,}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )