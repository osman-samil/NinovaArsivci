from collections import namedtuple
import sqlite3
from os.path import join, exists
from os import remove as delete_file
from enum import Enum
from zlib import crc32
from queue import Queue

from src import logger
from src import globals

import logging

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
    connection: sqlite3.Connection
    to_add = Queue()
    db_path: str

    @classmethod
    def init(cls):
        """
        Veritabanına bağlanır ve tablo yapısını kontrol eder ve oluşturur
        Eğer FIRST_RUN bayrağı kontrol edilirse ve bir DB dosyası varsa, zorla indirme aktif demektir
        """
        cls.db_path = join(globals.BASE_PATH, DATABASE_FILE_NAME)
        if globals.FIRST_RUN:
            try:
                delete_file(cls.db_path)
            except:
                pass
        cls.connect()
        cursor = cls.connection.cursor()
        if globals.FIRST_RUN:
            cursor.execute(TABLE_CREATION_QUERY)
            logger.verbose("Veritabanı ilk çalıştırma için hazırlandı.")
        else:
            cursor.execute(TABLE_CHECK_QUERY)
            if cursor.fetchone()[0] != "files":
                logger.fail(
                    f"Veritabanı bozuk. '{DATABASE_FILE_NAME}' dosyasını silip tekrar başlatın. Silme işlemi sonrasında tüm dosyalar yeniden indirilir."
                )

        cursor.close()

    @classmethod
    def connect(cls):
        """
        db_path sınıf niteliğini kullanarak DB'ye bağlanır
        Sınıfın bağlantı nesnesini ayarlar, hiçbir şey döndürmez
        """
        try:
            cls.connection = sqlite3.connect(cls.db_path, check_same_thread=False)
            logger.debug("Veritabanına bağlandı.")
        except:
            logger.fail("Veritabanına bağlanılamadı.")

    # file_id alır, veritabanından durumu bulur ve döner
    # file_id, dosya URL'sinin sonu (soru işareti sonrası - soru işareti ve 'g' dahil değil)
    @classmethod
    def check_file_status(cls, file_id: int, cursor: sqlite3.Cursor):
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

    # indirme sonrası çağrılmalı
    @classmethod
    def add_file(cls, id: int, path: str):
        cls.to_add.put(FileRecord(id, path))

    @classmethod
    def apply_changes_and_close(cls):
        cls.connection.commit()
        cls.connection.close()

    @classmethod
    def get_new_cursor(cls):
        return cls.connection.cursor()

    @classmethod
    @logger.speed_measure("Veritabanına yazma", False, False)
    def write_records(cls):
        cursor = cls.get_new_cursor()
        while not cls.to_add.empty():
            record = cls.to_add.get()
            if exists(record.path):
                with open(record.path, "rb") as file:
                    hash = crc32(file.read())
                    try:
                        cursor.execute(FILE_INSERTION_QUERY, (record.id, record.path, hash))
                    except Exception as e:
                        logger.fail(str(e) + "\n Dosya yolu: " + record.path)
                logger.new_file(record.path)
            else:
                logger.warning(f"Veritabanına yazılacak {record.path} dosyası bulunamadı. Veri tabanına yazılmayacak")

        cls.apply_changes_and_close()