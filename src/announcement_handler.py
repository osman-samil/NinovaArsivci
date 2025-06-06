from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.kampus import Course
    import requests

from os.path import join, exists
import os
import re
from bs4 import BeautifulSoup

from src import logger, globals
from src.login import URL
from src.utils import sanitize_filename, fix_turkish_characters

DUYURULAR_URL_EXTENSION = "/Duyurular"

def _dump_html_for_debug(course_crn: str, response: requests.Response, is_detail_page=False, detail_id=""):
    """Saves the raw HTML of a page to the central debug_output folder."""
    page_type = "Detail" if is_detail_page else "List"
    detail_suffix = f"_{detail_id}" if is_detail_page else ""
    debug_filename = f"DEBUG_{page_type}_Duyurular_CRN_{course_crn}{detail_suffix}.html"
    debug_filepath = join(globals.DEBUG_PATH, debug_filename)
    try:
        # Use response's apparent encoding to save the debug file accurately
        encoding = response.encoding if response.encoding else 'iso-8859-9'
        with open(debug_filepath, "w", encoding=encoding) as f:
            f.write(response.text)
        logger.warning(f"Duyuru {page_type} sayfası yapısı anlaşılamadı. HTML incelenmek üzere kaydedildi: {debug_filepath}")
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
        announcements_list_url = URL + course.link + DUYURULAR_URL_EXTENSION
        logger.verbose(f"Duyuru listesi sayfası alınıyor: {announcements_list_url}")
        response = session.get(announcements_list_url)
        response.raise_for_status()
        
        _parse_and_save_announcements(response, announcements_path, course.crn, session)

    except Exception as e:
        logger.error(f"'{course.code}' dersi için duyurular alınırken hata oluştu: {e}")


def _parse_and_save_announcements(list_page_response: requests.Response, destination_folder: str, course_crn: str, session: requests.Session):
    """
    Parses the announcement list page, visits each announcement's detail page,
    and saves the full content.
    """
    list_soup = BeautifulSoup(list_page_response.text, "lxml")
    announcements_found = 0

    # Step 1: Get all announcement blocks from the list page
    announcement_items = list_soup.select("div.duyuruGoruntule")

    if not announcement_items:
        logger.warning(f"CRN {course_crn} için 'div.duyuruGoruntule' yapısında duyuru bulunamadı.")
        _dump_html_for_debug(course_crn, list_page_response)
        return

    logger.verbose(f"{len(announcement_items)} adet potansiyel duyuru linki bulundu.")

    month_map = {
        "Ocak": "01", "Şubat": "02", "Mart": "03", "Nisan": "04", "Mayıs": "05", "Haziran": "06",
        "Temmuz": "07", "Ağustos": "08", "Eylül": "09", "Ekim": "10", "Kasım": "11", "Aralık": "12"
    }

    for item in announcement_items:
        try:
            title_link_element = item.select_one("h2 a")
            if not title_link_element or not title_link_element.has_attr('href'):
                continue

            # Step 2: Visit the detail page for each announcement
            detail_page_url = URL + title_link_element['href']
            announcement_id = detail_page_url.split('/')[-1]
            logger.verbose(f"Duyuru detay sayfası ziyaret ediliyor: {detail_page_url}")
            
            detail_response = session.get(detail_page_url)
            detail_response.raise_for_status()
            detail_soup = BeautifulSoup(detail_response.text, 'lxml')

            # Step 3: Parse the content from the detail page
            # The main content area is within div.orta > div.ic
            container = detail_soup.select_one("div.orta > div.ic")
            if not container:
                _dump_html_for_debug(course_crn, detail_response, is_detail_page=True, detail_id=announcement_id)
                continue

            # The title is in an H1 tag. The rest of the content is in a 'duyuruGoruntule' block.
            title_element = container.select_one("h1")
            announcement_block = container.select_one("div.duyuruGoruntule")

            # If the main block is missing, we can't proceed.
            if not announcement_block:
                logger.verbose(f"Duyuru {announcement_id} detay sayfasında 'div.duyuruGoruntule' bloğu bulunamadı.")
                _dump_html_for_debug(course_crn, detail_response, is_detail_page=True, detail_id=announcement_id)
                continue

            # Now, find the elements relative to the announcement_block
            date_and_author_spans = announcement_block.select("div.tarih > span.tarih")
            content_element = announcement_block.select_one("div.icerik")

            if not all([title_element, len(date_and_author_spans) >= 2, content_element]):
                logger.verbose(f"Duyuru {announcement_id} detay sayfası beklenen yapıda değil, atlanıyor.")
                _dump_html_for_debug(course_crn, detail_response, is_detail_page=True, detail_id=announcement_id)
                continue

            # Fix Turkish characters for all text fields
            title = fix_turkish_characters(title_element.get_text(strip=True))
            date_str_fixed = fix_turkish_characters(date_and_author_spans[0].get_text(strip=True))
            author = fix_turkish_characters(date_and_author_spans[1].get_text(strip=True))
            content = fix_turkish_characters(content_element.get_text("\n", strip=True))

            # --- Date parsing for creating a sortable filename (YYYY-MM-DD) ---
            formatted_date = "Tarih-Bulunamadı"
            try:
                parts = date_str_fixed.split()
                if len(parts) >= 3:
                    day = parts[0].zfill(2)
                    month_name = parts[1]
                    year = parts[2]
                    month_num = month_map.get(month_name, "00")
                    formatted_date = f"{year}-{month_num}-{day}"
            except Exception as e:
                logger.warning(f"Tarih ayrıştırılamadı: '{date_str_fixed}'. Ham tarih kullanılacak. Hata: {e}")
                formatted_date = re.sub(r'[\s:.]', '_', date_str_fixed)

            sanitized_title = sanitize_filename(title)
            filename = f"{formatted_date} - {sanitized_title}.txt"
            full_path = join(destination_folder, filename)

            if not exists(full_path):
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(f"Başlık: {title}\n")
                    f.write(f"Yayınlayan: {author}\n")
                    f.write(f"Tarih: {date_str_fixed}\n")
                    f.write("="*40 + "\n\n")
                    f.write(content)
                logger.new_file(full_path)
                announcements_found += 1
            else:
                logger.verbose(f"Duyuru '{full_path}' zaten mevcut. Atlanıyor.")

        except Exception as e:
            # Check if title_link_element exists before trying to access its attributes in the error message
            error_url_part = "Bilinmeyen URL"
            if 'title_link_element' in locals() and title_link_element and title_link_element.has_attr('href'):
                error_url_part = title_link_element['href']
            logger.warning(f"Bir duyuru ({error_url_part}) işlenirken hata oluştu, atlanıyor: {e}")
            continue

    if announcements_found == 0 and announcement_items:
        logger.verbose(f"'{course_crn}' için işlem tamamlandı ancak hiçbir yeni duyuru dosyası oluşturulmadı (muhtemelen hepsi zaten vardı).")