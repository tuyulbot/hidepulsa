from hidebot import *

def get_all_userbyid():
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query

        # Query untuk mendapatkan semua informasi pengguna
        query = """
        SELECT username, id_telegram, role, saldo
        FROM by_id;
        """
        cursor.execute(query)
        all_users = cursor.fetchall()  # Mengambil semua hasil query

        # Cek jika ada pengguna yang ditemukan
        if all_users:
            return all_users  # Mengembalikan daftar pengguna
        else:
            print("Tidak ada pengguna ditemukan.")
            return []  # Mengembalikan daftar kosong jika tidak ada pengguna
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return []  # Mengembalikan daftar kosong jika terjadi kesalahan
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def validate_byid11(id_telegram, role_name):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    conn = retry_connection1(get_db_connection2, max_retry=3, retry_interval=2)

    try:
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query
        
        # Query untuk mengambil role berdasarkan id_telegram
        query = "SELECT id_telegram, role FROM sys_id WHERE id_telegram = %s"
        cursor.execute(query, (id_telegram,))
        user = cursor.fetchone()
        
        # Validasi role
        if user and user['role'] == role_name:
            return "true"
        else:
            return "false"
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return "false"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def valid_superress_byid1(id_telegram):
    return validate_byid11(id_telegram, 'super_reseller')

def valid_ress_byid1(id_telegram):
    return validate_byid11(id_telegram, 'reseller')

def valid_priority_byid1(id_telegram):
    return validate_byid11(id_telegram, 'priority')

def validate_byid(id_telegram, role_name):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    conn = retry_connection(get_db_connection, max_retry=3, retry_interval=2)

    try:
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query
        
        # Query untuk mengambil role berdasarkan id_telegram
        query = "SELECT id_telegram, role FROM by_id WHERE id_telegram = %s"
        cursor.execute(query, (id_telegram,))
        user = cursor.fetchone()
        
        # Validasi role
        if user and user['role'] == role_name:
            return "true"
        else:
            return "false"
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return "false"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def valid_superress_byid(id_telegram):
    return validate_byid(id_telegram, 'super_reseller')

def valid_priority_byid(id_telegram):
    return validate_byid(id_telegram, 'priority')

def validate_role(id_telegram, role_name):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    conn = retry_connection(get_db_connection, max_retry=3, retry_interval=2)

    try:
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query
        
        # Query untuk mengambil role berdasarkan id_telegram
        query = "SELECT id_telegram, role FROM user WHERE id_telegram = %s"
        cursor.execute(query, (id_telegram,))
        user = cursor.fetchone()
        
        # Validasi role
        if user and user['role'] == role_name:
            return "true"
        else:
            return "false"
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return "false"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Fungsi untuk validasi admin
def valid_admin(id_telegram):
    return validate_role(id_telegram, 'admin')

def valid_reseller(id_telegram):
    return validate_role(id_telegram, 'reseller')

# Fungsi untuk validasi super reseller
def valid_superreseller(id_telegram):
    return validate_role(id_telegram, 'super_reseller')

def valid_priority(id_telegram):
    return validate_role(id_telegram, 'priority')

def validate_role1(id_telegram, role_name):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    conn = retry_connection1(get_db_connection2, max_retry=3, retry_interval=2)

    try:
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query
        
        # Query untuk mengambil role berdasarkan id_telegram
        query = "SELECT id_telegram, role FROM ress WHERE id_telegram = %s"
        cursor.execute(query, (id_telegram,))
        user = cursor.fetchone()
        
        # Validasi role
        if user and user['role'] == role_name:
            return "true"
        else:
            return "false"
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return "false"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
def valid_reseller1(id_telegram):
    return validate_role1(id_telegram, 'reseller')

# Fungsi untuk validasi super reseller
def valid_superreseller1(id_telegram):
    return validate_role1(id_telegram, 'super_reseller')

def valid_priority1(id_telegram):
    return validate_role1(id_telegram, 'priority')

