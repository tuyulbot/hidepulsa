from hidebot import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@bot.on(events.NewMessage(pattern=r"(?:.akrabadd|/akrabadd)$"))
@bot.on(events.CallbackQuery(pattern=b'akrabadd'))
async def akrabadd_slot(event):
    user_id = event.sender_id
    chat = event.chat_id

    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    # 🧹 Bersihkan session lama kalau ada
    await clear_session(user_id)

    # 🔑 Ambil data login user
    user_data = get_api_credentials(user_id)

    # ✅ Cek saldo dulu
    payload_saldo = {
        "action": "cek_saldo",
        "id_telegram": str(user_id),
        "password": user_data['password']
    }
    try:
        cek = await ngundang_api(API_TOOLS, payload_saldo)
        saldo = int(cek.get("data", {}).get("saldo", 0))
    except Exception as e:
        await event.respond(f"❌ Gagal cek saldo: {e}")
        return

    if saldo < 10000:
        msg = await event.respond(
            f"❌ Saldo Anda Rp {saldo:,}. Minimal saldo Rp 10.000 untuk menggunakan fitur ini."
        )
        sid = f"akrabadd:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [],
            "created_at": time.time()
        }
        user_sessions[user_id][sid]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Simpan session awal
    sid = f"akrabadd:{secrets.token_hex(2)}"
    user_sessions.setdefault(user_id, {})[sid] = {
        "messages": [],
        "created_at": time.time()
    }

    prompt = await event.respond("📲 Silakan kirim nomor pengelola :", buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_sessions[user_id][sid]["messages"].append(prompt)

    async with bot.conversation(chat) as conv:
        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(
                        events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)
                    ),
                    conv.wait_event(
                        events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id)
                    )
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                # kalau user tekan Cancel langsung return ke handler menu
                if isinstance(result, events.CallbackQuery.Event):
                    #await handle_menuilegal(result)  # tampilkan menu
                    await clear_session(user_id)
                    return

                # kalau user kirim nomor
                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_hp = nomor_event.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        if not nomor_hp.isdigit():
            gagal_msg = await event.respond("❌ Nomor HP tidak valid. Batal.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id][sid]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        fetching_msg = await event.respond("🔄 Proses mengambil data slot …")
        user_messages[user_id] = fetching_msg
        user_sessions[user_id][sid]["messages"].append(fetching_msg)

        payload = {
            "action": "slot",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor_hp
        }

        try:
            result = await ngundang_api(AKRAB, payload)
            slot_list = result["data"]["data_slot"]
        except Exception as e:
            return await event.respond(f"❌ Gagal ambil data slot: {e}")

        expired = result["data"].get("expired", "-")

        # 📋 Build status slot
        status_lines, buttons, row = [], [], []
        for s in slot_list:
            kosong = not s.get("nomor")
            nomor = s.get("nomor") or "Kosong"
            alias = s.get("alias") or "-"
            sisa_add = s.get("sisa-add", 0)
            slot_num = s['slot-ke']

            if slot_num == 0:
                status = "✅ Kosong" if kosong else f"❌ {nomor}"
                status_lines.append(f"Pengelola: {status} | {alias} | {sisa_add}/3")
                label = f"{'✅' if kosong else '❌'} Pengelola"
            else:
                status = "✅ Kosong" if kosong else f"❌ {nomor}"
                status_lines.append(f"Slot {slot_num}: {status} | {alias} | {sisa_add}/3")
                label = f"{'✅' if kosong else '❌'} Slot {slot_num}"

            row.append(Button.inline(label, data=f"slot:{slot_num}".encode()))
            if len(row) == 2:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        buttons.append([Button.inline("❌ Cancel", b"menu")])

        info_text = "\n".join(status_lines)
        choose = await event.respond(
            f"**Info Slot Akrab**\n\nExpired Slot = {expired}\n\n{info_text}\n\n❌ = slot sudah dipakai\n✅ = slot belum dipakai\n\nPilih slot yang akan dipakai ↓",
            buttons=buttons
        )
        user_messages[user_id] = choose
        user_sessions[user_id][sid]["messages"].append(choose)

        # ⏳ Tunggu pilihan slot
        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == user_id and e.chat_id == chat)),
                    conv.wait_event(events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id))
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                if isinstance(result, events.CallbackQuery.Event):
                    if result.data == b"menu":
                        await clear_session(user_id)
                        asyncio.create_task(auto_delete_multi(user_id, 0, fetching_msg, nomor_event.message, prompt))
                        return

                    no_slot = int(result.data.decode().split(":")[1])

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        user_messages[user_id] = choose
        user_sessions[user_id][sid]["messages"].append(choose)

        prompt2 = await event.respond("📲 Silakan kirim nomor anggota :")
        user_sessions[user_id][sid]["messages"].append(prompt2)
        user_messages[user_id] = prompt2
        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(
                        events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)
                    ),
                    conv.wait_event(
                        events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id)
                    )
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                # kalau user tekan Cancel langsung return ke handler menu
                if isinstance(result, events.CallbackQuery.Event):
                    if result.data == b"menu":
                        await clear_session(user_id)
                        return
                    return

                # kalau user kirim nomor
                nomor_event1 = result

            user_messages[user_id] = nomor_event1.message
            nomor_anggota = nomor_event1.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        if not nomor_anggota.isdigit():
            gagal_msg = await event.respond("❌ Nomor HP tidak valid. Batal.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id][sid]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return
        
        prompt3 = await event.respond("📲 Silakan kirim nama admin :")
        user_sessions[user_id][sid]["messages"].append(prompt3)
        user_messages[user_id] = prompt3

        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(
                        events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)
                    ),
                    conv.wait_event(
                        events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id)
                    )
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                # kalau user tekan Cancel langsung return ke handler menu
                if isinstance(result, events.CallbackQuery.Event):
                    if result.data == b"menu":
                        await clear_session(user_id)
                        return
                    return

                # kalau user kirim nomor
                nama_adminn = result

            user_messages[user_id] = nama_adminn.message
            nama_admin = nama_adminn.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        prompt4 = await event.respond("📲 Silakan kirim nama anggota :")
        user_sessions[user_id][sid]["messages"].append(prompt4)
        user_messages[user_id] = prompt4

        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(
                        events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)
                    ),
                    conv.wait_event(
                        events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id)
                    )
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                # kalau user tekan Cancel langsung return ke handler menu
                if isinstance(result, events.CallbackQuery.Event):
                    if result.data == b"menu":
                        await clear_session(user_id)
                        return
                    return

                # kalau user kirim nomor
                nama_anggotaa = result

            user_messages[user_id] = nama_anggotaa.message
            nama_anggota = nama_anggotaa.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        proses_msg = await event.respond(
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "         Detail Proses\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n"
            f"├ 📞 No Admin : {nomor_hp}\n"
            f"├ 👤 No Anggta : {nomor_anggota}\n"
            f"├ 🪪 Nma Admin : {nama_admin}\n"
            f"├ 🪪 Nma Anggota : {nama_anggota}\n"
            f"├ 💳 Slot : {no_slot}\n"
            f"└ 💰 Saldo : Rp {saldo:,}\n\n"
            "⏳ Sedang memproses tunggu sampe proses selesai"  
        )
        user_messages[user_id] = proses_msg
        user_sessions[user_id][sid]["messages"].append(proses_msg)

        add_payload = {
            "action": "add",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor_hp,
            "nomor_slot": no_slot,
            "nomor_anggota": nomor_anggota,
            "nama_anggota": nama_anggota,
            "nama_admin": nama_admin
        }

        try:
            add_resp = await ngundang_api(AKRAB, add_payload)
            data_root = add_resp.get("data", {})
        except Exception as e:
            return await event.respond(f"❌ Gagal add anggota akrab: {e}")

        details = data_root.get("details", {})
        waktu = data_root.get("waktu-eksekusi", {})
        info_panel = data_root.get("info_saldo_panel", {})

        nomor_pengelola = details.get("nomor-pengelola")
        nomor_slot = details.get("nomor-slot")
        nomor_anggota = details.get("nomor-anggota")
        nama_admin = details.get("nama-admin")
        nama_anggota = details.get("nama-anggota")
        # parsing waktu eksekusi
        time_exec = waktu.get("time")
        note_exec = waktu.get("note")
        # parsing info saldo
        harga = info_panel.get("harga") or 0

        payload_saldo1 = {
            "action": "cek_saldo",
            "id_telegram": str(user_id),
        "password": user_data['password']
        }

        try:
            cek = await ngundang_api(API_TOOLS, payload_saldo1)
            saldo_sisa = int(cek.get("data", {}).get("saldo", 0))
        except Exception as e:
            await event.respond(f"❌ Gagal cek saldo: {e}")
            return

        final_add = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "         Detail Sukses\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n"
            f"├ 📞 No Admin : `{nomor_pengelola}`\n"
            f"├ 👤 No Anggta : `{nomor_anggota}`\n"
            f"├ 🪪 Nma Admin : `{nama_admin}`\n"
            f"├ 🪪 Nma Anggota : `{nama_anggota}`\n"
            f"└ 💳 Slot : `{nomor_slot}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"├ ⏱ Waktu Eksekusi : {time_exec}\n"
            f"└ 📝 Note : {note_exec}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 💵 Jasa : Rp {harga:,}\n"
            f"└ 💰 Saldo Sisa : Rp {saldo_sisa:,}\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )
        await event.respond(final_add, parse_mode="markdown")

        # TTL session 2 menit
        asyncio.create_task(auto_delete_multi(user_id, 5, choose, fetching_msg, nomor_event.message, prompt, prompt2, nomor_event1.message, prompt3, nama_adminn.message, prompt4, nama_anggotaa.message, proses_msg))
        asyncio.create_task(expire_session(user_id, sid, 5))

