import os
import shutil
import re
import datetime
import subprocess
import urllib.parse
import time
import sys

SOURCE_DIR = "/data/obsidian/jerthefox"
REPO_ROOT = "/app/site-repo"

# Пути назначения в Hugo
DEST_CONTENT_DIR = os.path.join(REPO_ROOT, "content", "blog")
DEST_IMG_DIR = os.path.join(REPO_ROOT, "static", "images", "blog")
DEST_FILE_DIR = os.path.join(REPO_ROOT, "static", "files", "blog")

HUGO_IMG_PREFIX = "/images/blog/"
HUGO_FILE_PREFIX = "/files/blog/"

# Настройки триггеров
TRIGGER_WORDS = ["публикация", "#публикация"]
IGNORED_PREFIXES = ["публикация", "тип/", "статус/", "#публикация", "#тип/", "#статус/"]

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
FILE_EXTENSIONS = {'.pdf', '.docx', '.doc', '.zip', '.txt', '.xls', '.xlsx', '.pptx'}

# Глобальная карта ассетов: filename -> full_path
ASSET_MAP = {}

def build_asset_map():
    global ASSET_MAP
    ASSET_MAP = {}
    print("Indexing assets...")
    
    for root, dirs, files in os.walk(SOURCE_DIR):
        if ".git" in root: continue
        for file in files:
            ASSET_MAP[file] = os.path.join(root, file)
    
    print(f"Indexed {len(ASSET_MAP)} assets.")

def get_file_date(filepath):
    timestamp = os.path.getmtime(filepath)
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S")

def normalize_content_for_comparison(text):
    return re.sub(r'^date: .*$', '', text, flags=re.MULTILINE)

def extract_frontmatter_and_body(content):
    match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, content