def get_user_info1(id_telegram): 
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        if conn is None or not conn.is_connected():
            print("Koneksi tidak valid, mencoba mendapatkan koneksi baru...")
            conn = get_db_connection2()
        if conn is None or not conn.is_connected():
            print("Gagal mendapatkan koneksi ke database.")
            return None, None, None, None
        
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query
        # Query untuk mendapatkan informasi pengguna
        query = """
        SELECT username, id_telegram, role, saldo
        FROM ress 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (id_telegram,))
        user_info = cursor.fetchone()  # Mengambil satu baris hasil
        
        # Cek jika pengguna ditemukan
        if user_info:
            return user_info['username'], user_info['id_telegram'], user_info['role'], user_info['saldo']
        else:
            print("Pengguna tidak ditemukan.")
            return None, None, None, None  # Mengembalikan None jika pengguna tidak ada
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return None, None, None, None  # Mengembalikan None jika terjadi kesalahan
    finally:
        # Pastikan conn dan cursor didefinisikan sebelum ditutup
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_user_info(id_telegram):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor
    
    try:
        conn = get_db_connection()
        if conn is None or not conn.is_connected():
            print("Koneksi tidak valid, mencoba mendapatkan koneksi baru...")
            conn = get_db_connection()
        if conn is None or not conn.is_connected():
            print("Gagal mendapatkan koneksi ke database.")
            return None, None, None, None
        
        cursor = conn.cursor(dictionary=True)
        # Query untuk mendapatkan informasi pengguna
        query = """
        SELECT username, id_telegram, role, saldo
        FROM user 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (id_telegram,))
        user_info = cursor.fetchone()  # Mengambil satu baris hasil
        
        # Cek jika pengguna ditemukan
        if user_info:
            return user_info['username'], user_info['id_telegram'], user_info['role'], user_info['saldo']
        else:
            print("Pengguna tidak ditemukan.")
            return None, None, None, None  # Mengembalikan None jika pengguna tidak ada
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return None, None, None, None  # Mengembalikan None jika terjadi kesalahan
    finally:
        # Pastikan conn dan cursor didefinisikan sebelum ditutup
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def retry_connection1(get_connection_func, max_retry=3, retry_interval=2):
    """
    Mencoba ulang koneksi database jika gagal.
    
    Args:
        get_connection_func (callable): Fungsi untuk mendapatkan koneksi database.
        max_retry (int): Jumlah maksimum percobaan koneksi.
        retry_interval (int): Interval waktu (dalam detik) antara percobaan.
        
    Returns:
        conn: Objek koneksi database atau None jika semua percobaan gagal.
    """
    conn = None
    for attempt in range(max_retry):
        try:
            conn = get_connection_func()
            if conn is not None:  # Jika koneksi berhasil
                return conn
        except mysql.connector.Error as err:
            print(f"Percobaan {attempt + 1}/{max_retry} gagal: {err}")
        time.sleep(retry_interval)  # Tunggu sebelum mencoba lagi
    print("Gagal mendapatkan koneksi database setelah beberapa percobaan.")
    return None

def retry_connection(get_connection_func, max_retry=3, retry_interval=2):
    conn = None
    for attempt in range(max_retry):
        try:
            conn = get_connection_func()
            if conn is not None:  # Jika koneksi berhasil
                return conn
        except mysql.connector.Error as err:
            print(f"Percobaan {attempt + 1}/{max_retry} gagal: {err}")
        time.sleep(retry_interval)  # Tunggu sebelum mencoba lagi
    print("Gagal mendapatkan koneksi database setelah beberapa percobaan.")
    return None


