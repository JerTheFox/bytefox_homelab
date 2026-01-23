# ByteFox Homelab Infrastructure

Полностью декларативная Infrastructure-as-Code (IaC) конфигурация для управления распределенной домашней лабораторией. Проект демонстрирует подход GitOps, современные практики безопасности (Zero Trust), автоматизированный CI/CD и полный стек наблюдаемости.

## Архитектура

Инфраструктура построена на базе Debian 13 и оркестрируется через Ansible + Docker Compose. Сеть разделена на публичный и приватный контуры, доступ к внутренним сервисам закрыт через VPN и Traefik Middlewares.

### Топология узлов

| Нода | Роль | Описание | Ключевые сервисы |
| --- | --- | --- | --- |
| **Mgmt** | Control Plane | Управление, мониторинг, входная точка (Ingress), CI/CD. | Traefik, GitLab, Grafana, Prometheus, Loki, OpenConnect VPN |
| **Worker** | Compute | Ресурсоемкие приложения, NVMe хранилище. | Minecraft (Java), Syncthing, Vaultwarden, BookLore, Obsidian Publisher |
| **Backup** | Storage | Холодное хранение и бэкапы (RAID массив). | UrBackup Server |

### Технологический стек

* **Оркестрация:** Ansible, Docker Compose v2.
* **Ingress:** Traefik v3 (Wildcard SSL - Let's Encrypt DNS Challenge), Fail2Ban, OpenConnect (OCServ).
* **CI/CD:** GitLab CI.
* **Мониторинг:** Prometheus, Node Exporter, cAdvisor, Promtail, Loki, Grafana.
* **Дашборд:** Glance.
* **Сеть:** TCP BBR Congestion Control, Split DNS.

---

## Особенности реализации

### 1. GitOps

Любое изменение в инфраструктуре проходит через GitLab CI. Пайплайн настроен на определение изменений (`rules:changes`):

* Изменение в `roles/worker` -> Деплой только на Worker Node.
* Изменение в `roles/common` -> Обновление всей инфраструктуры.
* Изменение конфигурации мониторинга -> Перезагрузка только Prometheus/Grafana.

### 2. Безопасность и управление секретами

* **Ansible Vault:** Все чувствительные данные (пароли, токены API, ключи SSH) зашифрованы AES-256.
* **Separation of Concerns:** Конфигурация отделена от секретов (`vars.yml` и `vault.yml`).
* **Zero Trust:** Публично доступны только сайт и VPN. Все внутренние сервисы (Portainer, DBs, Metrics) скрыты за Traefik Middleware (`only-vpn-and-local`).
* **Hardening:** SSH root login отключен, Password auth отключен, UFW настроен по принципу "Deny Incoming All".

### 3. Наблюдение и сбор метрик/логов

Реализован полный цикл сбора метрик и логов:

* **Metrics:** Prometheus собирает метрики хостов (CPU/RAM/Disk), контейнеров (cAdvisor) и приложений (Minecraft Exporter).
* **Logs:** Promtail собирает логи Docker-контейнеров и отправляет в Loki.
* **Alerting:** Настроены алерты в Grafana (статус сервера Minecraft, здоровье дисков, доступность нод).
* **Custom Monitoring:** Glance дашборд отображает статус авто-паузы игрового сервера и здоровье CI/CD.

---

## Структура проекта

```text
.
├── inventory/
│   ├── group_vars/all/
│   │   ├── vars.yml       # Открытые глобальные переменные (версии, порты)
│   │   └── vault.yml      # Зашифрованные секреты (Ansible Vault)
│   └── hosts.ini          # Инвентарь серверов
├── playbooks/
│   └── site.yml           # Главный декларативный плейбук
├── roles/
│   ├── common/            # Базовая настройка (Kernel, Users, Docker, UFW base)
│   ├── mgmt/              # Специфика Management Node (VPN, Traefik, GitLab)
│   ├── worker/            # Специфика Worker Node (Heavy apps, NVMe mounts)
│   ├── backup/            # Специфика Backup Node (RAID, UrBackup)
│   └── deploy_stack/      # Универсальная роль для деплоя Docker Compose
├── templates/             # Jinja2 шаблоны для Docker Compose и конфигов
└── files/                 # Статические конфиги и скрипты

```

---

## Установка и запуск

### Предварительные требования

* Управляющая машина с Linux/macOS и Python 3.
* Установленный Ansible (`pip install ansible`).
* SSH доступ к серверам по ключу.

### 1. Клонирование

```bash
git clone https://github.com/your-username/homelab-infra.git
cd homelab-infra
```

### 2. Настройка секретов

Секреты должны храниться в `inventory/group_vars/all/vault.yml`, файл должен быть зашифрован сложным паролем через Ansible Vault, пароль должен храниться в переменных проекта в GitLab.

### 3. Запуск деплоя

Для развертывания всей инфраструктуры:

```bash
ansible-playbook playbooks/site.yml
```

Для обновления только конкретной ноды (например, Worker):

```bash
ansible-playbook playbooks/site.yml --limit worker
```

---

## Кастомные решения

### Minecraft Auto-Pause & Monitoring

Игровой сервер автоматически уходит в гибернацию при отсутствии игроков для экономии ресурсов CPU.

* **Решение:** Используется контейнер `itzg/minecraft-server` с флагом `ENABLE_AUTOPAUSE`.
* **Мониторинг:** Написан кастомный виджет для Glance, который опрашивает Prometheus. Если `up == 0`, но контейнер жив - выводится статус "Auto-Paused", а не ошибка.

### Obsidian to Hugo

Реализован автоматический деплой заметок из Obsidian в статический сайт Hugo.

* Скрипт на Python отслеживает изменения в папке Syncthing.
* При изменениях происходит `git commit && git push` во внутренний GitLab.
* GitLab CI собирает Hugo сайт и деплоит его на веб-сервер.

---

*Developed by Maksim Rososhanskiy*
