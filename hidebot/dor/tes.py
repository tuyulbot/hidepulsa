from hidebot import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@bot.on(events.NewMessage(pattern=r"(?:.akrab|/akrab)$"))
@bot.on(events.CallbackQuery(pattern=b'akrab'))
async def akrab_slot(event):
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
    await clear_session(user_id, "akrab")

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
        user_sessions.setdefault(user_id, {}).setdefault("akrab", {"messages": []})
        user_sessions[user_id]["akrab"]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, "akrab", 20))
        return

    # Simpan session awal
    user_sessions.setdefault(user_id, {})["akrab"] = {"messages": [], "created_at": time.time()}

    prompt = await event.respond("📲 Silakan kirim nomor HP :", buttons=[
            [Button.inline("❌ Cancel", b"akrab")]
        ]
    )
    user_sessions[user_id]["akrab"]["messages"].append(prompt)

    async with bot.conversation(chat) as conv:
        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(
                        events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)
                    ),
                    conv.wait_event(
                        events.CallbackQuery(pattern=b'akrab', func=lambda e: e.sender_id == user_id)
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
                    await clear_session(user_id, "akrab")
                    return

                # kalau user kirim nomor
                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_hp = nomor_event.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id]["akrab"]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, "akrab", 30))
            return

        if not nomor_hp.isdigit():
            gagal_msg = await event.respond("❌ Nomor HP tidak valid. Batal.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id]["akrab"]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, "akrab", 30))
            return

    fetching_msg = await event.respond("🔄 Proses mengambil data slot …")
    user_messages[user_id] = fetching_msg
    user_sessions[user_id]["akrab"]["messages"].append(fetching_msg)

    # ✅ Kalau saldo cukup, baru cek slot
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
        await event.respond(f"❌ Gagal ambil data slot: {e}")
        return

    status_lines, buttons, row = [], [], []
    for s in slot_list:
        kosong = not s.get("nomor")
        nomor = s.get("nomor") or "Kosong"
        alias = s.get("alias") or "-"
        sisa_add = s.get("sisa-add", 0)
        slot_num = s['slot-ke']

        if slot_num == 0:
            # 🔑 Slot 0 = Pengelola
            status = "✅ Kosong" if kosong else f"❌ {nomor}"
            status_lines.append(f"Pengelola: {status} | {alias} | {sisa_add}/3")

            emoji = "✅" if kosong else "❌"
            label = f"{emoji} Pengelola"
            row.append(Button.inline(label, data=f"slot:{slot_num}".encode()))
        else:
            # Slot biasa
            status = "✅ Kosong" if kosong else f"❌ {nomor}"
            status_lines.append(f"Slot {slot_num}: {status} | {alias} | {sisa_add}/3")

            emoji = "✅" if kosong else "❌"
            label = f"{emoji} Slot {slot_num}"
            row.append(Button.inline(label, data=f"slot:{slot_num}".encode()))

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([Button.inline("❌ Cancel", b"akrab")])

    info_text = "\n".join(status_lines)
    choose = await event.respond(
        f"**Status Slot Akrab**\n\n{info_text}\n\n❌ = slot sudah di pakai\n✅ = slot belom di pakai\n\nPilih slot yang akan dipakai ↓",
        buttons=buttons
    )
    try:
        done, pending = await asyncio.wait(
            [
                conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == user_id and e.chat_id == chat)),
                conv.wait_event(events.CallbackQuery(pattern=b'akrab', func=lambda e: e.sender_id == user_id))
            ],
            timeout=120,
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            result = task.result()

            if isinstance(result, events.CallbackQuery.Event):
                await clear_session(user_id, "akrab")

        no_slot = int(result.data.decode().split(":")[1])
        user_messages[user_id] = result.message
        await result.answer(f"✅ Slot {no_slot} dipilih")

    except asyncio.TimeoutError:
        error = await event.respond("⌛ Waktu habis.")
        user_messages[user_id] = error
        asyncio.create_task(auto_delete_multi(user_id, 30, error))
        user_sessions[user_id]["akrab"]["messages"].append(error)
        asyncio.create_task(expire_session(user_id, "akrab", 30))
        return

    await event.respond("✅ Slot berhasil dipilih. Silakan lanjut ke pembelian paket.")

    user_messages[user_id] = choose
    user_sessions[user_id]["akrab"]["messages"].append(choose)

    # TTL session 2 menit
    asyncio.create_task(auto_delete_multi(user_id, 30, choose, fetching_msg, nomor_event.message, prompt, ))
    asyncio.create_task(expire_session(user_id, "akrab", 120))

