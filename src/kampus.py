from __future__ import annotations
from typing import TYPE_CHECKING

from collections import namedtuple
from bs4 import BeautifulSoup

from src import globals
from src.login import URL
from src import logger

Course = namedtuple("Course", "code name link")
COURSE_TITLE_OFFSET = 8


# Kurs listesi döner: kurs kodu, kurs adı ve kursa ait ninova linki olan Course nesneleri
def get_course_list() -> tuple[Course]:
    global URL
    course_list = []

    session = globals.SESSION

    page = BeautifulSoup(session.get(URL + "/Kampus1").content.decode("utf-8"), "lxml")

    erisim_agaci = page.select(".menuErisimAgaci>ul>li")
    for element in erisim_agaci:
        link = element.find("a")["href"]
        ders_info = BeautifulSoup(
            session.get(URL + link + "/SinifBilgileri").content.decode("utf-8"), "lxml"
        )
        ders_info = ders_info.find(class_="formAbetGoster")
        ders_info = ders_info.select("tr")
        code = ders_info[0].select("td")[1].text.strip()
        name = ders_info[1].select("td")[2].text.strip()

        course_list.append(Course(code, name, link))

    return tuple(course_list)


def filter_courses(courses: tuple[Course]) -> tuple[Course]:
    for i, course in enumerate(courses):
        print(f"{i} - {course.code} | {course.name}")
    user_response = input(
        """İndirmek istediğiniz derslerin numaralarını, aralarında boşluk bırakarak girin
Tüm dersleri indirmek için boş bırakın ve enter'a basın
    > """
    )
    user_response = user_response.strip()
    if user_response:
        courses_filtered = list()
        selected_indexes_raw = user_response.split(" ")
        for selected_index in selected_indexes_raw:
            try:
                index = int(selected_index)
                courses_filtered.append(courses[index])
            except ValueError:
                logger.warning(
                    f"Girilen '{selected_index}' bir sayı değil. Yok sayılacak."
                )
            except IndexError:
                logger.warning(
                    f"Girilen '{selected_index}' herhangi bir kursun numarası değil. Yok sayılacak."
                )
        courses_filtered = tuple(courses_filtered)

        indirilecek_dersler = ""
        for course in courses_filtered:
            indirilecek_dersler += course.name + ", "
        print(f"{indirilecek_dersler} dersleri indirilecek.")
        return courses_filtered
    else:
        print("Tüm dersler indirilecek.")
        return courses