def add_member(username, id_telegram, role):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Tentukan password berdasarkan role
        if role == 'reseller':
            password = 'reseller'
        elif role == 'admin':
            password = 'admin'
        elif role == 'super_reseller':
            password = 'super_reseller'
        elif role == 'priority':
            password = 'priority'
        else:
            password = 'default_password'  # Password default jika role tidak dikenal

        # Query untuk menambahkan anggota baru ke tabel user
        query = """
        INSERT INTO user (username, id_telegram, role, password) 
        VALUES (%s, %s, %s, %s);
        """
        cursor.execute(query, (username, id_telegram, role, password))
        
        # Commit perubahan
        conn.commit()
        
        print("Anggota berhasil ditambahkan.")
        return True, "Anggota berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def add_byidd(username, id_telegram, role):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor 

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Cek apakah id_telegram sudah ada di database
        check_query = "SELECT COUNT(*) FROM by_id WHERE id_telegram = %s"
        cursor.execute(check_query, (id_telegram,))
        exists = cursor.fetchone()[0]

        if exists > 0:
            return False, "Pengguna dengan ID Telegram ini sudah ada."

        # Query untuk menambahkan anggota baru ke tabel user
        query = """
        INSERT INTO by_id (username, id_telegram, role) 
        VALUES (%s, %s, %s);
        """
        cursor.execute(query, (username, id_telegram, role))
        
        # Commit perubahan
        conn.commit()
        
        print("Anggota berhasil ditambahkan.")
        return True, "Anggota berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def add_saldo(id_telegram, amount):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query untuk menambah saldo
        query = """
        UPDATE user 
        SET saldo = saldo + %s 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (amount, id_telegram))
        
        # Commit perubahan
        conn.commit()
        
        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount == 0:
            print("ID Telegram tidak ditemukan.")
            return False, "ID Telegram tidak ditemukan."
        else:
            print("Saldo berhasil ditambahkan.")
            return True, "Saldo berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, str(err)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_all_users():
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query

        # Query untuk mendapatkan semua informasi pengguna
        query = """
        SELECT username, id_telegram, role, saldo
        FROM user;
        """
        cursor.execute(query)
        all_users = cursor.fetchall()  # Mengambil semua hasil query

        # Cek jika ada pengguna yang ditemukan
        if all_users:
            return all_users  # Mengembalikan daftar pengguna
        else:
            print("Tidak ada pengguna ditemukan.")
            return []  # Mengembalikan daftar kosong jika tidak ada pengguna
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return []  # Mengembalikan daftar kosong jika terjadi kesalahan
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def subtract_saldo(id_telegram, amount):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query untuk mengurangi saldo
        query = """
        UPDATE user 
        SET saldo = saldo - %s 
        WHERE id_telegram = %s AND saldo >= %s;
        """
        cursor.execute(query, (amount, id_telegram, amount))

        # Commit perubahan
        conn.commit()
        
        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount == 0:
            return False, "ID Telegram tidak ditemukan atau saldo tidak cukup."
        
        # Ambil saldo yang baru
        cursor.execute("SELECT saldo FROM user WHERE id_telegram = %s;", (id_telegram,))
        new_balance = cursor.fetchone()
        if new_balance:
            return True, new_balance[0]  # Mengembalikan saldo baru
        else:
            return False, "Gagal mendapatkan saldo baru."
    except mysql.connector.Error as err:
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def delete_user(id_telegram):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query untuk menghapus user
        query = """
        DELETE FROM user 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (id_telegram,))
        
        # Commit perubahan
        conn.commit()
        
        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount == 0:
            print("ID Telegram tidak ditemukan.")
            return False, "ID Telegram tidak ditemukan."
        else:
            print("User berhasil dihapus.")
            return True, "User berhasil dihapus."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def delete_byidd(id_telegram):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor 

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Cek apakah id_telegram ada di database
        check_query = "SELECT COUNT(*) FROM by_id WHERE id_telegram = %s"
        cursor.execute(check_query, (id_telegram,))
        exists = cursor.fetchone()[0]

        if exists == 0:
            return False, "Pengguna dengan ID Telegram ini tidak ditemukan."

        # Query untuk menghapus pengguna dari tabel by_id
        delete_query = "DELETE FROM by_id WHERE id_telegram = %s"
        cursor.execute(delete_query, (id_telegram,))
        
        # Commit perubahan
        conn.commit()
        
        print("Pengguna berhasil dihapus.")
        return True, "Pengguna berhasil dihapus."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def change_role(id_telegram, new_role):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query untuk mengubah role pengguna
        query = """
        UPDATE user 
        SET role = %s 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (new_role, id_telegram))

        # Commit perubahan
        conn.commit()

        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount > 0:  # Jika baris yang terpengaruh lebih dari 0, role berhasil diubah
            return True, f"Role berhasil diubah"
        else:  # Jika tidak ada baris yang terpengaruh, berarti ID tidak ditemukan
            return False, "ID Telegram tidak ditemukan."
    except mysql.connector.Error as err:
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

async def process_users_for_deletion():

    # Ambil semua pengguna
    all_users = get_all_users()
    
    # Periksa apakah ada pengguna yang ditemukan
    if not all_users:
        print("Tidak ada pengguna yang ditemukan.")
        return []

    deleted_users = []  # Daftar untuk menyimpan pengguna yang berhasil dihapus

    # Loop melalui setiap pengguna
    for user in all_users:
        id_telegram = user['id_telegram']

        # Ambil informasi saldo untuk setiap pengguna
        username, id_telegram, role, saldo = get_user_info(id_telegram)
        
        # Periksa apakah saldo adalah 0
        if saldo <= 2000:
            # Hapus pengguna jika saldo 0
            success, message = delete_user(id_telegram)
            if success:
                # Tambahkan pengguna yang dihapus ke daftar deleted_users
                deleted_users.append({"username": username, "id_telegram": id_telegram})
            print(f"Pengguna '{username}': {message}")  # Menampilkan nama pengguna dengan pesan keberhasilan atau kegagalan
        else:
            print(f"Pengguna '{username}' memiliki saldo {saldo}, tidak dihapus.")

    return deleted_users

def add_member1(username, id_telegram, role):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        cursor = conn.cursor()

        # Cek apakah id_telegram sudah ada di database
        check_query = "SELECT COUNT(*) FROM ress WHERE id_telegram = %s"
        cursor.execute(check_query, (id_telegram,))
        exists = cursor.fetchone()[0]

        if exists > 0:
            return False, "Pengguna dengan ID Telegram ini sudah ada."

        # Query untuk menambahkan anggota baru ke tabel user
        query = """
        INSERT INTO ress (username, id_telegram, role) 
        VALUES (%s, %s, %s);
        """
        cursor.execute(query, (username, id_telegram, role))
        
        # Commit perubahan
        conn.commit()
        
        print("Anggota berhasil ditambahkan.")
        return True, "Anggota berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def add_byidd2(username, id_telegram, role):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor  

    try:
        conn = get_db_connection2()
        cursor = conn.cursor()

        # Cek apakah id_telegram sudah ada di database
        check_query = "SELECT COUNT(*) FROM sys_id WHERE id_telegram = %s"
        cursor.execute(check_query, (id_telegram,))
        exists = cursor.fetchone()[0]

        if exists > 0:
            return False, "Pengguna dengan ID Telegram ini sudah ada."

        # Query untuk menambahkan anggota baru ke tabel user
        query = """
        INSERT INTO sys_id (username, id_telegram, role) 
        VALUES (%s, %s, %s);
        """
        cursor.execute(query, (username, id_telegram, role))
        
        # Commit perubahan
        conn.commit()
        
        print("Anggota berhasil ditambahkan.")
        return True, "Anggota berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def add_memberr1(username, id_telegram, role):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        cursor = conn.cursor()
        
        # Cek apakah id_telegram sudah ada di tabel user
        check_query = "SELECT COUNT(*) FROM ress WHERE id_telegram = %s"
        cursor.execute(check_query, (id_telegram,))
        (count,) = cursor.fetchone()
        
        if count > 0:
            print(f"ID Telegram {id_telegram} sudah ada di database.")
            return False, f"ID Telegram {id_telegram} sudah ada di database."
        
        # Query untuk menambahkan anggota baru ke tabel user
        query = """
        INSERT INTO user (username, id_telegram, role) 
        VALUES (%s, %s, %s);
        """
        cursor.execute(query, (username, id_telegram, role))
        
        # Commit perubahan
        conn.commit()
        
        print("Anggota berhasil ditambahkan.")
        return True, "Anggota berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# Fungsi untuk menambah saldo
def add_saldo1(id_telegram, amount):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        cursor = conn.cursor()

        # Query untuk menambah saldo
        query = """
        UPDATE ress 
        SET saldo = saldo + %s 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (amount, id_telegram))
        
        # Commit perubahan
        conn.commit()
        
        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount == 0:
            print("ID Telegram tidak ditemukan.")
            return False, "ID Telegram tidak ditemukan."
        else:
            print("Saldo berhasil ditambahkan.")
            return True, "Saldo berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, str(err)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Fungsi untuk mengurangi saldo
