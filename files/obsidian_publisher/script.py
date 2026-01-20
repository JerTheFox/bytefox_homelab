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

# Пути
DEST_CONTENT_DIR = os.path.join(REPO_ROOT, "content", "blog")
DEST_IMG_DIR = os.path.join(REPO_ROOT, "static", "images", "blog")
HUGO_IMG_PREFIX = "/images/blog/"

# Настройки триггеров
TRIGGER_WORDS = ["публикация", "#публикация"]
IGNORED_PREFIXES = ["публикация", "тип/", "статус/", "#публикация", "#тип/", "#статус/"]


def get_file_date(filepath):
    timestamp = os.path.getmtime(filepath)
    return datetime.date.fromtimestamp(timestamp).isoformat()

def normalize_content_for_comparison(text):
    return re.sub(r'^date: .*$', '', text, flags=re.MULTILINE)

def extract_frontmatter_and_body(content):
    match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, content

def parse_yaml_tags(yaml_text):
    tags = []
    tag_section_match = re.search(r'^tags:\s*\n((?:[\s-].*\n?)*)', yaml_text, re.MULTILINE)
    if tag_section_match:
        block = tag_section_match.group(1)
        items = re.findall(r'^\s*-\s*(.+)$', block, re.MULTILINE)
        tags = [t.strip().strip('"\'') for t in items]
    return tags

def extract_title(body, filename):
    match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return os.path.splitext(filename)[0]

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

def process_images(content, source_file_path):
    # 1. Wiki-links -> Standard
    def wiki_to_md(match):
        return f"![]({match.group(1)})"
    content = re.sub(r'!\[\[(.*?)\]\]', wiki_to_md, content)

    # 2. Standard links
    img_pattern = r'!\[(.*?)\]\((.*?)\)'

    def replace_image(match):
        alt_text = match.group(1)
        img_rel_path = match.group(2)
        img_rel_path_decoded = urllib.parse.unquote(img_rel_path)

        source_dir = os.path.dirname(source_file_path)
        img_abs_path = os.path.join(source_dir, img_rel_path_decoded)

        # Поиск в attachments
        if not os.path.isfile(img_abs_path):
             img_abs_path = os.path.join(source_dir, "attachments", img_rel_path_decoded)

        if os.path.isfile(img_abs_path):
            img_filename = os.path.basename(img_abs_path)
            clean_filename = img_filename.replace(" ", "_")

            os.makedirs(DEST_IMG_DIR, exist_ok=True)
            dest_img_path = os.path.join(DEST_IMG_DIR, clean_filename)

            # Копируем только если размер отличается
            should_copy = True
            if os.path.exists(dest_img_path):
                if os.path.getsize(dest_img_path) == os.path.getsize(img_abs_path):
                    should_copy = False

            if should_copy:
                # print(f"Картинка: {clean_filename}")
                shutil.copy2(img_abs_path, dest_img_path)

            return f'![{alt_text}]({HUGO_IMG_PREFIX}{clean_filename})'
        else:
            # print(f"Картинка не найдена: {img_rel_path_decoded}")
            return match.group(0)

    return re.sub(img_pattern, replace_image, content)


