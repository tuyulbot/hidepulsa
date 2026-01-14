from hidebot import *
from .fungsi_menu import *
from .menu_indosat import *
from .menu_tri import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@bot.on(events.NewMessage(pattern=r"(?:.menu|/menu)$"))
@bot.on(events.CallbackQuery(data=b'menu'))
async def menu(event):
    logger.info(f"Command menu dipanggil oleh {event.sender_id}")
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

    await handle_menuilegal(event)  # pakai await biar langsung muncul respon

async def handle_menuilegal(event):
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
        inline = [[Button.inline(" Topup ", b"topppnewmember")]]
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
╰───────────────────╯
"""
        msg = msg_monospace
        await event.client.send_message(
            event.chat_id,
            msg,
            buttons=inline
        )
        return
    # Tombol menu 
    inline = [
        [Button.inline("MyXL", b"xl"),
        Button.inline("MyIM3", b"indosat")],
        [Button.inline("Dompul", b"dompull")],
        [Button.inline("Bima Tri", b"tri"),
        Button.inline("PPOB All Provider", b"ppob")]
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

    if val4 == "true" or val5 == "true" or val6 == "true":
        inline.append([
            #Button.inline(" PPOB ", b"ppob"),
            Button.inline(" Topup ", b"topupppp2")
        ])
    if val == "true" or val1 == "true" or val2 == "true" or val3 == "true":
        inline.append([
            #Button.inline(" History ", b"infohs"),
            Button.inline(" Topup ", b"topupppp1")
            #Button.inline(" PPOB", b"ppob")
        ])
    """if vall == "true" or vall1 == "true" or vall2 == "true" or vall3 == "true" or vall4 == "true" or vall5 == "true":
        inline.append([
            Button.inline(" Tools Berguna", b"toolsuser")
        ]) """
    if validations[0] == "true" or str(sender.id) == "1316596937":
        inline.append([
            Button.inline(" Admin ", b"admin"),
            Button.inline(" Admin (Cadangan) ", b"user1")
        ])

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

        if isinstance(event, events.NewMessage.Event):
            msg_menu = await event.client.send_file(
                event.chat_id, 
                file="/etc/hidebot/xl.jpeg", 
                caption=msg, 
                buttons=inline
            )
            user_messages[event.sender_id] = msg_menu
            asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg_menu))

        # 2. Jika Trigger dari Tombol (CallbackQuery)
        elif isinstance(event, events.CallbackQuery.Event):
            # Coba hapus pesan lama (tombol cancel/list paket yg diklik)
            try:
                await event.delete()
            except:
                pass # Abaikan jika sudah terhapus duluan oleh auto_delete

            # Kirim Menu Baru dengan Gambar (Konsisten)
            msg_menu = await event.client.send_file(
                event.chat_id, 
                file="/etc/hidebot/xl.jpeg", 
                caption=msg, 
                buttons=inline
            )
            
            # Simpan ID pesan agar fitur auto delete di masa depan bekerja
            user_messages[event.sender_id] = msg_menu
    else:
        try:
            await event.answer(monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"), alert=True)
        except telethon.errors.QueryIdInvalidError:
            await event.reply(monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"))

@bot.on(events.NewMessage(pattern=r"(?:.xl|/xl)$"))
@bot.on(events.CallbackQuery(data=b'xl'))
async def xl(event):
    logger.info(f"Command menu dipanggil oleh {event.sender_id}")
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

    await handle_menuxl(event)  # pakai await biar langsung muncul respon

async def handle_menuxl(event):
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
╰───────────────────╯
"""
        msg = msg_monospace
        await event.client.send_message(
            event.chat_id,
            msg,
            buttons=inline
        )
        return
    # Tombol menu 
    inline = [
        [Button.inline("Login Nomor", b"login")],
        [Button.inline("Akrab Manage", b"akrab"),
        Button.inline("Circle Manage", b"circle")],
        [Button.inline("Akrab Unlimited", b"methodbuylegal|Akrab Unlimited"),
        Button.inline("Cek Kuota", b"cek")],
        [Button.inline("Biz", b"methodbuylegal|Biz"),
        Button.inline("Edukasi", b"methodbuylegal|Edukasi"),
        Button.inline("Reguler", b"reguler")],
        [Button.inline("Combo Flex", b"combo_flex"),
        Button.inline("Combo Plus", b"combo_plus"),
        Button.inline("Combo Bundling", b"methodbuylegal|Combo Bundling")],
        [Button.inline("Masa Aktif", b"methodbuylegal|Masaaktif")],
        [Button.inline("TikTok Dll", b"tt"),
        Button.inline("Unli Turbo", b"unli_turbo")],
        [Button.inline("Paket Lainnya", b"methodbuylegal|Paket Lain")],
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

    if val4 == "true" or val5 == "true" or val6 == "true":
        inline.append([
            Button.inline(" History ", b"infohs1"),
            Button.inline(" Topup ", b"topup")
        ])
    if val == "true" or val1 == "true" or val2 == "true" or val3 == "true":
        inline.append([
            Button.inline(" History ", b"infohs"),
            Button.inline(" Topup ", b"topup1")
            #Button.inline(" PPOB", b"ppob")
        ])
    if vall == "true" or vall1 == "true" or vall2 == "true" or vall3 == "true" or vall4 == "true" or vall5 == "true":
        inline.append([
            Button.inline(" Tools Berguna", b"toolsuser")
        ]) 

    inline.append([
        Button.inline(" Back Menu ", b"menu")
    ])
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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
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

@bot.on(events.CallbackQuery(data=b'tt'))
async def tt(event):
    logger.info(f"Command tt dipanggil oleh {event.sender_id}")
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

    await handle_tt(event)  # pakai await biar langsung muncul respon

async def handle_tt(event):
    # Tombol menu
    inline = [
        [Button.inline("Cek Nomor Layak Buy TikTok", b"ceknomortt")],
        [Button.inline("TikTok & YouTube", b"methodbuylegal|Apps")],
        [Button.inline("Back Menu", b"menu")]
    ]

    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)