def parse_yaml_tags(yaml_text):
    tags = []
    date = None
    title = None
    
    tag_section_match = re.search(r'^tags:\s*\n((?:[\s-].*\n?)*)', yaml_text, re.MULTILINE)
    if tag_section_match:
        block = tag_section_match.group(1)
        items = re.findall(r'^\s*-\s*(.+)$', block, re.MULTILINE)
        tags = [t.strip().strip('"\'') for t in items]
        
    date_match = re.search(r'^date:\s*(.+)$', yaml_text, re.MULTILINE)
    if date_match:
        date = date_match.group(1).strip()

    title_match = re.search(r'^title:\s*["\']?(.*?)["\']?$', yaml_text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        
    return tags, date, title

def slugify(text):
    """
    Создает URL из названия:
    'Тест Ссылки' -> 'тест-ссылки'
    """
    # Декодируем (убираем %20)
    text = urllib.parse.unquote(text)
    # Lowercase
    text = text.lower().strip()
    # Пробелы в дефисы
    text = re.sub(r'[\s_]+', '-', text)
    # Убираем расширение .md
    text = text.replace('.md', '')
    # Оставляем буквы, цифры, дефис
    text = re.sub(r'[^\w\-]', '', text)
    return text

def copy_asset(filename, dest_dir):
    filename = urllib.parse.unquote(filename)
    
    if filename not in ASSET_MAP:
        return None
    src_path = ASSET_MAP[filename]
    clean_filename = filename.replace(" ", "_")
    dest_path = os.path.join(dest_dir, clean_filename)
    os.makedirs(dest_dir, exist_ok=True)
    
    should_copy = True
    if os.path.exists(dest_path):
        if os.path.getsize(dest_path) == os.path.getsize(src_path):
            should_copy = False     
    if should_copy:
        try:
            shutil.copy2(src_path, dest_path)
        except Exception as e:
            print(f"Error copying asset {filename}: {e}")
            return None
    return clean_filename

def process_links_and_assets(content):
    
    # картинки
    def image_replacer(match):
        full_match = match.group(0)
        is_wiki = full_match.startswith('![[')
        if is_wiki:
            filename = match.group(1).split('|')[0]
            alt_text = filename
        else:
            alt_text = match.group(1) 
            path = match.group(2)
            filename = os.path.basename(urllib.parse.unquote(path))

        ext = os.path.splitext(filename)[1].lower()
        if ext not in IMAGE_EXTENSIONS: return full_match 

        new_filename = copy_asset(filename, DEST_IMG_DIR)
        if new_filename:
            return f'![{alt_text}]({HUGO_IMG_PREFIX}{new_filename})'
        return full_match

    content = re.sub(r'!\[\[(.*?)\]\]', image_replacer, content)
    content = re.sub(r'!\[(.*?)\]\((.*?)\)', image_replacer, content)

    # файлы и внутренние ссылки
    def link_replacer(match):
        full_match = match.group(0)
        is_wiki = full_match.startswith('[[')
        
        if is_wiki:
            # [[Note Name|Alias]]
            inner = match.group(1)
            if '|' in inner:
                target, text = inner.split('|', 1)
            else:
                target, text = inner, inner
        else:
            # [Text](Path)
            text = match.group(1)
            path = match.group(2)
            target = urllib.parse.unquote(path)
            
        filename = os.path.basename(target)
        ext = os.path.splitext(filename)[1].lower()
        
        # если это файл
        if (ext in FILE_EXTENSIONS) or (ext in IMAGE_EXTENSIONS):
            new_filename = copy_asset(filename, DEST_FILE_DIR)
            if new_filename:
                return f'<a href="{HUGO_FILE_PREFIX}{new_filename}" target="_blank">📎 {text}</a>'
            return full_match
            
        # если это ссылка на заметку
        if '://' in target:
            return full_match
            
        clean_target = target.split('#')[0]
        slug = slugify(clean_target)
        return f'[{text}](/blog/{slug}/)'

    content = re.sub(r'(?<!\!)\[\[(.*?)\]\]', link_replacer, content)
    content = re.sub(r'(?<!\!)\[(.*?)\]\((.*?)\)', link_replacer, content)

    return content

def process_tags(content):
    tag_pattern = r'(?:^|\s)(#[\w\d\-_/а-яА-ЯёЁ]+)'
    found_tags = set(re.findall(tag_pattern, content))
    final_tags_list = []
    for tag in found_tags:
        is_technical = False
        clean_tag = tag.strip().replace('#', '')
        for prefix in IGNORED_PREFIXES:
            clean_prefix = prefix.replace('#', '')
            if clean_tag.startswith(clean_prefix):
                is_technical = True
                break
        if not is_technical:
            final_tags_list.append(clean_tag)
        content = content.replace(tag, "")
    return final_tags_list, content

def process_file(filepath, filename):
    if "~" in filename or "sync-conflict" in filename: return False

    with open(filepath, 'r', encoding='utf-8') as f:
        original_content = f.read()

    raw_frontmatter, body = extract_frontmatter_and_body(original_content)

    current_tags = []
    original_date = None
    yaml_title = None
    
    if raw_frontmatter:
        parsed_tags, parsed_date, parsed_title = parse_yaml_tags(raw_frontmatter)
        current_tags.extend(parsed_tags)
        original_date = parsed_date
        yaml_title = parsed_title

    inline_tags = re.findall(r'(?:^|\s)(#[\w\d\-_/а-яА-ЯёЁ]+)', body)
    current_tags.extend(inline_tags)

    is_triggered = False
    for t in current_tags:
        clean_t = t.strip().replace('#', '')
        if 'публикация' == clean_t:
            is_triggered = True
            break
    if not is_triggered: return False

    # ДАТА
    if original_date:
        date_str = original_date
    else:
        date_str = get_file_date(filepath)
        
    # ЗАГОЛОВОК
    # приоритет: YAML > Имя файла
    if yaml_title:
        title = yaml_title
    else:
        title = os.path.splitext(filename)[0]

    # удаление дубликата заголовка
    # удаляем H1 заголовок (# Title), если он стоит в самом начале текста.
    body = re.sub(r'^\s*#\s+.*(\n|$)', '', body.lstrip(), count=1)

    for tag in inline_tags:
        body = body.replace(tag, "")
    
    tags_list, body = process_tags(body)

    final_tags_set = set(tags_list)
    if raw_frontmatter:
        pt, _, _ = parse_yaml_tags(raw_frontmatter)
        for t in pt:
            clean = t.replace('#', '')
            is_tech = False
            for p in IGNORED_PREFIXES:
                if clean.startswith(p.replace('#', '')): is_tech = True; break
            if not is_tech: final_tags_set.add(clean)

    # АССЕТЫ И ССЫЛКИ
    try:
        body = process_links_and_assets(body)
    except Exception as e:
        print(f"Error processing assets in {filename}: {e}")
        return False 

    sorted_tags = sorted(list(final_tags_set))
    tags_yaml = ""
    for t in sorted_tags:
        tags_yaml += f"  - {t}\n"

    new_frontmatter = f"""---
date: {date_str}
params:
  author: JerTheFox
draft: false
tags:
{tags_yaml}title: "{title}"
---
""" # выше указан автор заметки
    final_content = new_frontmatter + body.strip()

    os.makedirs(DEST_CONTENT_DIR, exist_ok=True)
    dest_path = os.path.join(DEST_CONTENT_DIR, filename)

    if os.path.exists(dest_path):
        with open(dest_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        if normalize_content_for_comparison(existing_content) == normalize_content_for_comparison(final_content):
            return True

    print(f"PUBLISHING: {filename}")
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    return True

def git_sync():
    try:
        subprocess.run(["git", "add", "."], cwd=REPO_ROOT, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True)
        if status.stdout.strip():
            print("Detected changes -> Pushing...")
            subprocess.run(["git", "commit", "-m", "Auto-publish from Obsidian"], cwd=REPO_ROOT, check=True)
            subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)
            print("Done.")
    except Exception as e:
        print(f"Git Error: {e}")

def garbage_collector(active_files):
    if not os.path.exists(DEST_CONTENT_DIR): return
    site_files = [f for f in os.listdir(DEST_CONTENT_DIR) if f.endswith(".md")]
    for file in site_files:
        if file == "_index.md": continue
        if file not in active_files:
            print(f"🗑 Delete: {file}")
            os.remove(os.path.join(DEST_CONTENT_DIR, file))

def main():
    print("Obsidian Publisher Service Started")
    if not os.path.exists(os.path.join(REPO_ROOT, ".git")):
         print("Cloning Site Repo...")
         try:
             repo_url = os.environ.get("SITE_REPO_URL")
             if not repo_url: return
             subprocess.run(["git", "clone", repo_url, REPO_ROOT], check=True)
             subprocess.run(["git", "config", "user.email", "bot@bytefox.ru"], cwd=REPO_ROOT)
             subprocess.run(["git", "config", "user.name", "ObsidianBot"], cwd=REPO_ROOT)
         except: return

    while True:
        try:
            print(f"Sync started at {datetime.datetime.now().isoformat()}")
            if os.path.exists(SOURCE_DIR):
                try:
                    subprocess.run(["git", "pull"], cwd=REPO_ROOT, check=True, capture_output=True)
                except: pass

                build_asset_map()
                processed_files_list = []
                for root, dirs, files in os.walk(SOURCE_DIR):
                    for file in files:
                        if file.endswith(".md"):
                            if process_file(os.path.join(root, file), file):
                                processed_files_list.append(file)
                garbage_collector(processed_files_list)
                git_sync()
        except Exception as e:
            print(f"Global Error: {e}")
        
        sys.stdout.flush() 
        time.sleep(900)

if __name__ == "__main__":
    main()