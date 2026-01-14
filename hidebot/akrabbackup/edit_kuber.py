from hidebot import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@bot.on(events.CallbackQuery(pattern=b'akrabkuber'))
async def akrabkuber_slot(event):
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
        user_sessions.setdefault(user_id, {}).setdefault("akrabedit", {"messages": []})
        user_sessions[user_id]["akrabedit"]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, "akrabedit", 20))
        return

    # Simpan session awal
    user_sessions.setdefault(user_id, {})["akrabedit"] = {"messages": [], "created_at": time.time()}

    prompt = await event.respond("📲 Silakan kirim nomor pengelola :", buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_sessions[user_id]["akrabedit"]["messages"].append(prompt)

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
            user_sessions[user_id]["akrabedit"]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, "akrabedit", 30))
            return

        if not nomor_hp.isdigit():
            gagal_msg = await event.respond("❌ Nomor HP tidak valid. Batal.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id]["akrabedit"]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, "akrabedit", 30))
            return

        fetching_msg = await event.respond("🔄 Proses mengambil data slot …")
        user_messages[user_id] = fetching_msg
        user_sessions[user_id]["akrabedit"]["messages"].append(fetching_msg)

        payload = {
            "action": "info",
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
            kuber = s.get("kuota-bersama", "-")

            if slot_num == 0:
                status = "✅ Kosong" if kosong else f"❌ {nomor}"
                status_lines.append(f"Pengelola: {status} | {alias} | {sisa_add}/3 | {kuber} GB")
                label = f"{'✅' if kosong else '❌'} Pengelola"
            else:
                status = "✅ Kosong" if kosong else f"❌ {nomor}"
                status_lines.append(f"Slot {slot_num}: {status} | {alias} | {sisa_add}/3 | {kuber} GB")
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
        user_sessions[user_id]["akrabedit"]["messages"].append(choose)

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
            user_sessions[user_id]["akrabedit"]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, "akrabedit", 30))
            return

        user_messages[user_id] = choose
        user_sessions[user_id]["akrabedit"]["messages"].append(choose)

        prompt2 = await event.respond("📲 Silakan kirim GB kuota bersama (20 = 20GB) :")
        user_sessions[user_id]["akrabedit"]["messages"].append(prompt2)
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
            total_kuber = nomor_event1.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id]["akrabedit"]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, "akrabedit", 30))
            return

        if not total_kuber.isdigit():
            gagal_msg = await event.respond("❌ Kuber bukan angka. Batal.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id]["akrabedit"]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, "akrabedit", 30))
            return

        proses_msg = await event.respond(
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "         Detail Proses\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n"
            f"├ 🎉 Kuber : {total_kuber}\n"
            f"├ 💳 Slot : {no_slot}\n"
            f"└ 💰 Saldo : Rp {saldo:,}\n\n"
            "⏳ Sedang memproses tunggu sampe proses selesai"  
        )
        user_messages[user_id] = proses_msg
        user_sessions[user_id]["akrabedit"]["messages"].append(proses_msg)

        edit_payload = {
            "action": "edit",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor_hp,
            "nomor_slot": no_slot,
            "input_gb": total_kuber
        }

        try:
            edit_resp = await ngundang_api(AKRAB, edit_payload)
            data_root = edit_resp.get("data", {})
        except Exception as e:
            return await event.respond(f"❌ Gagal add anggota akrab: {e}")

        details = data_root.get("data", {})
        info_panel = data_root.get("info_saldo_panel", {})

        # Parsing details
        nomor_pengelola = details.get("nomor-pengelola")
        nomor_slot = details.get("slot")
        original_alloc = details.get("original-allocation")
        new_alloc = details.get("new-allocation")

        # Parsing saldo panel
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

        final_edit = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "        Detail Sukses\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n"
            f"├ 📞 No Admin : {nomor_pengelola or '-'}\n"
            f"└ 💳 Slot : {nomor_slot or '-'}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 📦 Sebelum : {original_alloc or '-'}\n"
            f"└ 📦 Sesudah : {new_alloc or '-'}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 💵 Jasa : Rp 350\n"
            f"└ 💰 Saldo Sisa : Rp {saldo_sisa:,}\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )
        await event.respond(final_edit, parse_mode="markdown")

        # TTL session 2 menit
        asyncio.create_task(auto_delete_multi(user_id, 5, choose, fetching_msg, nomor_event.message, prompt, prompt2, nomor_event1.message, proses_msg))
        asyncio.create_task(expire_session(user_id, "akrabedit", 5))