@bot.on(events.CallbackQuery(data=b'reguler'))
async def reguler(event):
    logger.info(f"Command reguler dipanggil oleh {event.sender_id}")
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

    await handle_reguler(event)  # pakai await biar langsung muncul respon

async def handle_reguler(event):
    # Tombol menu
    inline = [
        [Button.inline("BPA", b"methodbuylegal|BPA")],
        [Button.inline("Back Menu", b"menu")],
    ]

    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)

@bot.on(events.CallbackQuery(data=b'combo_flex'))
async def combo_flex(event):
    logger.info(f"Command combo_flex dipanggil oleh {event.sender_id}")
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

    await handle_combo_flex(event)  # pakai await biar langsung muncul respon

async def handle_combo_flex(event):
    # Tombol menu
    inline = [
        [Button.inline("Flex", b"methodbuylegal|Xtra Combo Flex"),
        Button.inline("Add on", b"methodspam|Bonus")],
        [Button.inline("Back Menu", b"menu")],
    ]

    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)

@bot.on(events.CallbackQuery(data=b'combo_plus'))
async def combo_plus(event):
    logger.info(f"Command combo_plus dipanggil oleh {event.sender_id}")
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

    await handle_combo_plus(event)  # pakai await biar langsung muncul respon

async def handle_combo_plus(event):
    # Tombol menu
    inline = [
        [Button.inline("Combo Plus", b"methodbuylegal|Xtra Combo Plus"),
        Button.inline("Add on", b"methodbuylegal|Addon")],
        [Button.inline("Back Menu", b"menu")],
    ]

    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)

@bot.on(events.CallbackQuery(data=b'combo_bundling'))
async def combo_bundling(event):
    logger.info(f"Command combo_bundling dipanggil oleh {event.sender_id}")
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

    await handle_combo_bundling(event)  # pakai await biar langsung muncul respon

async def handle_combo_bundling(event):
    # Tombol menu
    inline = [
        [Button.inline("Combo Mini", b"methodbuylegal|Xtra Combo Mini"),
        Button.inline("Add on", b"methodspam|Edukasi")],
        [Button.inline("📊 Proses Berjalan", b"jobs1")],
        [Button.inline("Back Menu", b"menu")],
    ]

    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)


@bot.on(events.CallbackQuery(data=b'cek'))
async def cek(event):
    logger.info(f"Command cek dipanggil oleh {event.sender_id}")
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

    await handle_cek(event)  # pakai await biar langsung muncul respon

async def handle_cek(event):
    # Tombol menu
    inline = [
        [Button.inline("Cek Kuota", b"cek_kuota|cekkuota"),
        Button.inline("Cek Pulsa", b"cek_kuota|cekpulsa")],
        [Button.inline("Cek Dompul", b"cek_kuota|cekdompul")],
        [Button.inline("Back Menu", b"menu")],
    ]

    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)


@bot.on(events.CallbackQuery(data=b'unli_turbo'))
async def unli_turbo(event):
    logger.info(f"Command unli_turbo dipanggil oleh {event.sender_id}")
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

    await handle_unli_turbo(event)  # pakai await biar langsung muncul respon

async def handle_unli_turbo(event):
    # Tombol menu
    inline = [
        [Button.inline("Add On", b"methodbuylegal|UTB"),
        Button.inline("Gandengan", b"methodbuylegal|Gandengan")],
        [Button.inline("Back Menu", b"menu")],
    ]

    # Info pengguna
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)

