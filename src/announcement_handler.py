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

def archive_announcements_for_course(course: Course, session: requests.Session):
    """
    Fetches, parses, and saves all announcements for a given course.
    """
    logger.verbose(f"'{course.code} (CRN: {course.crn})' için duyurular arşivleniyor...")

    # Create a unique folder name using the course code and CRN.
    unique_folder_name = f"{course.code} (CRN {course.crn})"
    sanitized_folder_name = sanitize_filename(unique_folder_name)
    course_base_path = join(globals.BASE_PATH, sanitized_folder_name)
    
    announcements_path = join(course_base_path, sanitize_filename("Duyurular"))
    os.makedirs(announcements_path, exist_ok=True)

    try:
        # Fetch the announcements page
        announcements_url = URL + course.link + DUYURULAR_URL_EXTENSION
        response = session.get(announcements_url)
        response.raise_for_status()
        raw_html = response.content.decode("utf-8")
        
        # Parse and save the announcements
        _parse_and_save_announcements(raw_html, announcements_path)

    except Exception as e:
        logger.error(f"'{course.code}' dersi için duyurular alınırken hata oluştu: {e}")


def _parse_and_save_announcements(raw_html: str, destination_folder: str):
    try:
        soup = BeautifulSoup(raw_html, "lxml")
        announcement_table = soup.select_one("#ctl00_ContentPlaceHolder1_gdvDuyurular")

        if not announcement_table:
            logger.verbose("Bu derste duyuru tablosu bulunamadı veya hiç duyuru yok.")
            return

        rows = announcement_table.find_all("tr")
        if len(rows) <= 1: # Only a header row or empty
            logger.verbose("Duyuru tablosu boş.")
            return
            
        logger.verbose(f"Duyuru tablosunda {len(rows) - 1} adet satır bulundu, işleniyor...")
            
    except Exception as e:
        logger.warning(f"Duyurular ayrıştırılırken bir hata oluştu: {e}")
        return

    # Skip header row by starting loop at index 1
    # Each announcement is expected to be two rows: one for info, one for content.
    i = 1
    while i < len(rows) - 1: # Ensure there's a row after the current one
        try:
            info_row = rows[i]
            content_row = rows[i+1]

            # Heuristic: An info row has 2 cells, a content row has 1 cell with colspan.
            info_cells = info_row.find_all("td")
            content_cell = content_row.find("td")

            if len(info_cells) >= 2 and content_cell and content_cell.get('colspan'):
                logger.verbose(f"Potansiyel duyuru başlığı satırı {i}'de bulundu.")
                title = info_cells[0].get_text(strip=True)
                date_str = info_cells[1].get_text(strip=True)
                content = content_cell.get_text("\n", strip=True)
                
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
                        f.write(f"Tarih: {date_str}\n")
                        f.write("="*40 + "\n\n")
                        f.write(content)
                    logger.new_file(full_path)
                else:
                    logger.verbose(f"Duyuru '{full_path}' zaten mevcut. Atlanıyor.")
                
                i += 2 # Successfully processed an announcement, skip both rows
            else:
                # This row is not part of a standard announcement, skip it.
                i += 1
        except Exception as e:
            logger.warning(f"Bir duyuru işlenirken hata oluştu (satır {i}), atlanıyor: {e}")
            i += 1 # Move to the next row to avoid an infinite loop