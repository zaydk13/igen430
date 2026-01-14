import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
from datetime import datetime
import hashlib
import re


def _safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name:
        h = hashlib.sha1(url.encode('utf-8')).hexdigest()
        return f'image_{h}.jpg'
    # remove query strings and unsafe chars
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    return name


def download_images_from_linked_pages(url, output_folder='downloaded_images', same_domain=True, max_links=None, dated_subfolder=True):
    """Download images from the root page and from pages linked on the root page.

    Behavior:
      - Downloads images found directly on the root URL (prefixed with `root_`).
      - Finds `<a>` links on the root page, visits each linked page (same domain
        by default), and downloads the images found there (prefixed with link index).
    """
    session = requests.Session()
    base_output = Path(output_folder)
    if dated_subfolder:
        dated_name = datetime.now().strftime('images_%Y%m%d_%H%M%S')
        output_path = base_output / dated_name
    else:
        output_path = base_output
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching root URL {url}: {e}")
        return

    base_netloc = urlparse(url).netloc
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Download images on the root page itself
    root_imgs = soup.find_all('img')
    print(f"Found {len(root_imgs)} images on root page {url}")
    for i, img_tag in enumerate(root_imgs, start=1):
        img_src = img_tag.get('src') or img_tag.get('data-src')
        if not img_src:
            continue
        img_url = urljoin(url, img_src)
        try:
            img_resp = session.get(img_url, stream=True, timeout=10)
            img_resp.raise_for_status()
            name = _safe_filename_from_url(img_url)
            filename = f"root_{i}_{name}"
            filepath = output_path / filename
            with open(filepath, 'wb') as f:
                for chunk in img_resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            print(f"  Saved root image: {filename}")
        except requests.RequestException as e:
            print(f"  Error downloading root image {img_url}: {e}")

    # Now find links and download images from linked pages
    a_tags = soup.find_all('a', href=True)
    print(f"Found {len(a_tags)} links on {url}")

    link_count = 0
    for a in a_tags:
        link_href = a['href']
        link_url = urljoin(url, link_href)
        link_netloc = urlparse(link_url).netloc
        if same_domain and link_netloc != base_netloc:
            continue

        try:
            link_resp = session.get(link_url, stream=True, timeout=10)
            link_resp.raise_for_status()
            content_type = link_resp.headers.get('Content-Type', '')
        except requests.RequestException as e:
            print(f"Error fetching linked page {link_url}: {e}")
            continue

        # If the link is directly to an image (content-type starts with image/),
        # download it directly instead of treating it as an HTML page.
        if content_type.startswith('image/') or Path(urlparse(link_url).path).suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif'):
            try:
                # link_resp already opened with stream=True; reuse it
                name = _safe_filename_from_url(link_url)
                filename = f"link_{link_count+1}_direct_{name}"
                filepath = output_path / filename
                with open(filepath, 'wb') as f:
                    for chunk in link_resp.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                print(f"  Downloaded direct image link: {filename}")
            except requests.RequestException as e:
                print(f"  Error downloading direct image {link_url}: {e}")
            # we continue to next link; don't try to parse as HTML
            link_count += 1
            if max_links and link_count > max_links:
                break
            continue

        link_count += 1
        if max_links and link_count > max_links:
            break

        link_soup = BeautifulSoup(link_resp.text, 'html.parser')
        img_tags = link_soup.find_all('img')
        print(f"  Link {link_count}: {link_url} — {len(img_tags)} images")

        for idx, img_tag in enumerate(img_tags, start=1):
            img_src = img_tag.get('src') or img_tag.get('data-src')
            if not img_src:
                continue
            img_url = urljoin(link_url, img_src)
            try:
                img_resp = session.get(img_url, stream=True, timeout=10)
                img_resp.raise_for_status()
                name = _safe_filename_from_url(img_url)
                filename = f"{link_count}_{idx}_{name}"
                filepath = output_path / filename
                with open(filepath, 'wb') as f:
                    for chunk in img_resp.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                print(f"    Downloaded: {filename}")
            except requests.RequestException as e:
                print(f"    Error downloading {img_url}: {e}")
    # return the folder where images were saved
    return output_path


if __name__ == '__main__':
    html_page_url = "http://10.43.118.3:8000/"
    output_folder = r'C:\Users\Zayd\OneDrive\Documents\IGEN430'
    out = download_images_from_linked_pages(html_page_url, output_folder=output_folder, same_domain=True, max_links=None, dated_subfolder=True)
    print(f"Images downloaded to '{out}'")
