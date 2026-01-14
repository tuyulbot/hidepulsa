from hidebot import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@bot.on(events.NewMessage(pattern=r"(?:.createcircle|/createcircle)$"))
@bot.on(events.CallbackQuery(pattern=b'createcircle'))
async def createcircle_slot(event):
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
        sid = f"createcircle:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [],
            "created_at": time.time()
        }
        user_sessions[user_id][sid]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Simpan session awal
    sid = f"createcircle:{secrets.token_hex(2)}"
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
        
        fetching_msg = await event.respond("🔄 Proses memvalidasi nomor anggota.")
        user_messages[user_id] = fetching_msg
        user_sessions[user_id][sid]["messages"].append(fetching_msg)

        payload = {
            "action": "validasi_nomor",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_admin": nomor_hp,
            "nomor_anggota": nomor_anggota
        }

        try:
            result = await ngundang_api(CIRCLE, payload)
        except Exception as e:
            return await event.respond(f"❌ Gagal validasi nomor anggota: {e}")
        
        try:
            result = await ngundang_api(CIRCLE, payload)
        except Exception as e:
            err = await event.respond(f"❌ Gagal validasi nomor anggota: {e}")
            user_messages[user_id] = err
            asyncio.create_task(auto_delete_multi(user_id, 30, err))
            user_sessions[user_id][sid]["messages"].append(err)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        # Struktur aman
        top_status = (result.get("status") or "").lower()
        top_code = str(result.get("code"))
        data = result.get("data") or {}
        inner_status = (data.get("status") or "").lower()
        inner_code = (str(data.get("code") or "")).strip()
        inner_msg = data.get("message") or ""
        inner_detail = data.get("detail") or ""

        # Pola sukses yang diharapkan
        is_ok = (
            top_status == "success"
            and top_code in ("0", "000")
            and inner_status == "success"
            and inner_code == "200-2001"
        )

        if not is_ok:
            # Anggap nomor sudah terdaftar / tidak eligible
            await fetching_msg.edit(
                "⚠️ Nomor anggota tidak eligible — kemungkinan sudah terdaftar/menjadi anggota Circle.\n"
                f"• Kode: {inner_code or '-'}\n"
                f"• Pesan: {inner_msg or '-'}\n"
                f"• Detail: {inner_detail or '-'}"
            )
            user_sessions[user_id][sid]["messages"].append(fetching_msg)
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
        

        prompt5 = await event.respond("📲 Silakan kirim nama group :")
        user_sessions[user_id][sid]["messages"].append(prompt5)
        user_messages[user_id] = prompt5

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
                nama_groupp = result

            user_messages[user_id] = nama_groupp.message
            nama_group = nama_groupp.text.strip()

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
            f"├ 🏷️ Nma Group : {nama_group}\n"
            f"└ 💰 Saldo : Rp {saldo:,}\n\n"
            "⏳ Sedang memproses tunggu sampe proses selesai"  
        )
        user_messages[user_id] = proses_msg
        user_sessions[user_id][sid]["messages"].append(proses_msg)

        create_payload = {
            "action": "create",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_admin": nomor_hp,
            "nomor_anggota": nomor_anggota,
            "nama_group": nama_group,
            "nama_admin": nama_admin,
            "nama_anggota": nama_anggota
        }

        try:
            create_resp = await ngundang_api(CIRCLE, create_payload)
            data_root = create_resp.get("data", {}) or {}
        except Exception as e:
            return await event.respond(f"❌ Gagal create group circel dan invit anggota: {e}")

        # ===== Validasi pola sukses =====
        top_status = (create_resp.get("status") or "").lower()
        top_code   = str(create_resp.get("code"))
        mid_status = (data_root.get("status") or "").lower()
        mid_msg    = data_root.get("message") or "-"

        srv        = data_root.get("data") or {}
        srv_code   = (srv.get("code") or "")
        srv_status = (srv.get("status") or "").upper()
        srv_data   = srv.get("data") or {}
        srv_rc     = (srv_data.get("response_code") or "")
        srv_msg    = (srv_data.get("message") or mid_msg)

        is_ok = (
            top_status == "success"
            and top_code in ("0", "000")
            and mid_status == "success"
            and srv_code == "000"
            and srv_status == "SUCCESS"
            and srv_rc == "200-00"
        )

        if not is_ok:
            err_text = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "         Detail Gagal\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                f"├ Top    : status=`{top_status}` | code=`{top_code}`\n"
                f"├ Mid    : status=`{mid_status}` | message=`{mid_msg}`\n"
                f"└ Server : code=`{srv_code or '-'}` | status=`{srv_status or '-'}` | response_code=`{srv_rc or '-'}`\n"
                f"   Message: `{srv_msg or '-'}`\n"
                "💡 Harapan sukses: `code=000 | status=SUCCESS | response_code=200-00`"
                "╰━━━━━━━━━━━━━━━━━━━━╯"
            )
            await event.respond(err_text, parse_mode="markdown")
            return

        # ===== Parsing detail sukses (sesuai key underscore) =====
        details      = data_root.get("details", {}) or {}
        info_panel   = data_root.get("info_saldo_panel", {}) or {}

        group_name      = details.get("group_name")      or "-"
        group_id        = details.get("group_id")        or "-"
        owner_name_out  = details.get("owner_name")      or (details.get("nama_admin") or "-")
        member_name_out = details.get("member_name")     or (details.get("nama_anggota") or "-")
        nomor_pengelola = details.get("nomor_pengelola") or create_payload.get("nomor_admin", "-")
        nomor_member_out= details.get("nomor_member")    or create_payload.get("nomor_anggota", "-")
        member_id_out   = details.get("member_id")       or "-"

        # saldo/jasa (harga mungkin tidak ada di response; aman-kan)
        saldo_akhir  = info_panel.get("saldo_tersedia")
        catatan_panel= info_panel.get("catatan") or "-"

        # ===== Render pesan final (tanpa waktu-eksekusi) =====
        final_create = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "       Detail Sukses\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n"
            f"├ 🏷️ Nama Group : `{group_name}`\n"
            f"├ 🧑‍💼 Owner     : `{owner_name_out}`\n"
            f"├ 👤 Member     : `{member_name_out}`\n"
            f"├ 📞 No Admin   : `{nomor_pengelola}`\n"
            f"└ 👤 No Anggota : `{nomor_member_out}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 🆔 Group ID   : `{group_id}`\n"
            f"└ 🆔 Member ID  : `{member_id_out}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"├ 💵 Jasa : Rp 500\n"
            f"└ 💰 Saldo Sisa : {('Rp ' + format(saldo_akhir, ',') if isinstance(saldo_akhir, int) else str(saldo_akhir or '-'))}\n"
            "   📝 Catatan : " + catatan_panel + "\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )
        await event.respond(final_create, parse_mode="markdown")

        # TTL session 2 menit
        asyncio.create_task(auto_delete_multi(user_id, 5, fetching_msg, nomor_event.message, prompt, prompt2, nomor_event1.message, prompt3, nama_adminn.message, prompt4, nama_anggotaa.message, proses_msg, prompt5, nama_groupp.message))
        asyncio.create_task(expire_session(user_id, sid, 5))
