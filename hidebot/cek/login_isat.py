from hidebot import *

API_OTPP = "http://127.0.0.1:5000/api/login/isat_tri"
API_TOOLS_ISAT = "http://127.0.0.1:5000/api/tools/isat_tri"
MAX_OTP_ATTEMPTS = 5

@bot.on(events.CallbackQuery(pattern=b'isat_login'))
async def isat_login(event):
    user_id = event.sender_id
    chat = event.chat_id
    sender = await event.get_sender()
    print("DEBUG: isat_login TRIGGERED", user_id, time.time())

    user_data = get_api_credentials(sender.id)
    API_KEY = user_data.get("api_key")

    # ==========================
    # CLEANUP PESAN LAMA
    # ==========================
    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        user_messages.pop(user_id, None)

    # ==========================
    # BUAT SESSION
    # ==========================
    user_sessions.setdefault(user_id, {})["isat_login"] = {
        "messages": [],
        "created_at": time.time()
    }

    # ==========================
    # MINTA NOMOR HP
    # ==========================
    prompt = await event.respond(
        "📲 Silakan masukan nomor HP untuk meminta OTP:",
        buttons=[[Button.inline("❌ Cancel", b"menu")]]
    )
    user_sessions[user_id]["isat_login"]["messages"].append(prompt)

    try:
        async with bot.conversation(chat, timeout=150) as conv:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)),
                    conv.wait_event(events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id))
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                if isinstance(result, events.CallbackQuery.Event):
                    await clear_session(user_id)
                    return
                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_hp = nomor_event.text.strip()

    except asyncio.TimeoutError:
        return await send_err(event, user_id, "⌛ Waktu habis, silakan coba lagi.")

    # ==========================
    # VALIDASI NOMOR HP
    # ==========================
    if not nomor_hp.isdigit():
        return await send_err(event, user_id, "❌ Nomor HP tidak valid. Batal.")

    # ==========================
    # REQUEST OTP KE API SERVER
    # ==========================
    payload = {
        "action": "reqotp_isat",
        "id_telegram": str(user_id),
        "password": user_data['password'],
        "nomor_hp": nomor_hp
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_OTPP,
                headers={"Authorization": API_KEY, "Content-Type": "application/json"},
                json=payload
            ) as resp:

                LOG = f"🔍 DEBUG LOG RESPON API OTP:\nStatus: {resp.status}\n"
                result = await resp.json()
                LOG += f"Response JSON:\n```\n{result}\n```"

                # kirim log ke user (sebagai whisper)
                #await event.respond(LOG)

                # =============================
                # CEK STATUS UTAMA API
                # =============================
                if result.get("status") != "success":
                    return await send_err(
                        event, user_id,
                        f"❌ Gagal request OTP: {result.get('message')}"
                    )

                # =============================
                # CEK STATUS DI DALAM DATA
                # =============================
                data = result.get("data", {})
                if data.get("status") != "success":
                    return await send_err(
                        event, user_id,
                        f"❌ OTP gagal: {data.get('message')}"
                    )

                # Kalau sukses → lanjut
                msg = await event.respond(
                    f"📒 Nomor: `{nomor_hp}`\n"
                    f"⌛ OTP berlaku selama: 5 Menit\n\n"
                    f"mohon masukkan OTP yang telah dikirim ke nomor tersebut.",
                    buttons=[[Button.inline("❌ Cancel", b"menu")]]
                )

                user_messages[user_id] = msg
                user_sessions[user_id]["isat_login"]["messages"].append(msg)

    except Exception as e:
        return await send_err(event, user_id, f"❌ Error saat request OTP: {e}")

    access_token = None
    otp_event = None
    for attempt in range(1, MAX_OTP_ATTEMPTS + 1):
        otp_event = None
        try:
            async with bot.conversation(chat, timeout=320) as conv:
                done, pending = await asyncio.wait(
                    [
                        conv.wait_event(events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)),
                        conv.wait_event(events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id))
                    ],
                    timeout=300,
                    return_when=asyncio.FIRST_COMPLETED
                )

                for p in pending:
                    p.cancel()

                for task in done:
                    result = task.result()
                    if isinstance(result, events.CallbackQuery.Event):
                        await clear_session(user_id)
                        return
                    otp_event = result

                if not otp_event:
                    raise asyncio.TimeoutError()

                user_messages[user_id] = otp_event.message
                kode_otp = otp_event.text.strip()

        except asyncio.TimeoutError:
            return await send_err(event, user_id, "⌛ Waktu habis, silakan coba lagi.")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_OTPP,
                    headers={"Authorization": API_KEY, "Content-Type": "application/json"},
                    json={
                        "action": "validotp_isat",
                        "id_telegram": str(user_id),
                        "password": user_data['password'],
                        "nomor_hp": nomor_hp,
                        "otp": kode_otp
                    }
                ) as resp:
                    result = await resp.json()

            # OTP sukses
            if (
                result.get("status") == "success" and
                result.get("data", {}).get("status") == "success"
            ):
                # Ambil tokenid dari response
                access_token = result["data"]["data"]["data"]["tokenid"]

                msgg = await event.respond("✅ Login berhasil!")
                user_messages[user_id] = msgg
                break

            # OTP salah
            await event.respond(f"❌ OTP salah. Percobaan ke-{attempt} dari {MAX_OTP_ATTEMPTS}.")

        except Exception as e:
            await event.respond(f"❌ Error verifikasi OTP: {e}")

    if not access_token:
        await event.respond("❌ Gagal login, OTP salah 5 kali. Silakan request ulang.")
        return

    tools_payload = {
    "action": "cekkuota_isat",
    "id_telegram": str(user_id),
    "password": user_data['password'],
    "nomor_hp": nomor_hp,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_TOOLS_ISAT,
                headers={"Authorization": API_KEY, "Content-Type": "application/json"},
                json=tools_payload
            ) as resp:
                res = await resp.json()
        packdata = (
            res.get("data", {})
            .get("data", {})
            .get("packdata", {})
        )

        # Ambil data lain
        susbtype = packdata.get("substype", "-")
        cardtype = packdata.get("cardtype", "-")
        msisdn = packdata.get("msisdn", "-")
        tid = packdata.get("tid", "-")

        prepaidinfo = (
            res.get("data", {})
            .get("data", {})
            .get("prepaidinfo", {})
        )
        cardactivuntil = prepaidinfo.get("cardactiveuntil", "-")
        balance = prepaidinfo.get("balance", "-")
        graceperioduntil = prepaidinfo.get("graceperioduntil", "-")

        msg = await event.respond(
            f"📒 Nomor            : {msisdn}\n"
            f"💳 Tipe Kartu       : {cardtype}\n"
            f"🆔 TID              : {tid}\n"
            f"📡 Tipe             : {susbtype}\n"
            f"💰 Pulsa            : Rp {balance}\n"
            f"📅 Aktif Sampai     : {cardactivuntil}\n"
            f"⏳ Masa Tenggang    : {graceperioduntil}\n"
        )

        user_messages[user_id] = msg

    except Exception as e:
        await event.respond(f"❌ Gagal cek kuota setelah login: {e}")

    # ==========================
    # AUTO DELETE
    # ==========================
    asyncio.create_task(auto_delete_multi(user_id, 60, prompt, nomor_event.message, msg))
    asyncio.create_task(expire_session(user_id, "isat_login", 60))


# ====================================================
# FUNGSI ERROR HANDLER YANG SUDAH DIRAPIHKAN
# ====================================================
async def send_err(event, user_id, text):
    err = await event.respond(text)
    user_messages[user_id] = err
    asyncio.create_task(auto_delete_multi(user_id, 30, err))
    user_sessions[user_id]["isat_login"]["messages"].append(err)
    asyncio.create_task(expire_session(user_id, "isat_login", 30))
    return