from hidebot import *
from .fungsi_menu import *
import math

@bot.on(events.CallbackQuery(data=b'add_user'))
async def add_user(event):
    async def add_user_(event):
        async with bot.conversation(chat) as idtele:
            await event.respond('`Exit = back to menu \n\nMasukkan ID Telegram:`')
            idtele = await idtele.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            telegram_id = idtele.raw_text
            if telegram_id.lower() == "exit":
                await event.respond('exit', buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
                return
        async with bot.conversation(chat) as user:
            await event.respond('Masukkan username telegram:')
            user = await user.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            username = user.raw_text
        
        # Pemilihan role melalui tombol inline
        async with bot.conversation(chat) as role_add:
            await event.respond(f"ID: {telegram_id}\n Username: {username}. \n\nPilih role untuk user ini:", buttons=[
                [Button.inline(" Super Reseller ", "super_reseller"), Button.inline(" Reseller ", "reseller")],
                [Button.inline(" Member ", "member")]
            ])
            response = await role_add.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            selectedd_role = response.data.decode("ascii")
        
        # Panggil fungsi add_member untuk menambahkan pengguna dengan role yang dipilih
        success, message = add_member(username, telegram_id, selectedd_role)
        
        # Respon ke pengguna
        if success:
            msg = f"""
╭──────────────────────╮
│        ADD USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Saldo    : 0
│ Role     : {selectedd_role}
│ Status   : {message}
╰──────────────────────╯
"""
        else:
            msg = f"""
╭──────────────────────╮
│        ADD USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {selectedd_role}
│ Status   : {message}
╰──────────────────────╯
"""
        await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
    
    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()

    # Jika pengirim merupakan pengguna yang valid, panggil fungsi add_user_
    if valid_admin(str(sender.id)) == "true":
        await add_user_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

@bot.on(events.CallbackQuery(data=b'add_byid'))
async def add_byid(event):
    async def add_byid_(event):
        all_users = get_all_users()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
            return

        # Urutkan user
        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- KONFIGURASI PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            # Loop Navigasi & Pencarian
            while True:
                # Jika user sudah dipilih (dari pencarian), keluar loop
                if selected_user_id:
                    break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                # List User
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Saldo: {user['saldo']})", data=user['id_telegram'])])
                
                # Tombol Navigasi
                nav_buttons = []
                if current_page > 0:
                    nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                
                if current_page < total_pages - 1:
                    nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                
                buttons.append(nav_buttons)
                
                # --- TOMBOL PENCARIAN ---
                buttons.append([Button.inline("🔍 Cari by ID Telegram", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna untuk mendapatkan akses (Total: {total_users}):'
                
                if last_msg:
                    try:
                        await last_msg.edit(msg_text, buttons=buttons)
                    except:
                        last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                # Tunggu respon
                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                # Logika Tombol
                if data == "next_page":
                    current_page += 1
                elif data == "prev_page":
                    current_page -= 1
                elif data == "ignore":
                    await response.answer(f"Halaman {current_page + 1} dari {total_pages}")
                elif data == "admin":
                    await response.delete()
                    return
                elif data == "search_id":
                    # --- LOGIKA PENCARIAN ---
                    if last_msg: await last_msg.delete() 
                    prompt_search = await event.respond("Kirimkan ID Telegram user yang ingin dicari:")
                    
                    search_msg = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = search_msg.raw_text.strip()
                    
                    # Validasi apakah ID ada di all_users
                    user_found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    
                    await prompt_search.delete()
                    await search_msg.delete()
                    
                    if user_found:
                        selected_user_id = input_id
                        break 
                    else:
                        last_msg = await event.respond(f"❌ User dengan ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali ke List", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                        # Loop ulang
                
                else:
                    # Jika diklik user dari list
                    selected_user_id = data
                    break 

            # --- EKSEKUSI PERUBAHAN AKSES ---
            
            telegram_id = selected_user_id
            
            # Bersihkan menu list terakhir jika masih ada
            try:
                if last_msg: await last_msg.delete()
            except:
                pass

            # Ambil info user dan jalankan fungsi add_byidd
            username, idtele, role, saldo = get_user_info(telegram_id)
            success, message = add_byidd(username, telegram_id, role) 
            
            # Respon ke pengguna (Target)
            if success:
                msg = f"""
╭──────────────────────╮
│           ADD AKSES
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
                try:
                    await bot.send_message(int(telegram_id), msg)
                except:
                    pass # User memblokir bot
            else:
                msg = f"""
╭──────────────────────╮
│           ADD AKSES
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
            # Respon ke Admin
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
    
    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()

    # Validasi Admin
    if valid_admin(str(sender.id)) == "true":
        await add_byid_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

@bot.on(events.CallbackQuery(data=b'add_saldoo'))
async def add_saldoo(event):
    async def add_saldoo_(event):
        all_users = get_all_users()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
            return

        # Urutkan user berdasarkan username
        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- KONFIGURASI PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            # Loop Navigasi & Pencarian
            while True:
                # Jika user sudah dipilih (dari pencarian), keluar loop
                if selected_user_id:
                    break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                # List User
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Saldo: {user['saldo']})", data=user['id_telegram'])])
                
                # Tombol Navigasi
                nav_buttons = []
                if current_page > 0:
                    nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                
                if current_page < total_pages - 1:
                    nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                
                buttons.append(nav_buttons)
                
                # --- TOMBOL PENCARIAN ---
                buttons.append([Button.inline("🔍 Cari by ID Telegram", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna untuk diubah rolenya (Total: {total_users} user):'
                
                if last_msg:
                    try:
                        await last_msg.edit(msg_text, buttons=buttons)
                    except:
                        last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                # Tunggu respon
                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                # Logika Tombol
                if data == "next_page":
                    current_page += 1
                elif data == "prev_page":
                    current_page -= 1
                elif data == "ignore":
                    await response.answer(f"Halaman {current_page + 1} dari {total_pages}")
                elif data == "admin":
                    await response.delete()
                    return
                elif data == "search_id":
                    # --- FITUR PENCARIAN ---
                    await last_msg.delete() # Hapus menu list sementara
                    prompt_search = await event.respond("Kirimkan ID Telegram user yang ingin dicari:")
                    
                    search_msg = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = search_msg.raw_text.strip()
                    
                    # Validasi apakah ID ada di all_users
                    user_found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    
                    # Bersihkan chat history pencarian
                    await prompt_search.delete()
                    await search_msg.delete()
                    
                    if user_found:
                        selected_user_id = input_id
                        last_msg = None # Reset agar nanti pesan saldo dikirim baru
                        break # Keluar loop, lanjut ke input saldo
                    else:
                        last_msg = await event.respond(f"❌ User dengan ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali ke List", data="back_to_list")]])
                        # Tunggu user klik tombol kembali sebelum menampilkan list lagi
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                        # Loop akan mengulang dan menampilkan list lagi
                
                else:
                    # Jika diklik user dari list
                    selected_user_id = data
                    break 

            # --- PROSES INPUT SALDO ---
            # (Bagian ini jalan setelah user dipilih lewat List atau Pencarian)
            
            telegram_id = selected_user_id
            
            # Jika last_msg masih ada (dari list), hapus dulu agar rapi
            if last_msg:
                await last_msg.delete()

            prompt_saldo = await event.respond(f'Masukkan saldo untuk ID `{telegram_id}` (contoh: 50.000):')
            saldo1 = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            saldoo = saldo1.raw_text
            
            saldo_cleaned = saldoo.replace('.', '').strip()
            
            success = False
            message = "Gagal"
            
            if saldo_cleaned.isdigit():
                success, message = add_saldo(telegram_id, int(saldo_cleaned))
            else:
                await event.respond("Masukkan nilai saldo yang valid (angka).", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
                return
            
            username, idtele, role, saldo = get_user_info(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│           ADD SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Saldo    : {saldoo}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
                # Kirim notif ke user target
                try:
                    await bot.send_message(int(telegram_id), msg)
                except:
                    pass
            else:
                msg = f"""
╭──────────────────────╮
│           ADD SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])

    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()

    if valid_admin(str(sender.id)) == "true":
        await add_saldoo_(event)
    else:
        await event.answer("Akses Ditolak!", alert=True)

@bot.on(events.CallbackQuery(data=b'potong_saldo'))
async def potong_saldo(event):
    async def potong_saldo_(event):
        all_users = get_all_users()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
            return

        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            while True:
                if selected_user_id: break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Saldo: {user['saldo']})", data=user['id_telegram'])])
                
                nav_buttons = []
                if current_page > 0: nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                if current_page < total_pages - 1: nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                buttons.append(nav_buttons)
                
                buttons.append([Button.inline("🔍 Cari by ID", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna untuk POTONG SALDO (Total: {total_users}):'
                
                if last_msg:
                    try: await last_msg.edit(msg_text, buttons=buttons)
                    except: last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                if data == "next_page": current_page += 1
                elif data == "prev_page": current_page -= 1
                elif data == "ignore": await response.answer(f"Hal {current_page + 1}")
                elif data == "admin": 
                    await response.delete()
                    return
                elif data == "search_id":
                    if last_msg: await last_msg.delete() 
                    prompt = await event.respond("Kirimkan ID Telegram user:")
                    res = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = res.raw_text.strip()
                    found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    await prompt.delete()
                    await res.delete()
                    if found: selected_user_id = input_id; break 
                    else:
                        last_msg = await event.respond(f"❌ ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                else:
                    selected_user_id = data; break 

            # --- INPUT NOMINAL POTONGAN ---
            telegram_id = selected_user_id
            if last_msg: await last_msg.delete()

            prompt_saldo = await event.respond(f'Masukkan nominal POTONGAN saldo untuk ID `{telegram_id}` (contoh: 50.000):')
            saldo1 = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            saldoo = saldo1.raw_text
            saldo_cleaned = saldoo.replace('.', '').strip()
            
            success = False
            new_balance = 0
            
            if saldo_cleaned.isdigit():
                success, new_balance = subtract_saldo(telegram_id, int(saldo_cleaned))
            else:
                await event.respond("Masukkan nilai valid.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
                return
            
            username, idtele, role, saldo = get_user_info(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│       POTONG SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ User     : {username}
│ Potong   : {saldo_cleaned}
│ Baru     : {new_balance}
│ Role     : {role}
│ Status   : Saldo berhasil dikurangi.
╰──────────────────────╯
"""
            else:
                msg = f"""
╭──────────────────────╮
│       POTONG SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ User     : {username}
│ Role     : {role}
│ Status   : {new_balance}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])

    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true": await potong_saldo_(event)
    else: await event.answer("Akses Ditolak!", alert=True)

# ==========================================
# 2. DELETE USER (General Users)
# ==========================================
@bot.on(events.CallbackQuery(data=b'delet_user'))
async def delet_user(event):
    async def delet_user_(event):
        all_users = get_all_users()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
            return

        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            while True:
                if selected_user_id: break
                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Role: {user['role']})", data=user['id_telegram'])])
                
                nav_buttons = []
                if current_page > 0: nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                if current_page < total_pages - 1: nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                buttons.append(nav_buttons)
                
                buttons.append([Button.inline("🔍 Cari by ID", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna untuk DIHAPUS (Total: {total_users}):'
                
                if last_msg:
                    try: await last_msg.edit(msg_text, buttons=buttons)
                    except: last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                if data == "next_page": current_page += 1
                elif data == "prev_page": current_page -= 1
                elif data == "ignore": await response.answer(f"Hal {current_page + 1}")
                elif data == "admin": 
                    await response.delete()
                    return
                elif data == "search_id":
                    if last_msg: await last_msg.delete() 
                    prompt = await event.respond("Kirimkan ID Telegram user:")
                    res = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = res.raw_text.strip()
                    found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    await prompt.delete()
                    await res.delete()
                    if found: selected_user_id = input_id; break 
                    else:
                        last_msg = await event.respond(f"❌ ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                else:
                    selected_user_id = data; break 

            # --- EKSEKUSI DELETE ---
            telegram_id = selected_user_id
            if last_msg: await last_msg.delete()

            success, message = delete_user(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│       DELET USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Status   : {message}
╰──────────────────────╯
"""
            else:
                msg = f"""
╭──────────────────────╮
│       DELET USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
    
    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true": await delet_user_(event)
    else: await event.answer("Akses Ditolak!", alert=True)

# ==========================================
# 3. DELETE BY ID (Access/Role List)
# ==========================================
@bot.on(events.CallbackQuery(data=b'delet_byid'))
async def delet_byid(event):
    async def delet_byid_(event):
        all_users = get_all_userbyid() # Menggunakan list akses/ID khusus
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
            return

        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            while True:
                if selected_user_id: break
                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Role: {user['role']})", data=user['id_telegram'])])
                
                nav_buttons = []
                if current_page > 0: nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                if current_page < total_pages - 1: nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                buttons.append(nav_buttons)
                
                buttons.append([Button.inline("🔍 Cari by ID", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna (By ID) untuk DIHAPUS AKSES (Total: {total_users}):'
                
                if last_msg:
                    try: await last_msg.edit(msg_text, buttons=buttons)
                    except: last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                if data == "next_page": current_page += 1
                elif data == "prev_page": current_page -= 1
                elif data == "ignore": await response.answer(f"Hal {current_page + 1}")
                elif data == "admin": 
                    await response.delete()
                    return
                elif data == "search_id":
                    if last_msg: await last_msg.delete() 
                    prompt = await event.respond("Kirimkan ID Telegram user:")
                    res = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = res.raw_text.strip()
                    found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    await prompt.delete()
                    await res.delete()
                    if found: selected_user_id = input_id; break 
                    else:
                        last_msg = await event.respond(f"❌ ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                else:
                    selected_user_id = data; break 

            # --- EKSEKUSI DELETE AKSES ---
            telegram_id = selected_user_id
            if last_msg: await last_msg.delete()

            success, message = delete_byidd(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│       DELET AKSES
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Status   : {message}
╰──────────────────────╯
"""
            else:
                msg = f"""
╭──────────────────────╮
│       DELET AKSES
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
    
    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true": await delet_byid_(event)
    else: await event.answer("Akses Ditolak!", alert=True)

# ==========================================
# 4. UBAH ROLE (General Users)
# ==========================================
@bot.on(events.CallbackQuery(data=b'ubah_role'))
async def ubah_role(event):
    async def ubah_role_(event):
        all_users = get_all_users()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
            return

        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            while True:
                if selected_user_id: break
                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Role: {user['role']})", data=user['id_telegram'])])
                
                nav_buttons = []
                if current_page > 0: nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                if current_page < total_pages - 1: nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                buttons.append(nav_buttons)
                
                buttons.append([Button.inline("🔍 Cari by ID", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna untuk UBAH ROLE (Total: {total_users}):'
                
                if last_msg:
                    try: await last_msg.edit(msg_text, buttons=buttons)
                    except: last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                if data == "next_page": current_page += 1
                elif data == "prev_page": current_page -= 1
                elif data == "ignore": await response.answer(f"Hal {current_page + 1}")
                elif data == "admin": 
                    await response.delete()
                    return
                elif data == "search_id":
                    if last_msg: await last_msg.delete() 
                    prompt = await event.respond("Kirimkan ID Telegram user:")
                    res = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = res.raw_text.strip()
                    found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    await prompt.delete()
                    await res.delete()
                    if found: selected_user_id = input_id; break 
                    else:
                        last_msg = await event.respond(f"❌ ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                else:
                    selected_user_id = data; break 

            # --- PILIH ROLE BARU ---
            telegram_id = selected_user_id
            if last_msg: await last_msg.delete()

            role_msg = await event.respond(f'Pilih role baru untuk ID `{telegram_id}`:', buttons=[
                [Button.inline(" Priority ", "priority"), Button.inline(" Super Reseller ", "super_reseller")],
                [Button.inline(" Reseller ", "reseller"), Button.inline(" Admin ", "admin")]
            ])
            
            resp_role = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            selected_role = resp_role.data.decode("ascii")
            await role_msg.delete()

            success, message = change_role(telegram_id, selected_role)
            username, idtele, role, saldo = get_user_info(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│        UBAH ROLE
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role Baru : {selected_role}
│ Status   : {message}
╰──────────────────────╯
"""
            else:
                msg = f"""
╭──────────────────────╮
│        UBAH ROLE
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])

    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true": await ubah_role_(event)
    else: await event.answer("Akses Ditolak!", alert=True)

@bot.on(events.CallbackQuery(data=b'list_user'))
async def list_user(event):
    # Ambil informasi semua pengguna dari database
    all_users = get_all_users()

    # Cek jika tidak ada pengguna yang tersedia
    if not all_users:
        await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])
        return
    all_users = sorted(all_users, key=lambda user: user['username'].lower())

    # Siapkan format tampilan informasi semua user
    message = "📋 **Daftar Pengguna:**\n\n"
    messages = []  # List untuk menyimpan pesan yang akan dikirim
    for user in all_users:
        user_info = (
            f"👤 Username: {user['username']}\n"
            f"🆔 ID Telegram: {user['id_telegram']}\n"
            f"🎖️ Role: {user['role']}\n"
            f"💰 Saldo: {user['saldo']}\n"
            "────────────────────\n"
        )

        # Jika menambahkan user_info melebihi batas 4096 karakter, simpan pesan sebelumnya dan mulai pesan baru
        if len(message + user_info) > 4096:
            messages.append(message)  # Simpan pesan ke dalam daftar
            message = "📋 **Daftar Pengguna (Lanjutan):**\n\n"  # Buat pesan baru untuk data selanjutnya
        
        message += user_info

    # Tambahkan pesan terakhir yang belum disimpan
    messages.append(message)

    # Kirim semua pesan yang tersimpan
    for msg in messages:
        await event.respond(msg)

    # Tambahkan tombol "Back to Menu" setelah semua pesan terkirim
    await event.respond("Selesai menampilkan semua pengguna.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])

    # Mengambil informasi pengirim
    sender = await event.get_sender()

    # Validasi admin sebelum melanjutkan
    if valid_admin(str(sender.id)) == "true":
        return
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

@bot.on(events.NewMessage(pattern=r"(?:.dell|/dell)$"))
@bot.on(events.CallbackQuery(data=b'deluser'))
async def deluser(event):
    # Mengambil informasi pengirim
    sender = await event.get_sender()

    # Validasi admin sebelum melanjutkan
    if valid_admin(str(sender.id)) != "true":
        # Gunakan `answer` hanya jika event adalah CallbackQuery
        if isinstance(event, events.CallbackQuery.Event):
            await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)
        else:
            await event.respond("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪")
        return

    # Memproses penghapusan pengguna dan mengambil hasilnya
    all_users = await process_users_for_deletion()  # Dapatkan daftar pengguna yang berhasil dihapus

    # Siapkan format tampilan informasi semua user
    if all_users:
        message = "📋 **Done:**\n\n"
        messages = []  # List untuk menyimpan pesan yang akan dikirim
        for user in all_users:
            user_info = (
                f"👤 Username: {user['username']}\n"
                "────────────────────\n"
            )

            # Jika menambahkan user_info melebihi batas 4096 karakter, simpan pesan sebelumnya dan mulai pesan baru
            if len(message + user_info) > 4096:
                messages.append(message)  # Simpan pesan ke dalam daftar
                message = "📋 **Daftar Pengguna (Lanjutan):**\n\n"  # Buat pesan baru untuk data selanjutnya
            
            message += user_info

        # Tambahkan pesan terakhir yang belum disimpan
        messages.append(message)

        # Kirim semua pesan yang tersimpan
        for msg in messages:
            await event.respond(msg)
    else:
        await event.respond("Tidak ada pengguna yang dihapus.")

    # Tambahkan tombol "Back to Menu" setelah semua pesan terkirim
    await event.respond("Selesai menampilkan semua pengguna.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user")]])

@bot.on(events.NewMessage(pattern=r"(?:.user|/user)$"))
@bot.on(events.CallbackQuery(data=b'user'))
async def user(event):
    inline = [
        [Button.inline(" Add User", "add_user"),
        Button.inline(" Add Saldo ", "add_saldoo")],
        [Button.inline(" Add Akses by user", "add_byid"),
        Button.inline(" Delet Akses by user", "delet_byid")],
        [Button.inline(" Potong Saldo", "potong_saldo"),
        Button.inline(" Delet User", "delet_user")],
        [Button.inline(" Ubah Role", "ubah_role"),
        Button.inline(" List User", "list_user")],
        [Button.inline(" Delet User saldo 0", "deluser")],
        [Button.inline(" Back To Menu ", "admin")]
    ]
    
    # Melanjutkan pengecekan valid_superadmin jika username ada
    sender = await event.get_sender()
    val = valid_admin(str(sender.id))
    
    if val == "false":
        try:
            await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)
        except:
            await event.reply("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪")
    elif val == "true":
        sender_id = str(sender.id)
        username, idtele, role, saldo = get_user_info(sender.id)

        msg = f"""
╭───────────────────────╮
│         🤖 HIDE PULSA 🤖         
├───────────────────────┤
│ Username : {username}
│ User ID    : {idtele}
│ Role      : {role}
├───────────────────────┤
│ Menu Kontrol Panel HIDE PULSA
╰───────────────────────╯
"""
        try:
            await event.edit(msg, buttons=inline)
        except:
            await event.reply(msg, buttons=inline)