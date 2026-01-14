from hidebot import *

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@bot.on(events.NewMessage(pattern=r"(?:.ceknomortt|/ceknomortt)$"))
@bot.on(events.CallbackQuery(pattern=b'ceknomortt'))
async def ceknomortt_slot(event):
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
        sid = f"ceknomortt:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [],
            "created_at": time.time()
        }
        user_sessions[user_id][sid]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Simpan session awal
    sid = f"ceknomortt:{secrets.token_hex(2)}"
    user_sessions.setdefault(user_id, {})[sid] = {
        "messages": [],
        "created_at": time.time()
    }

    prompt = await event.respond("📲 Silakan kirim nomor hp :", buttons=[
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

        fetching_msg = await event.respond("🔄 Proses mengecek...")
        user_messages[user_id] = fetching_msg
        user_sessions[user_id][sid]["messages"].append(fetching_msg)

        payload = {
            "action": "cek_tt",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor_hp,
            "is_enterprise": "False"
        }

        try:
            result = await ngundang_api(API_TOOLS, payload)
        except Exception as e:
            err = await event.respond(f"❌ Gagal ambil data: {e}")
            user_messages[user_id] = err
            asyncio.create_task(auto_delete_multi(user_id, 30, err))
            user_sessions[user_id][sid]["messages"].append(err)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        try:
            await fetching_msg.delete()
        except:
            pass

        status_api = str(result.get("status", "")).lower()
        data_list = result.get("data") or []

        if status_api != "success" or not isinstance(data_list, list) or not data_list:
            gagal_msg = await event.respond("❌ Data tidak ditemukan / format tidak valid.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id][sid]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        # === HANYA AMBIL BASIC validity == "" ===
        basic_kosong = None
        for item in data_list:
            try:
                if str(item.get("name", "")).strip().lower() == "basic" and str(item.get("validity", "")).strip() == "":
                    basic_kosong = item
                    break
            except Exception:
                continue

        bisa_beli = False
        harga_basic = None
        harga_paket_tiktok = None
        nama_paket = None
        note_exec = []

        if basic_kosong:
            harga_basic = int(basic_kosong.get("price", 0))

            # mapping harga Basic validity kosong → TikTok price
            if harga_basic == 33000:
                bisa_beli = True
                harga_paket_tiktok = 30000
                nama_paket = "TikTok 30K"
                """note_exec.append(
                    f"Basic validity kosong Rp {harga_basic:,} → BISA BELI paket {nama_paket} (Rp {harga_paket_tiktok:,}) ✅"
                )"""
            else:
                harga_basic == 50000
                bisa_beli = True
                harga_paket_tiktok = 50000
                nama_paket = "TikTok 50K"
                """note_exec.append(
                    f"Basic validity kosong Rp {harga_basic:,} → BISA BELI paket {nama_paket} (Rp {harga_paket_tiktok:,}) ✅"
                )"""
        else:
            note_exec.append("Basic validity kosong tidak ditemukan pada respon API.")

        saldo_sisa = saldo
        nomor_pengelola = nomor_hp

        note_text = "\n".join(note_exec)
        if bisa_beli:
            note_text += f"\n\n✅ BISA BELI {nama_paket} dengan harga Rp {harga_paket_tiktok:,}."
        else:
            note_text += "\n\n⛔ Tidak memenuhi syarat beli paket."

        final_add = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "         Detail Cek\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n"
            f"├ 📞 Nomor : `{nomor_pengelola}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 Note : {note_text}\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )

        await event.respond(final_add, parse_mode="markdown")

        if bisa_beli:
            btn = await event.respond(
                f"Lanjutkan pembelian {nama_paket}?",
                buttons=[
                    [Button.inline(f"🛒 Beli {nama_paket}", b"methodbuylegal|Apps")],
                    [Button.inline("❌ Batal", b"menu")]
                ],
            )
            user_sessions[user_id][sid]["messages"].append(btn)

        # TTL session 2 menit
        asyncio.create_task(auto_delete_multi(user_id, 5, fetching_msg, nomor_event.message, prompt))
        asyncio.create_task(expire_session(user_id, sid, 5))


        