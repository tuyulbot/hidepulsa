from hidebot import *
import asyncio, time, secrets, logging, re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Konfigurasi
NUMBER_DELAY_SEC    = 5     # jeda antar nomor
MAX_NUMBERS         = 50    # batas aman banyaknya nomor sekali input
NORMALIZE_08_TO_62  = True  # 08xxxx -> 62xxxx

@bot.on(events.CallbackQuery(pattern=b'listakrab'))
async def listakrab_slot(event):
    user_id = event.sender_id
    chat = event.chat_id

    # Hapus pesan lama user (kalau ada)
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

    # ✅ Cek saldo dulu (minimal 10.000)
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
        sid = f"listakrab:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [msg],
            "created_at": time.time()
        }
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Session awal
    sid = f"listakrab:{secrets.token_hex(2)}"
    user_sessions.setdefault(user_id, {})[sid] = {
        "messages": [],
        "created_at": time.time()
    }

    # Minta input nomor (bisa banyak baris)
    prompt = await event.respond(
        "📲 Silakan kirim **nomor pengelola** (bisa banyak, pisahkan baris/koma/spasi):",
        buttons=[[Button.inline("❌ Cancel", b"menu")]],
        parse_mode="markdown"
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
                if isinstance(result, events.CallbackQuery.Event):
                    await clear_session(user_id)
                    return
                nomor_event = result

            user_messages[user_id] = nomor_event.message
            raw_input = nomor_event.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        # ====== MULTI INPUT NOMOR ======
        def parse_numbers(text: str, normalize: bool = True) -> list[str]:
            parts = re.split(r"[,\s]+", text.strip())
            nums = []
            for n in parts:
                n = n.strip()
                if not n:
                    continue
                if not n.isdigit():
                    continue
                if normalize and n.startswith("0") and len(n) > 1:
                    n = "62" + n[1:]
                nums.append(n)
            return nums[:MAX_NUMBERS]

        nomor_list = parse_numbers(raw_input, NORMALIZE_08_TO_62)
        if not nomor_list:
            gagal_msg = await event.respond("❌ Input kosong / tidak ada nomor valid.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id][sid]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        found_msg = await event.respond(f"🔎 Ditemukan {len(nomor_list)} nomor. Mulai cek satu per satu…")
        user_sessions[user_id][sid]["messages"].append(found_msg)

        # ====== UTIL: Kirim panel Info Slot untuk satu nomor ======
        async def show_info_slot(nomor_admin: str):
            payload = {
                "action": "slot",
                "id_telegram": str(user_id),
                "password": user_data['password'],
                "nomor_hp": nomor_admin
            }
            try:
                res = await ngundang_api(AKRAB, payload)
                slot_list = res["data"]["data_slot"]
                expired_val = res["data"].get("expired", "-")
            except Exception as e:
                await event.respond(
                    "╭──────────────────────╮\n"
                    "        Info Slot      \n"
                    "╰──────────────────────╯\n"
                    f"📞 {nomor_admin}\n"
                    f"❌ Gagal ambil data slot: {e}"
                )
                return

            # Build teks panel (garis, bukan tabel)
            lines = [
                "╭──────────────────────╮",
                "        Info Slot      ",
                "╰──────────────────────╯",
                #f"📞 {nomor_admin}",
                f"Expired Slot : {expired_val}",
                "────────────────────────",
            ]

            # urut pengelola (0) → slot 1..n
            for s in sorted(slot_list, key=lambda x: x.get("slot-ke", 0)):
                slot_ke = s.get("slot-ke", 0)
                kosong = not s.get("nomor")
                nomor = s.get("nomor") or "-"
                alias = s.get("alias") or "-"
                sisa_add = s.get("sisa-add", 0)
                status = "✅" if kosong else "❌"

                if slot_ke == 0:
                    lines.append(f"Pengelola: {status} | {nomor} | {alias} | [{sisa_add}/3]")
                else:
                    lines.append(f"Slot {slot_ke}: {status} | {nomor} | {alias} | [{sisa_add}/3]")

            lines.append("────────────────────────")
            lines.append("❌ = slot sudah dipakai | ✅ = slot belum dipakai")

            await event.respond("\n".join(lines))

        # ====== PROSES BERURUTAN PER NOMOR DENGAN JEDA 5s ======
        for i, nadmin in enumerate(nomor_list, start=1):
            text = await event.respond(f"🧩 [{i}/{len(nomor_list)}] Mengecek **{nadmin}**…", parse_mode="markdown")
            user_sessions[user_id][sid]["messages"].append(text)
            await show_info_slot(nadmin)

            # jeda per nomor
            if i < len(nomor_list):
                await asyncio.sleep(NUMBER_DELAY_SEC)

        # TTL session & auto-delete beberapa pesan biar bersih
        asyncio.create_task(auto_delete_multi(
            user_id, 5, prompt, nomor_event.message, found_msg, text
        ))
        asyncio.create_task(expire_session(user_id, sid, 5))
