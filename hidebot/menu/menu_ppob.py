from hidebot import *
from .fungsi_menu import *
from .menu_indosat import *
from .menu_tri import *
from datetime import datetime
import pytz

@bot.on(events.CallbackQuery(data=b'ppob'))
async def ppob(event):
    # ==========================================
    # LOGIC CUT OFF HARIAN (23:50 - 00:20 WIB)
    # ==========================================
    try:
        # Set timezone ke WIB
        tz = pytz.timezone('Asia/Jakarta') 
        now = datetime.now(tz)
        hour = now.hour
        minute = now.minute

        # Cek Range Waktu (23:30 s/d 00:20)
        if (hour == 23 and minute >= 30) or (hour == 0 and minute <= 20):
            # Tampilan Kotak Cut Off
            msg_cutoff = f"""
╭───────────────────╮
│    ⛔ CUT OFF PUSAT ⛔   
├───────────────────┤
│ 🚧 MAINTENANCE HARIAN 
│ ⏰ 23:50 - 00:20 WIB  
│                       
│ Mohon maaf, saat ini sedang 
│ berlangsung Maintenance Harian
│ Silakan transkasi lagi
│ di jam 00:21 WIB.   
╰───────────────────╯
"""
            # Tambahkan tombol kembali
            buttons = [[Button.inline("🔙 Kembali ke Menu", b"menu")]]
            
            # Gunakan edit agar tampilan kotaknya rapi
            await event.edit(msg_cutoff, buttons=buttons)
            #await event.answer(msg_cutoff, alert=True)
            return

    except Exception as e:
        logger.error(f"Error checking time: {e}")
    logger.info(f"Command ppob dipanggil oleh {event.sender_id}")
    user_id = event.sender_id
    is_channel_member = await check_membership(event.client, user_id)

    # Cek membership di grup
    is_group_member = await check_group_membership(event.client, user_id)

    # Jika belum join salah satu, kirim tombol gabung
    if not is_channel_member or not is_group_member:
        buttons = []

        if not is_channel_member:
            buttons.append([Button.url("🔗 Join Channel", f"https://t.me/{CHANNEL_USERNAME}")])
        if not is_group_member:
            buttons.append([Button.url("💬 Join Grup", f"https://t.me/{GROUP_USERNAME}")])

        await event.respond(
            "⚠️ Anda harus bergabung dengan channel **dan** grup sebelum mengakses menu.\n\nSilakan join dulu dengan tombol di bawah.",
            buttons=buttons
        )
        return
    
    """if is_blocked(user_id):
        await event.respond("❌ Akses ditolak. Anda telah diblokir dari bot.")
        return"""

    await handle_ppobilegal(event)  # pakai await biar langsung muncul respon

