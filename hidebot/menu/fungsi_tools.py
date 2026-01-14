from hidebot import *
from .fungsi_menu import *
import math, json, time

def rupiah(n):
    try:
        return f"Rp {int(n):,}".replace(",", ".")
    except Exception:
        return str(n)

def build_plp_text(items):
    lines = ["**Daftar Paket (total: {} item)**\n".format(len(items))]
    for it in items:
        idx = it.get("number", "-")
        name = it.get("name", "-")
        price = rupiah(it.get("price", 0))
        op = it.get("original_price", 0)
        original = rupiah(op) if op else "—"
        disc = it.get("discount", 0)
        validity = it.get("validity", "-")
        lines.append(
            f"**{idx}. {name}**\n"
            f"• 💵 Harga: {price}   | 🏷️ Diskon: {disc}%\n"
            f"• 🧾 Harga Normal: {original}   | ⏳ Masa Aktif: {validity}\n"
        )
    return "\n".join(lines).strip()

def split_for_telegram(text, limit=3900):
    chunks, cur = [], []
    cur_len = 0
    for line in text.splitlines(True):
        if cur_len + len(line) > limit:
            chunks.append("".join(cur))
            cur, cur_len = [line], len(line)
        else:
            cur.append(line); cur_len += len(line)
    if cur:
        chunks.append("".join(cur))
    return chunks

@bot.on(events.CallbackQuery(data=b'plp'))
async def plp(event):
    chat = event.chat_id
    sender = await event.get_sender()
    user_id = sender.id

    if valid_admin(str(user_id)) != "true":
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)
        return

    # pilih enterprise True/False
    await event.respond("**Pilih Mode Enterprise:**", buttons=[
        [Button.inline("✅ True", b"ent|true"), Button.inline("❌ False", b"ent|false")]
    ])
    async with bot.conversation(chat) as conv:
        cb = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == user_id and e.data.startswith(b'ent|')))
        payment = cb.data.decode("ascii").split("|", 1)[1]  # 'true' atau 'false'

    # input PLP
    await event.respond('`Input PLP:`')
    async with bot.conversation(chat) as conv:
        msg = await conv.wait_event(events.NewMessage(incoming=True, from_users=user_id))
        plp_code = msg.raw_text.strip()

    await event.respond("**Tunggu sedang proses mengambil data...**")

    # siapkan nomor & kredensial
    nomor_hp = '087777334689'   # TODO: kalau mau, ganti ambil dari input
    user_data = get_api_credentials(user_id)

    payload = {
        "action": "cek_plp",
        "id_telegram": str(user_id),
        "password": user_data['password'],
        "nomor_hp": nomor_hp,
        "is_enterprise": payment,   # 'true'/'false' → python script parse ke bool
        "plp": plp_code
    }

    try:
        resp = await ngundang_api(API_TOOLS, payload)

        if not isinstance(resp, dict):
            await event.respond(f"❌ Respon tidak dikenal:\n```{resp}```", parse_mode="markdown")
            return

        if resp.get("status") != "success":
            await event.respond(
                f"❌ Gagal cek PLP:\n```json\n{json.dumps(resp, ensure_ascii=False, indent=2)}\n```",
                parse_mode="markdown"
            )
            return

        items = resp.get("data") or []
        if not items:
            await event.respond("ℹ️ Tidak ada paket ditemukan untuk PLP ini.")
            return

        # bangun teks & auto-split tanpa pagination
        full_text = build_plp_text(items)
        parts = split_for_telegram(full_text, limit=3900)

        for i, chunk in enumerate(parts, start=1):
            suffix = f"\n\n_(bagian {i}/{len(parts)})_" if len(parts) > 1 else ""
            await event.respond(chunk + suffix, link_preview=False, parse_mode="markdown")

    except Exception as e:
        await event.respond(f"❌ Error: {e}")

@bot.on(events.CallbackQuery(data=b'otp'))
async def otp(event):
    # --- ambil info user dulu
    chat = event.chat_id
    sender = await event.get_sender()
    user_id = event.sender_id

    async def otp_(event):
        async with bot.conversation(chat) as conv:
            try:
                await event.respond("`Input Nomor :`")
                nomor = await conv.wait_event(events.NewMessage(
                    func=lambda e: e.sender_id == sender.id and e.chat_id == chat
                ))
                nomor_hp = nomor.raw_text
            except asyncio.exceptions.TimeoutError:
                await event.respond("Waktu input habis! Silakan coba lagi.",
                                    buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "menu")]])
                return

        await event.respond("**Tunggu sedang proses mengambil data...**")

        user_data = get_api_credentials(user_id)
        payload_saldo = {
            "action": "cek_otp",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor_hp
        }

        try:
            cek = await ngundang_api(API_TOOLS, payload_saldo)
            if cek.get("status") != "success":
                await event.respond(f"❌ Gagal cek OTP: {cek}")
                return

            data = cek.get("data", {})
            otp_messages = data.get("otp_messages", [])
            other_messages = data.get("other_messages", [])

            # Format OTP messages
            if otp_messages:
                pesan_otp = "**📩 Daftar OTP:**\n\n"
                for msg in otp_messages:
                    pesan_otp += f"🔑 {msg['full_message']}\n🕒 {msg['timestamp']}\n\n"
                await event.respond(pesan_otp.strip())
            else:
                await event.respond("Tidak ada pesan OTP ditemukan.")

            # Format other messages
            if other_messages:
                pesan_other = "**📩 Pesan Lain:**\n\n"
                for msg in other_messages:
                    pesan_other += f"💬 {msg['full_message']}\n🕒 {msg['timestamp']}\n\n"
                await event.respond(pesan_other.strip())

        except Exception as e:
            await event.respond(f"❌ Gagal cek saldo: {e}")
            return

    # cek izin dulu
    validation_result = await izin(sender.id, otp_, event)
    if validation_result == "true":
        await otp_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)


