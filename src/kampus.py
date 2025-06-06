from __future__ import annotations
from typing import TYPE_CHECKING

from collections import namedtuple
from bs4 import BeautifulSoup

from src import globals
from src.login import URL
from src import logger

Course = namedtuple("Course", "code name crn link")
COURSE_TITLE_OFFSET = 8


# Kurs listesi döner: kurs kodu, kurs adı ve kursa ait ninova linki olan Course nesneleri
def get_course_list() -> tuple[Course]:
    global URL
    course_list = []
    processed_crns = set() # Use a set to track processed CRNs for uniqueness
    session = globals.SESSION

    response = session.get(URL + "/Kampus1")
    raw_html = response.content.decode("utf-8")
    page = BeautifulSoup(raw_html, "lxml")

    crn_link_tags = page.select('.menuErisimAgaci a[href*="/Sinif/"]')
    
    logger.verbose(f"Erişim Ağacı içinde {len(crn_link_tags)} adet ders bölümü (CRN) linki bulundu.")

    if not crn_link_tags:
        logger.warning("Erişim Ağacı'nda hiçbir ders bölümü (CRN) bulunamadı.")
        return tuple()

    for crn_link_tag in crn_link_tags:
        try:
            link_text = crn_link_tag.get_text(strip=True)
            
            if not link_text.startswith("CRN:"):
                logger.verbose(f"Standart olmayan CRN linki atlanıyor: '{link_text}'")
                continue

            crn = link_text.replace("CRN:", "").strip()

            if crn in processed_crns:
                logger.verbose(f"Yinelenen CRN {crn} atlanıyor.")
                continue
            processed_crns.add(crn)

            link = crn_link_tag["href"].strip()
            
            ders_info_page = session.get(URL + link + "/SinifBilgileri").content.decode("utf-8")
            ders_info_soup = BeautifulSoup(ders_info_page, "lxml")
            
            ders_info_table = ders_info_soup.find(class_="formAbetGoster")
            if not ders_info_table:
                logger.warning(f"CRN {crn} için sınıf bilgileri tablosu bulunamadı, atlanıyor.")
                continue

            ders_info_rows = ders_info_table.select("tr")
            
            code = ders_info_rows[0].select("td")[1].text.strip()
            name = ders_info_rows[1].select("td")[2].text.strip()

            course_list.append(Course(code, name, crn, link))
            logger.verbose(f"Bulunan ders: {code} (CRN: {crn}) - {name}")

        except Exception as e:
            logger.warning(f"Bir ders/CRN ayrıştırılırken hata oluştu, atlanıyor: {e}")

    return tuple(course_list)


def filter_courses(courses: tuple[Course]) -> tuple[Course]:
    for i, course in enumerate(courses):
        print(f"{i} - {course.code} (CRN: {course.crn}) | {course.name}")
        
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
            indirilecek_dersler += f"{course.code} (CRN: {course.crn}), "
        print(f"{indirilecek_dersler.strip(', ')} dersleri indirilecek.")
        return courses_filtered
    else:
        print("Tüm dersler indirilecek.")
        return courses