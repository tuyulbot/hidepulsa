from hidebot import *
from importlib import import_module
from hidebot.dor import ALL_MODULES as ALL_MODULES_1
from hidebot.menu import ALL_MODULES as ALL_MODULES_2
from hidebot.cek import ALL_MODULES as ALL_MODULES_3
from hidebot.akrab import ALL_MODULES as ALL_MODULES_4
from hidebot.topup import ALL_MODULES as ALL_MODULES_5
from hidebot.circel import ALL_MODULES as ALL_MODULES_6

# Menggabungkan semua modul dari semua folder
ALL_MODULES = ALL_MODULES_1 + ALL_MODULES_2 + ALL_MODULES_3 + ALL_MODULES_4 + ALL_MODULES_5 + ALL_MODULES_6

# Loop melalui semua modul di modules1, modules2, dan modules3
for module_name in ALL_MODULES:
    if module_name in ALL_MODULES_1:
        imported_module = import_module("hidebot.dor." + module_name)
    elif module_name in ALL_MODULES_2:
        imported_module = import_module("hidebot.menu." + module_name)
    elif module_name in ALL_MODULES_3:
        imported_module = import_module("hidebot.cek." + module_name)
    elif module_name in ALL_MODULES_4:
        imported_module = import_module("hidebot.akrab." + module_name)
    elif module_name in ALL_MODULES_5:
        imported_module = import_module("hidebot.topup." + module_name)
    elif module_name in ALL_MODULES_6:
        imported_module = import_module("hidebot.circel." + module_name)

# Menjalankan bot
try:
    print("Bot is running...")
    bot.run_until_disconnected()
finally:
    print("Bot is shutting down...")
    bot.disconnect()