@bot.on(events.CallbackQuery(data=b'pdp'))
async def pdp(event):
    async def pdp_(event):    
        async with bot.conversation(chat) as conv:
            try:
                nomor_message = await event.respond('`Input Nomor :`')
                nomor = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                nomor_hp = nomor.raw_text
            except asyncio.exceptions.TimeoutError:
                await event.respond("Waktu input habis! Silakan coba lagi.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "menu")]])
                return
        # Jalankan perintah PHP dalam executor
        await event.respond("**Tunggu sedang proses mengambil data**")
        cmd = f'python3 -m dor.tools_admin.cek_list "{nomor_hp}"'
        loop = asyncio.get_running_loop()
        
        try:
            # Menggunakan lambda untuk memasukkan argumen 'shell=True'
            output = await loop.run_in_executor(None, lambda: subprocess.check_output(cmd, shell=True))
            output = output.decode("utf-8")
        except subprocess.CalledProcessError:
            await event.respond("**Perintah gagal**")
            return

        # Cek jika keluaran terlalu panjang dan bagi jika perlu
        if len(output) > 4000:
            parts = [output[i:i+4000] for i in range(0, len(output), 4000)]
            for part in parts:
                await event.respond(f"`{part}`")
        else:
            await event.respond(f"`{output}`")

        async with bot.conversation(chat) as conv:
            try:
                nomorp_message = await event.respond('`Input Nomor Paket :`')
                nomorr = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                nomor_paket = nomorr.raw_text
            except asyncio.exceptions.TimeoutError:
                await event.respond("Waktu input habis! Silakan coba lagi.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "menu")]])
                return
            
        await event.respond("**Tunggu sedang proses mengambil data**")
        cmd = f'python3 -m dor.tools_admin.cek_pdp "{nomor_hp}" "{nomor_paket}"'
        loop = asyncio.get_running_loop()
        
        try:
            # Menggunakan lambda untuk memasukkan argumen 'shell=True'
            output = await loop.run_in_executor(None, lambda: subprocess.check_output(cmd, shell=True))
            output = output.decode("utf-8")
        except subprocess.CalledProcessError:
            await event.respond("**Perintah gagal**")
            return

        # Cek jika keluaran terlalu panjang dan bagi jika perlu
        if len(output) > 4000:
            parts = [output[i:i+4000] for i in range(0, len(output), 4000)]
            for part in parts:
                await event.respond(f"`{part}`")
        else:
            await event.respond(f"`{output}`")
        

    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true":
        await pdp_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

@bot.on(events.CallbackQuery(data=b'unreg'))
async def unreg(event):
    async def unreg_(event):    
        async with bot.conversation(chat) as conv:
            try:
                nomor_message = await event.respond('`Input Nomor :`')
                nomor = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                nomor_hp = nomor.raw_text
            except asyncio.exceptions.TimeoutError:
                await event.respond("Waktu input habis! Silakan coba lagi.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "menu")]])
                return
        # Jalankan perintah PHP dalam executor
        await event.respond("**Tunggu sedang proses mengambil data**")
        cmd = f'python3 -m dor.tools_admin.unreg_list "{nomor_hp}"'
        loop = asyncio.get_running_loop()
        
        try:
            # Menggunakan lambda untuk memasukkan argumen 'shell=True'
            output = await loop.run_in_executor(None, lambda: subprocess.check_output(cmd, shell=True))
            output = output.decode("utf-8")
        except subprocess.CalledProcessError:
            await event.respond("**Perintah gagal**")
            return

        # Cek jika keluaran terlalu panjang dan bagi jika perlu
        if len(output) > 4000:
            parts = [output[i:i+4000] for i in range(0, len(output), 4000)]
            for part in parts:
                await event.respond(f"`{part}`")
        else:
            await event.respond(f"`{output}`")

        async with bot.conversation(chat) as conv:
            try:
                nomorp_message = await event.respond('`Input Nomor Paket (pisahkan dengan koma untuk memilih beberapa kuota) :`')
                nomorr = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                nomor_paket = nomorr.raw_text
            except asyncio.exceptions.TimeoutError:
                await event.respond("Waktu input habis! Silakan coba lagi.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "menu")]])
                return
            
        await event.respond("**Tunggu sedang proses menghapus paket**")
        cmd = f'python3 -m dor.tools_admin.unreg "{nomor_hp}" "{nomor_paket}"'
        loop = asyncio.get_running_loop()
        
        try:
            # Menggunakan lambda untuk memasukkan argumen 'shell=True'
            output = await loop.run_in_executor(None, lambda: subprocess.check_output(cmd, shell=True))
            output = output.decode("utf-8")
        except subprocess.CalledProcessError:
            await event.respond("**Perintah gagal**")
            return

        # Cek jika keluaran terlalu panjang dan bagi jika perlu
        if len(output) > 4000:
            parts = [output[i:i+4000] for i in range(0, len(output), 4000)]
            for part in parts:
                await event.respond(f"`{part}`")
        else:
            await event.respond(f"`{output}`")
        

    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()
    validation_result = await izin(sender.id, unreg_, event)
    if validation_result == "true":
        await unreg_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)