async def handle_ppobilegal(event):
    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None
    username, idtele, role, saldo = get_user_info(sender.id)
    if username is None:
        username, idtele, role, saldo = get_user_info1(sender.id)
    if username is None:
        await event.reply("Untuk daftar silahkan ke @refresyitreborn, jangan lupa ngocok dulu")
        return
    if saldo <= 0:
        inline = [[Button.inline(" Topup ", b"topupmembernew")]]
        msg_monospace = f""" 
╭───────────────────╮
│           🤖 HIDE PULSA 🤖       
├───────────────────┤
│ 📝 {"User":<12} : {full_name}       
│ 🪪 {"Id-Tele":<10}  : {telegram_id}   
│ 💰 {"Saldo":<9}   : Rp: {saldo:,}     
│ 🎖️ {"Role":<9}    : {role}         
│
│ ⏰ {"Uptime":<8}  : {uptime} 
├───────────────────┤
│ Menu PPOB tanpa otp
╰───────────────────╯
"""
        msg = msg_monospace
        await event.client.send_message(
            event.chat_id,
            msg,
            buttons=inline
        )
        return
    # Tombol ppob 
    inline = [
        [Button.inline("PPOB XL DATA", b"buy_ppob|xl|data"),
        Button.inline("PPOB IM3 DATA", b"buy_ppob|indosat|data")],
        [Button.inline("PPOB SMARTFREN DATA", b"buy_ppob|smartfren|data")],
        [Button.inline("PPOB TRI DATA", b"buy_ppob|tri|data")],
        [Button.inline("PPOB MASTIF XL", b"buy_ppob|xl|Masa Aktif"),
        Button.inline("PPOB MASTIF TRI", b"buy_ppob|tri|Masa Aktif")],
        [Button.inline("PPOB MASTIF AXIS", b"buy_ppob|axis|Masa Aktif"),
        Button.inline("PPOB MASTIF INDOSAT", b"buy_ppob|indosat|Masa Aktif")],
        [Button.inline("PPOB MASTIF TELKOMSEL", b"buy_ppob|telkomsel|Masa Aktif")],
        [Button.inline("Back Menu", b"menu")],
    ]

    validations = [
    valid_admin(str(sender.id)),          # val
    valid_reseller(str(sender.id)),       # val1
    valid_priority(str(sender.id)),         # val2
    valid_superreseller(str(sender.id)),  # val3
    valid_reseller1(str(sender.id)),      # val4
    valid_superreseller1(str(sender.id)),  # val5
    valid_priority1(str(sender.id))
    ]

    val = valid_admin(str(sender.id))
    val1 = valid_reseller(str(sender.id))
    val2 = valid_priority(str(sender.id))
    val3 = valid_superreseller(str(sender.id))
    val4 = valid_reseller1(str(sender.id))
    val5 = valid_superreseller1(str(sender.id))
    val6 = valid_priority1(str(sender.id))

    vall = valid_admin(str(sender.id))
    vall1 = valid_superress_byid(str(sender.id))
    vall2 = valid_priority_byid(str(sender.id))
    vall3 = valid_superress_byid1(str(sender.id))
    vall4 = valid_ress_byid1(str(sender.id))
    vall5 = valid_priority_byid1(str(sender.id))

    """if val4 == "true" or val5 == "true" or val6 == "true":
        inline.append([
            Button.inline(" PPOB ", b"ppob"),
            Button.inline(" Topup ", b"topup")
        ])"""
    """if val == "true" or val1 == "true" or val2 == "true" or val3 == "true":
        inline.append([
            #Button.inline(" History ", b"infohs"),
            #Button.inline(" Topup ", b"topup1")
            #Button.inline(" PPOB", b"ppob")
        ])"""
    """if vall == "true" or vall1 == "true" or vall2 == "true" or vall3 == "true" or vall4 == "true" or vall5 == "true":
        inline.append([
            Button.inline(" Tools Berguna", b"toolsuser")
        ]) """
    """if validations[0] == "true" or str(sender.id) == "1316596937":
        inline.append([
            Button.inline(" Admin ", b"admin"),
            Button.inline(" Admin (Cadangan) ", b"user1")
        ])"""

    # 🧹 Hapus semua session user biar ga numpuk
    deleted = 0
    for key in list(user_sessions.keys()):
        if str(key).startswith(str(user_id)):  # aman kalau campuran int/str
            del user_sessions[key]
            deleted += 1

    if deleted > 0:
        logger.info(f"[SESSION] {deleted} session milik user {user_id} berhasil dihapus")
    else:
        logger.info(f"[SESSION] Tidak ada session yang dihapus untuk user {user_id}")

    generate_api = await get_api_generate(sender.id)

    user_data = get_api_credentials(sender.id)
    payload = {
        "action": "cek_saldo",
        "id_telegram": str(sender.id),
        "password": user_data['password']
    }

    try:
        result = await ngundang_api(API_TOOLS, payload)
        print(result)
    except Exception as e:
        await event.respond(f"❌ Gagal cek saldo: {e}")
        return

    data = result.get("data", {})
    role = data.get("role")
    saldo = int(data.get("saldo", 0))
    
    if not username:
        await event.respond(
            "⚠️ Anda belum mengatur username Telegram.\n\n"
            "Silakan pergi ke *Pengaturan Telegram* dan buat username terlebih dahulu agar bisa menggunakan bot ini."
        )
        return

    if any(validations):    
        msg = f"""
╭───────────────────╮
│           🤖 HIDE PULSA 🤖       
├───────────────────┤
│ 📝 {"User":<12} : {full_name}       
│ 🪪 {"Id-Tele":<10}  : {telegram_id}   
│ 💰 {"Saldo":<9}   : Rp: {saldo:,}     
│ 🎖️ {"Role":<9}    : {role}         
│
│ ⏰ {"Uptime":<8}  : {uptime}      
├───────────────────┤
│ 💰 Harga sewaktu-waktu bisa berubah tanpa
│    pemberitahuan
╰───────────────────╯
"""

        if isinstance(event, events.NewMessage.Event):
            msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
            user_messages[event.sender_id] = msg  # Simpan ID pesan
            asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
        elif isinstance(event, events.CallbackQuery.Event):
            await event.edit(msg, buttons=inline)
    else:
        try:
            await event.answer(monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"), alert=True)
        except telethon.errors.QueryIdInvalidError:
            await event.reply(monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"))