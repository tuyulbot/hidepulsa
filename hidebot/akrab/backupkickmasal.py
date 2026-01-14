from hidebot import *
import asyncio, time, secrets, logging, re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ====== KONFIG OPSIONAL ======
SLOT_DELAY_SEC       = 10   # jeda antar slot
NUMBER_DELAY_SEC     = 3    # jeda antar nomor (beri napas API)
MAX_NUMBERS          = 20   # batasi banyaknya nomor sekali input
NORMALIZE_08_TO_62   = True # normalisasi 08xx -> 62xx

@bot.on(events.CallbackQuery(pattern=b'kickmasal'))
async def kickmasal_slot(event):
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
        sid = f"kickmasal:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [msg],
            "created_at": time.time()
        }
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Session awal
    sid = f"kickmasal:{secrets.token_hex(2)}"
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

    # ==============
    # Conversation
    # ==============
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

        found_msg = await event.respond(f"🔄 Ditemukan {len(nomor_list)} nomor. Menyiapkan proses…")
        user_sessions[user_id][sid]["messages"].append(found_msg)

        # ====== UTIL TAMPIL INFO SLOT (panel garis, bukan tabel) ======
        async def show_info_slot(nomor_admin: str, expired_val: str, slot_list: list[dict]):
            lines = [
                "╭──────────────────────────────────────────────╮",
                "                Info Slot Akrab               ",
                "╰──────────────────────────────────────────────╯",
                f"Expired Slot : {expired_val}",
            ]
            # urutkan pengelola (0) dulu, lalu slot 1..n
            for s in sorted(slot_list, key=lambda x: x.get("slot-ke", 0)):
                slot_ke = int(s.get("slot-ke", 0))
                kosong = not s.get("nomor")
                nomor = s.get("nomor") or "-"
                alias = s.get("alias") or "-"
                sisa_add = s.get("sisa-add", 0)
                status = "✅" if kosong else "❌"
                lines.append("────────────────────────────────────────────────")
                if slot_ke == 0:
                    lines.append(f"Pengelola: {status} | {nomor} | {alias} | {sisa_add}/3")
                else:
                    lines.append(f"Slot {slot_ke}: {status} | {nomor} | {alias} | {sisa_add}/3")
            lines.append("────────────────────────────────────────────────")
            lines.append("❌ = slot sudah dipakai | ✅ = slot belum dipakai")
            #await event.respond("\n".join(lines))  # tampilkan info slot PER NOMOR

        # ====== UTIL PROSES SATU NOMOR ======
        async def process_one_number(nomor_admin: str) -> str:
            # Ambil info slot
            payload_slot = {
                "action": "slot",
                "id_telegram": str(user_id),
                "password": user_data['password'],
                "nomor_hp": nomor_admin
            }
            try:
                result = await ngundang_api(AKRAB, payload_slot)
                slot_list = result["data"]["data_slot"]
                expired_local = result["data"].get("expired", "-")
            except Exception as e:
                return (
                    "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                    "      Rekap Hasil    \n"
                    "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                    f"├ 📞 No Adm  : {nomor_admin}\n"
                    f"└ ❌ Gagal ambil data slot: {e}\n"
                )

            # Info awal slot (panel bergaris)
            await show_info_slot(nomor_admin, expired_local, slot_list)

            # Target hanya slot anggota (>0). Pengelola (0) tidak di-kick.
            sorted_slots = sorted([s.get("slot-ke", 0) for s in slot_list if s.get("slot-ke", 0) > 0])

            if not sorted_slots:
                return (
                    "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                    "      Rekap Hasil    \n"
                    "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                    f"├ 📞 No Adm  : {nomor_admin}\n"
                    f"└ ℹ️ Tidak ada slot anggota yang terdeteksi.\n"
                )

            proses_msg = await event.respond(
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "        Mulai Proses\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                f"├ 📞 No Adm  : {nomor_admin}\n"
                f"├ 🎯 Target  : {', '.join(map(str, sorted_slots))}\n"
                f"└ 💬 Catatan : jeda {SLOT_DELAY_SEC} detik per slot\n"
            )
            user_sessions[user_id][sid]["messages"].append(proses_msg)

            hasil = []
            for idx, no_slot in enumerate(sorted_slots, start=1):
                step_msg = await event.respond(f"➡️ [{idx}/{len(sorted_slots)}] Kick Slot {no_slot}…")
                user_sessions[user_id][sid]["messages"].append(step_msg)

                kick_payload = {
                    "action": "kick",
                    "id_telegram": str(user_id),
                    "password": user_data['password'],
                    "nomor_hp": nomor_admin,
                    "nomor_slot": no_slot
                }
                try:
                    kick_resp = await ngundang_api(AKRAB, kick_payload)
                    data_root = kick_resp.get("data", {})
                    details = data_root.get("data", {})

                    nomor_slot = details.get("slot", no_slot)
                    nomor_anggota = details.get("nomor-anggota") or "-"
                    alias = details.get("alias") or "-"

                    hasil.append({"slot": nomor_slot, "anggota": nomor_anggota, "alias": alias, "status": "SUKSES"})
                except Exception as e:
                    hasil.append({"slot": no_slot, "anggota": "-", "alias": "-", "status": f"GAGAL: {e}"})

                if idx < len(sorted_slots):
                    await asyncio.sleep(SLOT_DELAY_SEC)

            # Rekap satu nomor
            out = ["╭━━━━━━━━━━━━━━━━━━━━╮", "        Rekap Hasil", "╰━━━━━━━━━━━━━━━━━━━━╯"]
            out.append(f"├ 📞 No Adm  : {nomor_admin}")
            for r in hasil:
                out.append(f"├ Slot {r['slot']}: {r['status']}")
                if r["status"] == "SUKSES":
                    out.append(f"│    ├ 👤 Anggota : `{r['anggota']}`")
                    out.append(f"│    └ 🏷️ Alias   : `{r['alias']}`")
            out.append("╰━━━━━━━━━━━━━━━━━━━━╯")
            return "\n".join(out)

        # ====== EKSEKUSI BERURUTAN PER NOMOR (rekap dikirim per nomor) ======
        progress_msgs = []
        for i, nadmin in enumerate(nomor_list, start=1):
            progress = await event.respond(
                f"🧩 Proses [{i}/{len(nomor_list)}] untuk **{nadmin}**…",
                parse_mode="markdown"
            )
            progress_msgs.append(progress)
            user_sessions[user_id][sid]["messages"].append(progress)

            # proses satu nomor -> dapat teks rekap
            panel_text = await process_one_number(nadmin)

            # kirim rekap PER NOMOR (biarkan tidak dihapus)
            await event.respond(panel_text, parse_mode="markdown")

            # jeda kecil antar nomor
            if i < len(nomor_list):
                await asyncio.sleep(NUMBER_DELAY_SEC)

        # Cek saldo akhir
        try:
            cek2 = await ngundang_api(API_TOOLS, payload_saldo)
            saldo_sisa = int(cek2.get("data", {}).get("saldo", 0))
        except Exception:
            saldo_sisa = saldo

        # Kirim saldo sisa sekali saja
        saldo_msg = await event.respond(f"💰 **Saldo Sisa:** Rp {saldo_sisa:,}", parse_mode="markdown")

        # TTL session & auto-delete: hapus pesan sementara saja
        # (prompt, input user, found_msg, dan seluruh progress msgs)
        asyncio.create_task(auto_delete_multi(
            user_id, 5, prompt, nomor_event.message, found_msg, *progress_msgs
        ))
        asyncio.create_task(expire_session(user_id, sid, 5))