def subtract_saldo1(id_telegram, amount):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        cursor = conn.cursor()

        # Query untuk mengurangi saldo
        query = """
        UPDATE ress 
        SET saldo = saldo - %s 
        WHERE id_telegram = %s AND saldo >= %s;
        """
        cursor.execute(query, (amount, id_telegram, amount))

        # Commit perubahan
        conn.commit()
        
        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount == 0:
            return False, "ID Telegram tidak ditemukan atau saldo tidak cukup."
        
        # Ambil saldo yang baru
        cursor.execute("SELECT saldo FROM user WHERE id_telegram = %s;", (id_telegram,))
        new_balance = cursor.fetchone()
        if new_balance:
            return True, new_balance[0]  # Mengembalikan saldo baru
        else:
            return False, "Gagal mendapatkan saldo baru."
    except mysql.connector.Error as err:
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Fungsi untuk menghapus user
def delete_user1(id_telegram):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        cursor = conn.cursor()

        # Query untuk menghapus user
        query = """
        DELETE FROM ress 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (id_telegram,))
        
        # Commit perubahan
        conn.commit()
        
        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount == 0:
            print("ID Telegram tidak ditemukan.")
            return False, "ID Telegram tidak ditemukan."
        else:
            print("User berhasil dihapus.")
            return True, "User berhasil dihapus."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Fungsi rubah role
def change_role1(id_telegram, new_role):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        cursor = conn.cursor()

        # Query untuk mengubah role pengguna
        query = """
        UPDATE ress 
        SET role = %s 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (new_role, id_telegram))

        # Commit perubahan
        conn.commit()

        # Cek jumlah baris yang terpengaruh
        if cursor.rowcount > 0:  # Jika baris yang terpengaruh lebih dari 0, role berhasil diubah
            return True, f"Role berhasil diubah"
        else:  # Jika tidak ada baris yang terpengaruh, berarti ID tidak ditemukan
            return False, "ID Telegram tidak ditemukan."
    except mysql.connector.Error as err:
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# fungsi informasi user 
def get_user_info1(id_telegram): 
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection2()
        if conn is None or not conn.is_connected():
            print("Koneksi tidak valid, mencoba mendapatkan koneksi baru...")
            conn = get_db_connection2()
        if conn is None or not conn.is_connected():
            print("Gagal mendapatkan koneksi ke database.")
            return None, None, None, None
        
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query
        # Query untuk mendapatkan informasi pengguna
        query = """
        SELECT username, id_telegram, role, saldo
        FROM ress 
        WHERE id_telegram = %s;
        """
        cursor.execute(query, (id_telegram,))
        user_info = cursor.fetchone()  # Mengambil satu baris hasil
        
        # Cek jika pengguna ditemukan
        if user_info:
            return user_info['username'], user_info['id_telegram'], user_info['role'], user_info['saldo']
        else:
            print("Pengguna tidak ditemukan.")
            return None, None, None, None  # Mengembalikan None jika pengguna tidak ada
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return None, None, None, None  # Mengembalikan None jika terjadi kesalahan
    finally:
        # Pastikan conn dan cursor didefinisikan sebelum ditutup
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# fungsi untuk menampilkan smua user
def get_all_users1():
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor
    
    try:
        conn = get_db_connection2()
        cursor = conn.cursor(dictionary=True)  # Menggunakan dictionary untuk hasil query

        # Query untuk mendapatkan semua informasi pengguna
        query = """
        SELECT username, id_telegram, role, saldo
        FROM ress;
        """
        cursor.execute(query)
        all_users = cursor.fetchall()  # Mengambil semua hasil query

        # Cek jika ada pengguna yang ditemukan
        if all_users:
            return all_users  # Mengembalikan daftar pengguna
        else:
            print("Tidak ada pengguna ditemukan.")
            return []  # Mengembalikan daftar kosong jika tidak ada pengguna
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return []  # Mengembalikan daftar kosong jika terjadi kesalahan
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

