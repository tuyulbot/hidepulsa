from hidebot import *

@bot.on(events.CallbackQuery(data=b'topupppp1'))
async def topup1_handler(event):
    logger.info(f"Command topup1 dipanggil oleh {event.sender_id}")
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

    await handle_topup1(event)  # pakai await biar langsung muncul respon

async def handle_topup1(event):
    status_orkut, status_qios, status_tripay = await asyncio.gather(
        cek_status_orkut(),
        cek_status_qiospay(),
        cek_status_tripay()
    )
    
    # Indikator Visual
    orkut_status_text = "🟢" if status_orkut == "ONLINE" else "🔴"
    orkut_display = f"🟢 {status_orkut}" if status_orkut == "ONLINE" else f"🔴 {status_orkut}"

    qios_status_text = "🟢" if status_qios == "ONLINE" else "🔴"
    qios_display = f"🟢 {status_qios}" if status_qios == "ONLINE" else f"🔴 {status_qios}"

    tripay_status_text = "🟢" if status_tripay == "ONLINE" else "🔴"
    tripay_display = f"🟢 {status_tripay}" if status_tripay == "ONLINE" else f"🔴 {status_tripay}"

    # Tombol menu
    inline = [
        [Button.inline(f"QiosPay ({qios_status_text})", b"toppp"),
         Button.inline(f"Orkut ({orkut_status_text})", b"topuporkut1")],
        [Button.inline(f"Tripay ({tripay_status_text})", b"topup1")],
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
│ 🔋 Status Topup:
│   📢 Orkut        : {orkut_display}
│   📢 QiosPay      : {qios_display}
│   📢 Tripay       : {tripay_display}
├───────────────────┤
│ Topup Menu:
│   - Tripay = Fee Tinggi
│   - QiosPay & Orkut = Fee Rendah
╰───────────────────╯
"""

    if isinstance(event, events.NewMessage.Event):
        msg = await event.client.send_file(event.chat_id, file="/etc/hidebot/xl.jpeg", caption=msg, buttons=inline)
        user_messages[event.sender_id] = msg  # Simpan ID pesan
        asyncio.create_task(auto_delete_multi(event.sender_id, 120, msg))  # Hapus otomatis dalam 30 detik
    elif isinstance(event, events.CallbackQuery.Event):
        await event.edit(msg, buttons=inline)