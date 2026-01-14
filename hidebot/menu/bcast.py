from .fungsi_menu import *
from hidebot import *

@bot.on(events.NewMessage(pattern="(?:/bcast)"))
async def bcast(event):
    # Koneksi ke database
    db1 = get_db_connection()
    db2 = get_db_connection2()
    
    memberz = []
    memberz1 = []
    
    try:
        # Mengambil data `id_telegram` dari tabel `user` di database pertama
        cursor1 = db1.cursor()
        cursor1.execute("SELECT id_telegram FROM user")
        memberz = [x[0] for x in cursor1.fetchall()]

        # Mengambil data `id_telegram` dari tabel `ress` di database kedua
        cursor2 = db2.cursor()
        cursor2.execute("SELECT id_telegram FROM ress")
        memberz1 = [x[0] for x in cursor2.fetchall()]

        # Gabungkan kedua daftar ID Telegram
        memberz_combined = list(set(memberz + memberz1))

    finally:
        # Tutup semua koneksi dan cursor
        if cursor1:
            cursor1.close()
        if db1:
            db1.close()
        if cursor2:
            cursor2.close()
        if db2:
            db2.close()

    async def bcast_(event, res):
        if event.is_reply:
            msg = await event.get_reply_message()
            try:
                await bot.send_message(res, msg)  # Menggunakan 'bot' sebagai klien untuk mengirim pesan
                return True  # Berhasil mengirim pesan
            except Exception as e:
                print(f"Broadcast ke user {res} gagal: {e}")
                return False  # Gagal mengirim pesan

        else:
            await event.respond("**Reply To Message, File, Media, Images, Or Sticker!**")
            return False  # Gagal mengirim pesan karena tidak ada pesan balasan

    sender = await event.get_sender()
    # Jika pengirim merupakan pengguna yang valid, panggil fungsi broadcast
    if valid_admin(str(sender.id)) == "true":
        if event.is_reply:
            success_count = 0
            for res in memberz_combined:
                success = await bcast_(event, res)
                if success:
                    success_count += 1
            
            await event.respond(f"**Berhasil Broadcast ke semua Reseller**")
        else:
            await event.respond("**Reply To Message, File, Media, Images, Or Sticker!**")
    else:
        await event.respond("**Akses Ditolak**")
