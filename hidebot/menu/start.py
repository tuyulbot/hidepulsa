from hidebot import *
from .fungsi_menu import *

@bot.on(events.NewMessage(pattern=r"(?:.start|/start)$"))
@bot.on(events.CallbackQuery(data=b'start'))
async def start(event):
    sender = await event.get_sender()
    first_name = sender.first_name
    last_name = sender.last_name
    full_name = first_name
    if last_name:
        full_name += " " + last_name

    if user_exists1(sender.id) or user_exists2(sender.id):  
        success, message = False, "User sudah ada tidak ditambahkan lagi."
    else:
    # Jika belum ada di kedua tabel, pilih fungsi penambahan sesuai kebutuhan
        success, message = add_memberr(full_name, sender.id, "reseller")


    if success:
        msg = f"""
✨ Hai {full_name}! Selamat datang di bot kami! ✨

Anda sekarang resmi terdaftar sebagai **Reseller** di sistem kami! 🚀 Bersiaplah untuk pengalaman seru dan kesempatan luar biasa yang menanti anda untuk menghasilkan uang!

💳 **ID Telegram:** {sender.id}  
📛 **Username:** {full_name}  
💰 **Saldo:** 0  
🎖 **Role:** Reseller  
✅ **Status:** {message}  

🔥 **Ingin segera memulai?** Top-up sekarang ketik */menu* dan pilih *Topup* untuk membuka akses penuh ke fitur kami! Jangan lewatkan kesempatan untuk menggunakan layanan kami. 💸✨
💥 **INFO PENTING!** 💥  
Transaksi harian Anda gacor? Kami akan upgrade role Anda ke **Super Reseller** dengan harga spesial! Nikmati keuntungan lebih besar dan akses dengan harga yang lebih murah daripada reseller biasa! Jadi, ayo aktif bertransaksi dan raih level ini! 🌟
"""
    else:
        msg = f"""
⚠️ **Oops, {full_name}!** Sepertinya Anda sudah terdaftar sebagai Reseller.  

💳 **ID Telegram:** {sender.id}  
📛 **Username:** {full_name}  
🎖 **Role:** Reseller  
❗️ **Status:** {message}  

🚀 **Siap melanjutkan perjalanan?** Jangan lupa untuk top-up di menu *Top-Up* agar Anda bisa menikmati fitur kami! Mari kita mulai! 🌟

💥 **INFO PENTING!** 💥  
Transaksi harian Anda gacor? Kami akan upgrade role Anda ke **Super Reseller** dengan harga spesial! Nikmati keuntungan lebih besar dan akses dengan harga yang lebih murah daripada reseller biasa! Jadi, ayo aktif bertransaksi dan raih level ini! 🌟
"""

    # Mengirim pesan ke pengguna
    await event.respond(msg)