async def izin1(sender_id, callback, event):
    val = valid_admin(str(sender_id))
    val1 = valid_reseller(str(sender_id))
    val2 = valid_member(str(sender_id))
    val3 = valid_superreseller(str(sender_id))
    val4 = valid_reseller1(str(sender_id))
    val5 = valid_superreseller1(str(sender_id))

    # Cek apakah salah satu validasi terpenuhi
    if val == "true" or val1 == "true" or val2 == "true" or val3 == "true" or val4 == "true" or val5 == "true":
        # Jika validasi berhasil, panggil callback (misal login_)
        await callback(event)
    else:
        # Jika validasi gagal, tampilkan pesan
        await event.answer(monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"), alert=True)

async def izin(sender_id, callback, event):
    # Kumpulkan semua validasi ke dalam list 
    validations = [
        valid_admin(str(sender_id)),
        valid_reseller(str(sender_id)),
        valid_priority(str(sender_id)),
        valid_superreseller(str(sender_id)),
        valid_superress_byid(str(sender_id)),
        valid_priority_byid(str(sender_id)),
        valid_superress_byid1(str(sender_id)),
        valid_ress_byid1(str(sender_id)),
        valid_priority_byid1(str(sender_id)),
        valid_reseller1(str(sender_id)),
        valid_superreseller1(str(sender_id)),
        valid_priority1(str(sender_id))
    ]

    # Cek apakah ada satu saja validasi yang berhasil
    if "true" in validations:
        try:
            # Jika validasi berhasil, panggil callback (misal login_)
            print("Memanggil callback untuk event:", event)
            await callback(event)
        except Exception as e:
            print(f"Error saat memanggil callback: {e}")
            raise e
    else:
        # Jika validasi gagal, tampilkan pesan
        await event.answer(
            monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"), alert=True
        )

def user_exists1(id_telegram):
    """Cek apakah user sudah ada di tabel user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT COUNT(*) FROM user WHERE id_telegram = %s"
    cursor.execute(query, (id_telegram,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return result[0] > 0

def user_exists2(id_telegram):
    """Cek apakah user sudah ada di tabel ress."""
    conn = get_db_connection2()
    cursor = conn.cursor()
    
    query = "SELECT COUNT(*) FROM ress WHERE id_telegram = %s"
    cursor.execute(query, (id_telegram,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return result[0] > 0

def add_memberr(username, id_telegram, role):
    conn = None  # Inisialisasi variabel conn
    cursor = None  # Inisialisasi variabel cursor

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Cek apakah id_telegram sudah ada di tabel user
        check_query = "SELECT COUNT(*) FROM user WHERE id_telegram = %s"
        cursor.execute(check_query, (id_telegram,))
        (count,) = cursor.fetchone()

        if count > 0:
            print(f"ID Telegram {id_telegram} sudah ada di database.")
            return False, f"ID Telegram {id_telegram} sudah ada di database."

        # Tentukan password berdasarkan role
        if role == 'reseller':
            password = 'reseller'
        elif role == 'admin':
            password = 'admin'
        elif role == 'super_reseller':
            password = 'super_reseller'
        elif role == 'priority':
            password = 'priority'
        else:
            password = 'default_password'  # Password default jika role tidak dikenal

        # Query untuk menambahkan anggota baru ke tabel user
        query = """
        INSERT INTO user (username, id_telegram, role, password) 
        VALUES (%s, %s, %s, %s);
        """
        cursor.execute(query, (username, id_telegram, role, password))

        # Commit perubahan
        conn.commit()

        print("Anggota berhasil ditambahkan.")
        return True, "Anggota berhasil ditambahkan."
    except mysql.connector.Error as err:
        print(f"Terjadi kesalahan: {err}")
        return False, f"Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()