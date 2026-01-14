from hidebot import *
import aiohttp
import asyncio
import time

API_OTP = "http://127.0.0.1:5000/api/v1/minta-otp"
API_VERIF = "http://127.0.0.1:5000/api/v1/verif-otp"
MAX_OTP_ATTEMPTS = 5

@bot.on(events.CallbackQuery(pattern=b'login'))
async def login(event):
    user_id = event.sender_id
    chat = event.chat_id
    sender = await event.get_sender()

    user_data = get_api_credentials(sender.id)
    API_KEY = user_data.get("api_key")

    # Hapus pesan lama
    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        user_messages.pop(user_id, None)

    # Simpan session awal
    user_sessions.setdefault(user_id, {})["login"] = {"messages": [], "created_at": time.time()}

    # Minta input nomor HP
    prompt = await event.respond(
        "📲 Silakan masukan nomor HP untuk meminta OTP:",
        buttons=[[Button.inline("❌ Cancel", b"menu")]]
    )
    user_sessions[user_id]["login"]["messages"].append(prompt)

    # Ambil nomor HP
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
        error = await event.respond("⌛ Waktu habis, silakan coba lagi.")
        user_messages[user_id] = error
        asyncio.create_task(auto_delete_multi(user_id, 30, error))
        user_sessions[user_id]["login"]["messages"].append(error)
        asyncio.create_task(expire_session(user_id, "login", 30))
        return

    # Validasi nomor HP
    if not nomor_hp.isdigit():
        gagal_msg = await event.respond("❌ Nomor HP tidak valid. Batal.")
        user_messages[user_id] = gagal_msg
        asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
        user_sessions[user_id]["login"]["messages"].append(gagal_msg)
        asyncio.create_task(expire_session(user_id, "login", 30))
        return

    payload = {
        "id_telegram": str(user_id),
        "password": user_data['password'],
        "nomor_hp": nomor_hp
    }

    # Request OTP
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_OTP,
                headers={"Authorization": API_KEY, "Content-Type": "application/json"},
                json=payload
            ) as resp:
                if resp.status != 200:
                    error = await event.respond(f"❌ Gagal request OTP, status code: {resp.status}")
                    user_messages[user_id] = error
                    asyncio.create_task(auto_delete_multi(user_id, 30, error))
                    user_sessions[user_id]["login"]["messages"].append(error)
                    asyncio.create_task(expire_session(user_id, "login", 30))
                    return
                result = await resp.json()

        if result.get("status") != "success":
            error = await event.respond(f"❌ Gagal request OTP: {result.get('message')}")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id]["login"]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, "login", 30))
            return

        data_otp = result["data"]["data"]
        subscriber_id = data_otp.get("subscriber_id", "-")
        expires_in = data_otp.get("expires_in", 0)

        msg = await event.respond(
            f" 📒 Nomor: `{nomor_hp}`\n"
            f" 🆔 Subscriber ID: `{subscriber_id}`\n"
            f" ⌛ OTP berlaku selama: {expires_in} detik\n"
            f" ✅ OTP berhasil dikirim!",
            buttons=[[Button.inline("❌ Cancel", b"menu")]]
        )
        user_messages[user_id] = msg
        user_sessions[user_id]["login"]["messages"].append(msg)

    except Exception as e:
        error = await event.respond(f"❌ Terjadi error saat request OTP: {e}")
        user_messages[user_id] = error
        asyncio.create_task(auto_delete_multi(user_id, 30, error))
        user_sessions[user_id]["login"]["messages"].append(error)
        asyncio.create_task(expire_session(user_id, "login", 30))
        return

    # Loop input OTP maksimal 5 kali
    access_token = None
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
            error = await event.respond("⌛ OTP expired. Silakan request ulang OTP.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id]["login"]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, "login", 30))
            return

        payload = {
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor_hp,
            "kode_otp": kode_otp
        }

        # Verifikasi OTP
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_VERIF,
                    headers={"Authorization": API_KEY, "Content-Type": "application/json"},
                    json=payload
                ) as resp:
                    result = await resp.json()

            if result.get("status") == "success" and result.get("data", {}).get("status") == "success":
                access_token = result["data"]["data"]["access_token"]
                msgg = await event.respond(f"✅ Login berhasil!")
                user_messages[user_id] = msgg
                break
            else:
                await event.respond(f"❌ OTP salah. Percobaan ke-{attempt} dari {MAX_OTP_ATTEMPTS}.")
        except Exception as e:
            await event.respond(f"❌ Terjadi error saat verifikasi OTP: {e}")

    if not access_token:
        await event.respond("❌ Gagal login, OTP salah 5 kali. Silakan request ulang.")
        return

    # ----------------------
    # Lanjut ke cek kuota setelah login berhasil
    # ----------------------
    cek_payload = {
        "action": "cek_kuota",
        "id_telegram": str(user_id),
        "password": user_data['password'],
        "nomor_hp": nomor_hp
    }

    try:
        res = await ngundang_api(API_TOOLS, cek_payload)
        data = res.get("data", {})
        kuota_list = data.get("kuota", [])
        expired = data.get("balance", {}).get("expired", "-")
        tipe = data.get("sub_type", "-")
        pulsa = data.get("balance", {}).get("pulsa", 0)
        sub = data.get("subscriber_id", "-")

        pesan = (
            f"📒 Nomor   : {data.get('nomor')}\n"
            f"📡 Tipe    : {tipe}\n"
            f"🆔 Sub ID  : {sub}\n"
            f"📶 Status  : 4G\n"
            f"📜 Dukcapil: Sudah\n"
            f"💰 Pulsa   : Rp {pulsa:,}\n"
            f"📅 Tenggang: {expired}\n"
            "═══════════════════════\n"
        )
        await msgg.edit(pesan, buttons=[[Button.inline(" Menu ", b"menu")]])
    except Exception as e:
        error = await event.respond(f"❌ Gagal cek kuota: {e}")
        user_messages[user_id] = error
        asyncio.create_task(auto_delete_multi(user_id, 30, error))

    asyncio.create_task(auto_delete_multi(user_id, 5, prompt, nomor_event.message, msg, otp_event.message)) 
    asyncio.create_task(expire_session(user_id, "login", 5))


