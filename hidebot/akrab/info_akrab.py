from hidebot import *
import asyncio
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@bot.on(events.CallbackQuery(pattern=b'akrabbekasan'))
async def akrabbekasan_slot(event):
    user_id = event.sender_id
    chat = event.chat_id

    # Hapus pesan lama
    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    await clear_session(user_id)

    # Ambil data login
    user_data = get_api_credentials(user_id)

    # Cek saldo awal
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
        msg = await event.respond(f"❌ Saldo Anda Rp {saldo:,}. Minimal Rp 10.000 untuk menggunakan fitur ini.")
        sid = f"akrabbekasan:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [],
            "created_at": time.time()
        }
        user_sessions[user_id][sid]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Simpan session
    sid = f"akrabbekasan:{secrets.token_hex(2)}"
    user_sessions.setdefault(user_id, {})[sid] = {
        "messages": [],
        "created_at": time.time()
    }

    # Minta input nomor (bisa lebih dari 1 nomor, pisah baris)
    prompt = await event.respond(
        "📲 Silakan kirim nomor pengelola (bisa lebih dari 1, pisah per baris):",
        buttons=[[Button.inline("❌ Cancel", b"menu")]]
    )
    user_sessions[user_id][sid]["messages"].append(prompt)

    async with bot.conversation(chat) as conv:
        try:
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
            # Pisahkan tiap nomor berdasarkan baris
            nomor_list = [n.strip() for n in nomor_event.text.splitlines() if n.strip().isdigit()]
            if not nomor_list:
                gagal_msg = await event.respond("❌ Tidak ada nomor valid. Batal.")
                user_messages[user_id] = gagal_msg
                asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
                user_sessions[user_id][sid]["messages"].append(gagal_msg)
                asyncio.create_task(expire_session(user_id, sid, 30))
                return

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

    # Pesan loading
    fetching_msg = await event.respond("🔄 Proses mengecek bekasan untuk semua nomor...")
    user_messages[user_id] = fetching_msg
    user_sessions[user_id][sid]["messages"].append(fetching_msg)

    asyncio.create_task(auto_delete_multi(user_id, 5, fetching_msg, nomor_event.message, prompt)) 
    asyncio.create_task(expire_session(user_id, sid, 5))

    # Proses tiap nomor satu per satu
    for nomor_hp in nomor_list:
        info_payload = {
            "action": "bekasan",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor_hp
        }

        try:
            resp = await ngundang_api(AKRAB, info_payload)
            data_root = resp.get("data", {})

            nomor_pengelola = data_root.get("nomor-pengelola", "-")
            jumlah_slot = data_root.get("jumlah_slot", 0)
            data_slot = data_root.get("data_slot", [])
            info_panel = data_root.get("info_saldo_panel", {})

            harga = info_panel.get("harga", 0)
            role = info_panel.get("role", "-")
            slots_terkena = info_panel.get("slots_terkena_pemotongan", [])
            catatan = info_panel.get("catatan", "-")

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

            slot_lines = []
            for slot in data_slot:
                slot_lines.append(
                    f"```Slot {slot.get('slot-ke')}\n"
                    f"    ├ Alias    : {slot.get('alias') or '-'}\n"
                    f"    ├ Nomor    : {slot.get('nomor') or '-'}\n"
                    f"    ├ SlotID   : {slot.get('slot-id') or '-'}\n"
                    f"    ├ SisaAdd  : {slot.get('sisa-add',0)}/{jumlah_slot}\n"
                    f"    ├ Kuber    : {slot.get('kuota-bersama',0)} GB (pakai {slot.get('pemakaian-kuota-bersama',0)} GB)\n"
                    f"    ├ Benefit  : {slot.get('benefit','-')}\n"
                    f"    └ Kuota    : {slot.get('total-kuota-benefit',0)} GB (sisa {slot.get('sisa-kuota-benefit',0)} GB)```"
                )

            msg_per_nomor = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "        Detail Sukses\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                f"├ 📞 No Adm: {nomor_pengelola}\n"
                f"├ 📊 Jumlah Slot: {jumlah_slot}\n"
                f"└ 🔢 Slot terkena pemotongan: {slots_terkena}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"├ 🎖️ Role: {role}\n"
                f"├ 💵 Jasa: Rp 150\n"
                f"├ 💰 Saldo Sisa: Rp {saldo_sisa:,}\n"
                f"└ 📝 Catatan: {catatan}\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                + "\n".join(slot_lines)
            )

            # Kirim per nomor
            await event.respond(msg_per_nomor)

            # Delay 5 detik sebelum nomor berikutnya
            await asyncio.sleep(5)

        except Exception as e:
            await event.respond(f"❌ Gagal cek nomor {nomor_hp}: {e}")

    # Bersihkan pesan loading
    try:
        await fetching_msg.delete()
    except: 
        pass
