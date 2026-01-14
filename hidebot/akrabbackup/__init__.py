# admin/__init__.py

import sys
import importlib
import glob
from os.path import basename, dirname, isfile

def __list_all_modules():
    mod_paths = glob.glob(dirname(__file__) + "/*.py")
    all_modules = [
        basename(f)[:-3]
        for f in mod_paths
        if isfile(f) and f.endswith(".py") and not f.endswith("__init__.py")
    ]
    return all_modules

ALL_MODULES = sorted(__list_all_modules())

# Impor semua modul dan ambil semua fungsi ke dalam namespace
for module in ALL_MODULES:
    imported_module = importlib.import_module(f".{module}", package=__name__)