def process_file(filepath, filename):
    # Игнор временных файлов
    if "~" in filename or "sync-conflict" in filename:
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # СБОР ДАННЫХ
    raw_frontmatter, body = extract_frontmatter_and_body(original_content)

    current_tags = []
    if raw_frontmatter:
        current_tags.extend(parse_yaml_tags(raw_frontmatter))

    inline_tags = re.findall(r'(?:^|\s)(#[\w\d\-_/а-яА-ЯёЁ]+)', body)
    current_tags.extend(inline_tags)

    # Проверка триггера
    is_triggered = False
    for t in current_tags:
        clean_t = t.strip().replace('#', '')
        if 'публикация' == clean_t:
            is_triggered = True
            break

    if not is_triggered:
        return False

    # ГЕНЕРАЦИЯ КОНТЕНТА
    date_str = get_file_date(filepath)
    title = extract_title(body, filename)
    body = re.sub(r'^#\s+.+$', '', body, flags=re.MULTILINE)

    for tag in inline_tags:
        body = body.replace(tag, "")

    tags_list, body = process_tags(body)

    # Объединение тегов
    final_tags_set = set(tags_list)
    if raw_frontmatter:
        yaml_tags = parse_yaml_tags(raw_frontmatter)
        for t in yaml_tags:
            clean = t.replace('#', '')
            is_tech = False
            for p in IGNORED_PREFIXES:
                if clean.startswith(p.replace('#', '')):
                    is_tech = True
                    break
            if not is_tech:
                final_tags_set.add(clean)

    body = process_images(body, filepath)

    sorted_tags = sorted(list(final_tags_set))

    tags_yaml = ""
    for t in sorted_tags:
        tags_yaml += f"- {t}\n"

    if not title:
        title = os.path.splitext(filename)[0]

    new_frontmatter = f"""---
date: {date_str}
params:
  author: JerTheFox
tags:
{tags_yaml}title: "{title}"
weight: 10
---
"""
    final_content = new_frontmatter + body.strip()

    # ЗАПИСЬ
    os.makedirs(DEST_CONTENT_DIR, exist_ok=True)
    dest_path = os.path.join(DEST_CONTENT_DIR, filename)

    if os.path.exists(dest_path):
        with open(dest_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()

        if normalize_content_for_comparison(existing_content) == normalize_content_for_comparison(final_content):
            # print(f"Стабильно: {filename}")
            return True

    print(f"✅ ИЗМЕНЕНИЕ: {filename}")
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    return True

def git_sync():
    # print("\n Checking Git...")
    try:
        subprocess.run(["git", "add", "."], cwd=REPO_ROOT, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True)

        if status.stdout.strip():
            print("Detected changes -> Pushing to GitLab...")
            subprocess.run(["git", "commit", "-m", "Auto-publish from Obsidian"], cwd=REPO_ROOT, check=True)
            subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)
            print("Done.")
        else:
            pass

    except Exception as e:
        print(f"❌ Git Error: {e}")

def garbage_collector(active_files):
    # print("\n GC...")
    if not os.path.exists(DEST_CONTENT_DIR):
        return

    site_files = [f for f in os.listdir(DEST_CONTENT_DIR) if f.endswith(".md")]
    deleted = False

    for file in site_files:
        if file == "_index.md":
            continue
        if file not in active_files:
            print(f"🗑 Delete: {file}")
            os.remove(os.path.join(DEST_CONTENT_DIR, file))
            deleted = True

def main():
    print("🚀 Obsidian Publisher Service Started")

    if not os.path.exists(os.path.join(REPO_ROOT, ".git")):
         print("Cloning Site Repo...")
         try:
             repo_url = os.environ.get("SITE_REPO_URL")
             if not repo_url:
                 print("❌ Error: SITE_REPO_URL not set")
                 return

             subprocess.run(["git", "clone", repo_url, REPO_ROOT], check=True)

             subprocess.run(["git", "config", "user.email", "bot@bytefox.ru"], cwd=REPO_ROOT)
             subprocess.run(["git", "config", "user.name", "ObsidianBot"], cwd=REPO_ROOT)
         except Exception as e:
             print(f"❌ Clone Error: {e}")
             return

    # Бесконечный цикл
    while True:
        try:
            print(f"Sync started at {datetime.datetime.now().isoformat()}")

            if not os.path.exists(SOURCE_DIR):
                print(f"❌ Source not found: {SOURCE_DIR}")
            else:
                try:
                    subprocess.run(["git", "pull"], cwd=REPO_ROOT, check=True, capture_output=True)
                except:
                    pass

                processed_files_list = []
                for root, dirs, files in os.walk(SOURCE_DIR):
                    for file in files:
                        if file.endswith(".md"):
                            if process_file(os.path.join(root, file), file):
                                processed_files_list.append(file)

                garbage_collector(processed_files_list)
                git_sync()
            # -------------------

        except Exception as e:
            print(f"❌ Global Error: {e}")

        # print("Sleeping...")
        sys.stdout.flush() # Чтобы логи сразу попадали в Docker logs
        time.sleep(900)

if __name__ == "__main__":
    main()