@bot.on(events.CallbackQuery(data=b'akrab'))
async def akrab(event):
    logger.info(f"Command akrab dipanggil oleh {event.sender_id}")
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

    await handle_akrab(event)  # pakai await biar langsung muncul respon

async def handle_akrab(event):
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

    user_data = get_api_credentials(sender.id)

    payload_help = {
        "action": "help",
        "id_telegram": str(sender.id),
        "password": user_data['password']
    }

    try:
        help_result = await ngundang_api(AKRAB, payload_help)
        help_data = help_result.get("data", [])
        # Buat dict mapping action -> fee
        action_fee = {item["action"]: item["fee"] for item in help_data}
    except Exception as e:
        action_fee = {}
        logger.warning(f"Gagal ambil fee action: {e}")

    # Ambil fee tiap action
    fee_add = action_fee.get("add", 0)
    fee_edit = action_fee.get("edit", 0)
    fee_bekasankick = action_fee.get("bekasankick", 0)
    fee_bekasan = action_fee.get("bekasan", 0)
    fee_list = action_fee.get("list", 0)
    # Tombol menu
    inline = [
        [Button.inline(f"Add Anggota ({fee_add:,})", b"akrabadd"),
        Button.inline(f"Edit kuber ({fee_edit:,})", b"akrabkuber")],
        [Button.inline("Kick Anggota (Free)", b"akrabkick")],
        [Button.inline(f"Info Akrab ({fee_bekasan:,})", b"akrabbekasan"),
        Button.inline(f"Bekasan Kick ({fee_bekasankick})", b"bekasankick")],
        [Button.inline(f"Add + Edit ({fee_add + fee_edit:,})", b"addedit"),
        Button.inline(f"Add + Kick ({fee_add})", b"addkick")],
        [Button.inline("Kick Masal (Free)", b"kickmasal"),
        Button.inline("Lihat Slot", b"listakrab")],
        [Button.inline("Back Menu", b"menu")],
    ]

    # 🧹 Hapus semua session user biar ga numpuk
    deleted = 0
    for key in list(user_sessions.keys()):
        if str(key).startswith(str(user_id)):  # aman kalau campuran int/str
            del user_sessions[key]
            deleted += 1
    #del user_messages[user_id]

    if deleted > 0:
        logger.info(f"[SESSION] {deleted} session milik user {user_id} berhasil dihapus")
    else:
        logger.info(f"[SESSION] Tidak ada session yang dihapus untuk user {user_id}")

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)

@bot.on(events.CallbackQuery(data=b'circle'))
async def circle(event):
    logger.info(f"Command circle dipanggil oleh {event.sender_id}")
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

    await handle_circle(event)  # pakai await biar langsung muncul respon

async def handle_circle(event):
    uptime = get_uptime()
    sender = await event.get_sender()
    user_id = event.sender_id
    telegram_id = sender.id
    first_name = sender.first_name
    last_name = sender.last_name if sender.last_name else ""
    full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
    username = sender.username if sender.username else None

    user_data = get_api_credentials(sender.id)

    payload_help = {
        "action": "help",
        "id_telegram": str(sender.id),
        "password": user_data['password']
    }

    try:
        help_result = await ngundang_api(CIRCLE, payload_help)
        help_data = help_result.get("data", [])
        # Buat dict mapping action -> fee
        action_fee = {item["action"]: item["fee"] for item in help_data}
    except Exception as e:
        action_fee = {}
        logger.warning(f"Gagal ambil fee action: {e}")

    # Ambil fee tiap action
    fee_create = action_fee.get("create", 0)
    fee_invite = action_fee.get("invite", 0)
    fee_bonus = action_fee.get("bonus", 0)
    # Tombol menu
    inline = [
        [Button.inline(f"Buat Group ({fee_create:,})", b"createcircle"),
        Button.inline(f"Invit Anggota ({fee_invite:,})", b"invitcircle")],
        [Button.inline(f"Klaim Bonus ({fee_bonus:,})", b"bonuscirclee")],
        [Button.inline(f"Kick Anggota (free)", b"kickcirclee"),
        Button.inline(f"Info Circle (free)", b"infocircle")],
        [Button.inline("Back Menu", b"menu")]
    ]

    # 🧹 Hapus semua session user biar ga numpuk
    deleted = 0
    for key in list(user_sessions.keys()):
        if str(key).startswith(str(user_id)):  # aman kalau campuran int/str
            del user_sessions[key]
            deleted += 1
    #del user_messages[user_id]

    if deleted > 0:
        logger.info(f"[SESSION] {deleted} session milik user {user_id} berhasil dihapus")
    else:
        logger.info(f"[SESSION] Tidak ada session yang dihapus untuk user {user_id}")

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
│ 🌐 OTP Mandiri 
│    Web : https://otp.hidepulsa.com
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)
