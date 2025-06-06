from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.kampus import Course
    import requests

from os.path import join, exists
import os
from bs4 import BeautifulSoup

from src import logger, globals
from src.login import URL
from src.utils import sanitize_filename

DUYURULAR_URL_EXTENSION = "/Duyurular"

def _dump_html_for_debug(course_crn: str, raw_html: str):
    """Saves the raw HTML of the announcements page to the central debug_output folder."""
    debug_filename = f"DEBUG_Duyurular_CRN_{course_crn}.html"
    debug_filepath = join(globals.DEBUG_PATH, debug_filename)
    try:
        with open(debug_filepath, "w", encoding="utf-8") as f:
            f.write(raw_html)
        logger.warning(f"Duyuru yapısı anlaşılamadı. Sayfanın HTML'i incelenmek üzere şu dosyaya kaydedildi: {debug_filepath}")
    except Exception as e:
        logger.error(f"Debug HTML dosyası kaydedilirken hata oluştu: {e}")


def archive_announcements_for_course(course: Course, session: requests.Session):
    """
    Fetches, parses, and saves all announcements for a given course.
    """
    logger.verbose(f"'{course.code} (CRN: {course.crn})' için duyurular arşivleniyor...")

    unique_folder_name = f"{course.code} (CRN {course.crn})"
    sanitized_folder_name = sanitize_filename(unique_folder_name)
    course_base_path = join(globals.BASE_PATH, sanitized_folder_name)
    
    announcements_path = join(course_base_path, sanitize_filename("Duyurular"))
    os.makedirs(announcements_path, exist_ok=True)

    try:
        announcements_url = URL + course.link + DUYURULAR_URL_EXTENSION
        logger.verbose(f"Duyuru sayfası alınıyor: {announcements_url}")
        response = session.get(announcements_url)
        response.raise_for_status()
        raw_html = response.content.decode("utf-8")
        
        _parse_and_save_announcements(raw_html, announcements_path, course.crn)

    except Exception as e:
        logger.error(f"'{course.code}' dersi için duyurular alınırken hata oluştu: {e}")


def _parse_and_save_announcements(raw_html: str, destination_folder: str, course_crn: str):
    soup = BeautifulSoup(raw_html, "lxml")
    announcements_found = 0

    announcement_container = soup.select_one("#ctl00_ContentPlaceHolder1_pnlDuyurular") 
    
    if announcement_container:
        logger.verbose("Potansiyel duyuru konteyneri bulundu. İçerik işleniyor...")
        
        items = announcement_container.find_all("div", class_="col-md-12") # GUESS
        logger.verbose(f"{len(items)} adet potansiyel duyuru öğesi bulundu.")

        if not items:
             _dump_html_for_debug(course_crn, raw_html)
             return

        for item in items:
            try:
                title_element = item.select_one("h4") # GUESS
                date_element = item.select_one(".text-muted") # GUESS
                content_element = item.select_one(".panel-body") # GUESS

                if not all([title_element, date_element, content_element]):
                    logger.verbose("Duyuru öğesi beklenen yapıda değil, atlanıyor.")
                    continue

                title = title_element.get_text(strip=True)
                date_str_raw = date_element.get_text(strip=True) 
                date_str = "01.01.2024" # Placeholder
                content = content_element.get_text("\n", strip=True)
                
                try:
                    day, month, year = date_str.split('.')
                    formatted_date = f"{year}-{month}-{day}"
                except:
                    formatted_date = date_str.replace('.', '-')

                sanitized_title = sanitize_filename(title)
                filename = f"{formatted_date} - {sanitized_title}.txt"
                full_path = join(destination_folder, filename)

                if not exists(full_path):
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(f"Başlık: {title}\n")
                        f.write(f"Tarih: {date_str_raw}\n")
                        f.write("="*40 + "\n\n")
                        f.write(content)
                    logger.new_file(full_path)
                    announcements_found += 1
                else:
                    logger.verbose(f"Duyuru '{full_path}' zaten mevcut. Atlanıyor.")

            except Exception as e:
                logger.warning(f"Bir duyuru öğesi işlenirken hata oluştu, atlanıyor: {e}")
                continue
    else:
        logger.warning("Duyuru konteyneri (selector: #ctl00_ContentPlaceHolder1_pnlDuyurular) bulunamadı.")
        _dump_html_for_debug(course_crn, raw_html)

    if announcements_found == 0:
        logger.verbose(f"'{course_crn}' için işlem tamamlandı ancak hiçbir yeni duyuru dosyası oluşturulmadı.")