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
    logger.verbose(f"'{course.code}' için duyurular arşivleniyor...")

    # Create a dedicated "Duyurular" folder for the course
    course_base_path = join(globals.BASE_PATH, sanitize_filename(course.code))
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
    """
    Parses the HTML of the announcements page and saves each announcement as a .txt file.
    """
    try:
        soup = BeautifulSoup(raw_html, "lxml")
        rows = soup.select("table.data tr")
        if not rows:
            return
    except Exception as e:
        logger.warning(f"Duyurular ayrıştırılırken bir hata oluştu: {e}")
        return

    # Each announcement spans two <tr> tags. We skip the header row and iterate.
    i = 1
    while i < len(rows):
        try:
            # The row with title and date
            info_row = rows[i]
            cols = info_row.find_all("td")
            if len(cols) < 2:
                i += 1
                continue

            title = cols[0].get_text(strip=True)
            date_str = cols[1].get_text(strip=True) # Format: DD.MM.YYYY
            
            # Reformat date for better file sorting: YYYY-MM-DD
            try:
                day, month, year = date_str.split('.')
                formatted_date = f"{year}-{month}-{day}"
            except:
                formatted_date = date_str.replace('.', '-') # Fallback

            # The next row contains the announcement content
            i += 1
            if i >= len(rows):
                break
            content_row = rows[i]
            content = content_row.get_text("\n", strip=True)

            # Create and sanitize filename
            sanitized_title = sanitize_filename(title)
            filename = f"{formatted_date} - {sanitized_title}.txt"
            full_path = join(destination_folder, filename)

            # Save the announcement if it doesn't already exist to preserve the archive
            if not exists(full_path):
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(f"Başlık: {title}\n")
                    f.write(f"Tarih: {date_str}\n")
                    f.write("="*40 + "\n\n")
                    f.write(content)
                logger.new_file(full_path)
            else:
                logger.verbose(f"Duyuru '{full_path}' zaten mevcut. Atlanıyor.")

        except Exception as e:
            logger.warning(f"Bir duyuru işlenirken hata oluştu, atlanıyor: {e}")
        finally:
            # Move to the next announcement (each announcement takes 2 rows)
            i += 1 