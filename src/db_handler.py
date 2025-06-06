from collections import namedtuple
import sqlite3
from os.path import join, exists
from os import remove as delete_file
from enum import Enum
from zlib import crc32
from queue import Queue
import threading  # Import the threading module

from src import logger
from src import globals

DATABASE_FILE_NAME = "ninova_arsivci.db"
TABLE_CREATION_QUERY = "CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT UNIQUE, hash INT, isDeleted INT DEFAULT 0);"
TABLE_CHECK_QUERY = (
    "SELECT name FROM sqlite_master WHERE type='table' AND name='files';"
)
SELECT_FILE_BY_ID_QUERY = "SELECT isDeleted, id FROM files WHERE id = ?"
FILE_INSERTION_QUERY = "INSERT INTO files (id, path, hash) VALUES (?, ?, ?)"


class FILE_STATUS(Enum):
    NEW = 0
    DELETED = 1
    EXISTS = 2


FileRecord = namedtuple("FileRecord", "id, path")


class DB:
    # Use threading.local() to store connection objects. Each thread will have its own.
    _thread_local = threading.local()
    to_add = Queue()
    db_path: str

    @classmethod
    def get_thread_safe_connection(cls):
        """
        Gets a database connection that is safe for the current thread.
        If a connection does not exist for this thread, it creates one.
        """
        # Check if a connection exists for the current thread
        if not hasattr(cls._thread_local, "connection"):
            # If not, create a new one and store it in the thread-local storage
            try:
                cls._thread_local.connection = sqlite3.connect(cls.db_path, check_same_thread=True)
                logger.debug(f"Thread {threading.get_ident()} created a new DB connection.")
            except Exception as e:
                logger.fail(f"Veritabanına bağlanılamadı: {e}")
        return cls._thread_local.connection

    @classmethod
    def init(cls):
        """
        Initializes the DB path and prepares the database file for the main thread.
        """
        cls.db_path = join(globals.BASE_PATH, DATABASE_FILE_NAME)
        if globals.FIRST_RUN:
            if exists(cls.db_path):
                delete_file(cls.db_path)
        
        # Get a connection for the main thread and set up the table
        main_conn = cls.get_thread_safe_connection()
        cursor = main_conn.cursor()
        
        if globals.FIRST_RUN:
            cursor.execute(TABLE_CREATION_QUERY)
            logger.verbose("Veritabanı ilk çalıştırma için hazırlandı.")
        else:
            cursor.execute(TABLE_CHECK_QUERY)
            result = cursor.fetchone()
            if not result or result[0] != "files":
                logger.fail(
                    f"Veritabanı bozuk. '{DATABASE_FILE_NAME}' dosyasını silip tekrar başlatın. Silme işlemi sonrasında tüm dosyalar yeniden indirilir."
                )
        cursor.close()

    @classmethod
    def check_file_status(cls, file_id: int, cursor: sqlite3.Cursor):
        """
        Checks the database for a given file_id using the provided cursor.
        """
        try:
            logger.debug(f"file_id ile sorgu çalıştırılıyor: {file_id}")
            cursor.execute(SELECT_FILE_BY_ID_QUERY, (file_id,))
            file = cursor.fetchone()
            logger.debug(f"file_id {file_id} için sorgu sonucu: {file}")
            
            if file:
                deleted, id = file
                if file_id != id:
                    logger.fail(
                        "Eş zamanlı erişim nedeniyle bir race condition oluştu. Veritabanından gelen bilgi bu dosyaya ait değil. Geliştiriciye bildirin."
                    )
                if deleted:
                    return FILE_STATUS.DELETED
                else:
                    return FILE_STATUS.EXISTS
            else:
                return FILE_STATUS.NEW
        except sqlite3.InterfaceError as e:
            logger.error(f"SQLite InterfaceError for file_id {file_id}: {e}")
            raise
        except sqlite3.Error as e:
            logger.error(f"SQLite Hatası for file_id {file_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"check_file_status fonksiyonunda beklenmeyen hata for file_id {file_id}: {e}")
            raise

    @classmethod
    def add_file(cls, id: int, path: str):
        cls.to_add.put(FileRecord(id, path))

    @classmethod
    def apply_changes_and_close(cls):
        """Closes the connection for the current thread."""
        if hasattr(cls._thread_local, "connection"):
            conn = cls._thread_local.connection
            conn.commit()
            conn.close()
            logger.debug(f"Thread {threading.get_ident()} closed its DB connection.")
            del cls._thread_local.connection

    @classmethod
    def get_new_cursor(cls):
        """Gets a new cursor from the thread-safe connection."""
        conn = cls.get_thread_safe_connection()
        return conn.cursor()

    @classmethod
    @logger.speed_measure("Veritabanına yazma", False, False)
    def write_records(cls):
        """Writes all queued records to the DB using the main thread's connection."""
        cursor = cls.get_new_cursor()
        while not cls.to_add.empty():
            record = cls.to_add.get()
            if exists(record.path):
                with open(record.path, "rb") as file:
                    hash_val = crc32(file.read())
                    try:
                        cursor.execute(FILE_INSERTION_QUERY, (record.id, record.path, hash_val))
                    except Exception as e:
                        logger.fail(str(e) + "\n Dosya yolu: " + record.path)
                logger.new_file(record.path)
            else:
                logger.warning(f"Veritabanına yazılacak {record.path} dosyası bulunamadı. Veri tabanına yazılmayacak")
        
        # apply_changes_and_close is called from main.py after this