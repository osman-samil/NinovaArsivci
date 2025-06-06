from typing import TYPE_CHECKING
from os.path import exists, join
from os import getcwd, makedirs
from tkinter.filedialog import askdirectory
try:
    from pwinput import pwinput as getpass
except:
    from getpass import getpass
import copy

from src import logger
from src.argv_handler import get_args
from src.login import login


BASE_PATH: str = None
FIRST_RUN: bool = None
SESSION = None
ARGV: dict = None
PROJECT_ROOT: str = None
DEBUG_PATH: str = None


def init_globals():
    global BASE_PATH, FIRST_RUN, SESSION, ARGV, PROJECT_ROOT, DEBUG_PATH
    
    # --- NEW: Define project root and debug path ---
    PROJECT_ROOT = getcwd()
    DEBUG_PATH = join(PROJECT_ROOT, "debug_output")
    makedirs(DEBUG_PATH, exist_ok=True) # Create the debug folder if it doesn't exist
    # --- END NEW ---

    ARGV = _get_argv_dict()
    logger._DEBUG, logger._VERBOSE = _get_debug_verbose()
    BASE_PATH = _get_directory()
    FIRST_RUN = _get_first_run()
    SESSION = _get_session()


def _get_argv_dict():
    """
    Komut satırı argümanlarını python dict olarak döner
    """
    return get_args(d=1, u=2, debug=0, verbose=0)

def _get_debug_verbose():
    return ("debug" in ARGV, "verbose" in ARGV)

def _get_directory():
    """
    Komut satırından dizini alır, yoksa klasör dialogu gösterir\n
    Dönüş yolunun mevcut olduğunu garanti eder, mevcut değilse hata verir\n
    Son kullanılan dizini almak için '.last_dir' dosyasına erişir
    """

    # Dosyadan son seçilen dizini al
    try:
        with open(join(getcwd(), ".last_dir"), "r", encoding="utf-8") as default_dir_file:
            default_dir = default_dir_file.read().strip()
    except:
        default_dir = getcwd()

    if "d" in ARGV:
        if exists(ARGV["d"][0]):
            # Komut satırından indirme dizinini al
            download_directory = ARGV["d"][0]
        else:
            logger.warning(
                f"-d parametresi ile verilen {ARGV['d'][0]} klasörü bulunamadı."
            )
            download_directory = askdirectory(
                initialdir=default_dir, title="Ninova Arşivci - İndirme klasörü seçin"
            )
    else:
        download_directory = askdirectory(
            initialdir=default_dir, title="Ninova Arşivci - İndirme klasörü seçin"
        )

    if not exists(download_directory):
        logger.fail(f"Verilen '{download_directory}' geçerli bir klasör değil!")

    try:
        # Dizini UTF-8 kodlaması ile dosyaya yaz
        with open(join(getcwd(), ".last_dir"), "w", encoding="utf-8") as default_dir_file:
            default_dir_file.write(download_directory)
    except Exception as e:
        logger.warning(f"Son seçilen dizini kaydederken hata oluştu: {e}")

    return download_directory

def _get_first_run():
    """
    Seçilen dizinde bu programın ilk kez çalışıp çalışmadığını kontrol eder (veritabanı dosyasına bakarak)
    """
    if BASE_PATH:
        first_run = (not exists(join(BASE_PATH, "ninova_arsivci.db"))) or ("force" in ARGV)
        return first_run
    else:
        logger.fail("Klasör seçilmemiş. get_directory() fonksiyonu ile BASE_PATH değişkeni ayarlanmalı! Geliştiriciye bildirin!")

def _get_session():
    """
    Komut satırından kullanıcı adı ve şifre alır, yoksa kullanıcıdan istenir\n
    Eğer kullanıcı adı veya şifre yanlış ise
    """
    while True:
        if "u" in ARGV:
            try:
                username, password = ARGV["u"]
            except ValueError:
                logger.warning("Kullanıcı bilgileri yeterli değil. Tekrar deneyin.")
                del ARGV["u"]
                continue
        else:
            username = input("Kullanıcı adı (@itu.edu.tr olmadan): ")
            password = getpass("Şifre: ")
    
        print("Giriş yapılıyor...\n")
        try:
            session = login( (username, password) )
            return session
        except PermissionError:
            logger.warning("Kullanıcı adı veya şifre hatalı. Tekrar deneyin.")
            try:
                del ARGV["u"]
            except:
                pass

def session_copy():
    return copy.copy(SESSION)