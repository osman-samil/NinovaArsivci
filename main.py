# getpass hiçbir şey göstermeden şifre girilmesine izin verir ama pwinput *** gösterir
# pwinput daha iyi görünür ama standart kütüphanede değil

# ---IMPORTS---
try:
    from src import logger
    from src.login import login
    from src.kampus import get_course_list, filter_courses
    from src.task_handler import start_tasks
    from src.db_handler import DB
    from src import globals
except ModuleNotFoundError:
    print(
        "HATA! Kütüphaneler yüklenemedi. 'src' klasörü silinmiş veya yeri değişmiş olabilir."
    )
    exit()

# ---MAIN---
@logger.speed_measure("Program", False)
def main():
    DB.init()
    courses = get_course_list()
    courses = filter_courses(courses)
    start_tasks(courses)

    DB.write_records()


# ---Program yönlendirme kodu---
if __name__ == "__main__":
    globals.init_globals()
    main()