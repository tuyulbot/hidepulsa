from hidebot import *
from hidebot.menu.menu import *

@bot.on(events.CallbackQuery(pattern=b'cek_kuota\|(.*)'))
async def cek_kuota_handler(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, mode = event.data.decode().split("|", 1)  # cekkuota / cekpulsa / cekdompul

    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    # Minta nomor
    msg = await event.respond(
        "📱 Masukkan nomor HP yang ingin dicek (0877 / 62877, pisahkan baris baru untuk banyak nomor):",
        buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_messages[user_id] = msg

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
                    return

                # kalau user kirim nomor
                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_list = [n.strip() for n in nomor_event.text.splitlines() if n.strip()]

        except asyncio.TimeoutError:
            return await event.respond("⌛ Waktu habis.", buttons=[[Button.inline("🔙 MENU", b"menu")]])

    msg1 = await event.respond(f"🔄 Memproses pengecekan nomor...")

    user_data = get_api_credentials(user_id)

    for nomor in nomor_list:
        payload = {
            "action": "cek_dompul" if mode == "cekdompul" else "cek_kuota",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor
        }

        try:
            res = await ngundang_api(API_TOOLS, payload)
        except Exception as e:
            error = await event.respond(f"❌ Gagal cek {nomor}: {e}")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            continue

        if res.get("status") != "success":
            error = await event.respond(f"❌ Nomor {nomor} gagal dicek.\n```json\n{json.dumps(res, indent=2)}```")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            continue

        # ===================== CEK PULSA ===================== #
        if mode == "cekpulsa":
            data = res.get("data", {})
            expired = data.get("balance", {}).get("expired", "-")
            tipe = data.get("sub_type", "-")
            pulsa = data.get("balance", {}).get("pulsa", 0)

            pesan = (
                f"📒 Nomor   : {data.get('nomor')}\n"
                f"📡 Tipe    : {tipe}\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"📅 Tenggang: {expired}\n"
                "═══════════════════════"
            )

        # ===================== CEK KUOTA ===================== #
        elif mode == "cekkuota":
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

            for paket in kuota_list:
                total_semua = 0
                pesan += f"📦 {paket['package_name']}\n"
                pesan += f"📅 Expired : {paket['expired_at']}\n"

                for b in paket.get("benefits", []):
                    total_semua += b.get("remaining_gb", 0)
                    nama = b.get("name", "-")
                    info = b.get("information", "")
                    total = b.get("total_gb", 0)
                    sisa = b.get("remaining_gb", 0)

                    def format_gb(val):
                        return f"{val*1000:.0f} MB" if val < 1 else f"{val:.2f} GB"

                    pesan += f"🏷️ {nama} {info} : {format_gb(sisa)} / {format_gb(total)}\n"

                pesan += f"\n🧮 Total Semua : {total_semua:.2f} GB\n"
                pesan += "═══════════════════════\n"

        # ===================== CEK DOMPUL ===================== #
        # ===================== CEK DOMPUL ===================== #
        elif mode == "cekdompul":
            # Mengambil data utama dari nested JSON (data -> data -> data)
            raw_data = res.get("data", {}).get("data", {})
            
            subs = raw_data.get("subs_info", {})
            pkg_info = raw_data.get("package_info", {})
            volte = subs.get("volte", {})

            # Logika VoLTE
            vt_status = "Aktif" if volte.get("simcard") and volte.get("area") else "Tidak Aktif"
            
            # Hitung Total GB Terlebih Dahulu agar bisa ditaruh di atas
            packages = pkg_info.get("packages", [])
            total_gb = 0.0
            detail_paket = ""

            for pkg in packages:
                p_name = pkg.get("name", "-")
                p_exp = pkg.get("expiry", "-")
                
                detail_paket += f"📦 {p_name}\n"
                detail_paket += f"   📅 Exp: {p_exp}\n"
                
                for q in pkg.get("quotas", []):
                    q_name = q.get("name", "-")
                    q_total = q.get("total", "-")
                    q_remain = q.get("remaining", "-")
                    
                    detail_paket += f"   ├ 🌐 {q_name}: {q_remain} / {q_total}\n"
                    
                    # Hitung Estimasi Total (Hanya jika satuan GB)
                    if "GB" in q_remain:
                        try:
                            val = q_remain.replace("GB", "").strip()
                            total_gb += float(val)
                        except: pass
                detail_paket += "\n"

            # Susun Pesan (Total Estimasi diletakkan di atas)
            pesan = (
                f"📒 Nomor    : {subs.get('msisdn', '-')}\n"
                f"📶 Status   : {subs.get('net_type', '-')}\n"
                f"📡 VoLTE    : {vt_status}\n"
                f"🆔 Operator : {subs.get('operator', '-')}\n"
                f"📜 Verified : {subs.get('id_verified', '-')}\n"
                f"⏳ Umur     : {subs.get('tenure', '-')}\n"
                f"📅 Aktif    : {subs.get('exp_date', '-')}\n"
                f"⏳ Tenggang : {subs.get('grace_until', '-')}\n"
                f"═══════════════════════\n"
                f"🧮 Total Estimasi: {total_gb:.2f} GB\n"
                f"═══════════════════════\n\n"
                f"{detail_paket}"
                f"═══════════════════════"
            )

        await event.respond(pesan)
        await asyncio.sleep(5)

    asyncio.create_task(auto_delete_multi(user_id, 10, nomor_event.message, msg, msg1))
