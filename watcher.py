#!/usr/bin/env python3
"""Surveille des zones de pages web et envoie une alerte Telegram quand elles changent.

La liste des sites est dans sites.yaml ; l'état (dernier contenu vu) dans state.json.
Usage : python watcher.py [--dry-run]
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "sites.yaml"
STATE_FILE = ROOT / "state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
MAX_DIFF_LINES = 20
TELEGRAM_MAX_CHARS = 4000


def extract(html, selector=None, ignore=()):
    """Renvoie le texte visible de la zone ciblée, normalisé ligne par ligne."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    nodes = soup.select(selector) if selector else [soup.body or soup]
    if not nodes:
        raise ValueError(f"sélecteur introuvable sur la page : {selector}")

    lines = []
    for node in nodes:
        for line in node.get_text("\n").splitlines():
            line = " ".join(line.split())
            for pattern in ignore:
                line = re.sub(pattern, "", line).strip()
            if line:
                lines.append(line)
    if not lines:
        raise ValueError("page vide : le site bloque probablement les robots")
    return "\n".join(lines)


def summarize_diff(old, new):
    """Lignes ajoutées (+) et retirées (−) entre deux versions du texte."""
    changes = [
        ("➕ " if line.startswith("+") else "➖ ") + line[1:]
        for line in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    if len(changes) > MAX_DIFF_LINES:
        hidden = len(changes) - MAX_DIFF_LINES
        changes = changes[:MAX_DIFF_LINES] + [f"… et {hidden} autre(s) ligne(s)"]
    return "\n".join(changes) or "(changement de mise en forme uniquement)"


def send_telegram(text, dry_run):
    if dry_run:
        print("─── message ───\n" + text + "\n───────────────")
        return
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    if len(text) > TELEGRAM_MAX_CHARS:
        text = text[: TELEGRAM_MAX_CHARS - 1] + "…"
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    if not resp.ok:
        print(f"Échec de l'envoi Telegram : {resp.status_code} {resp.text}", file=sys.stderr)


def check_site(site, previous, dry_run):
    """Vérifie un site et renvoie son nouvel état."""
    name, url = site["name"], site["url"]
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        # Octets bruts : BeautifulSoup lit l'encodage dans la page, que certains
        # sites (ex. Leclerc) n'annoncent pas dans l'en-tête HTTP.
        text = extract(resp.content, site.get("selector"), site.get("ignore", ()))
    except Exception as exc:  # réseau, HTTP, sélecteur absent…
        print(f"[{name}] erreur : {exc}")
        # On n'alerte qu'au passage en erreur, pas à chaque vérification.
        if not previous.get("error"):
            send_telegram(f"⚠️ {name} : vérification impossible\n{exc}\n{url}", dry_run)
        return {**previous, "error": str(exc)}

    digest = hashlib.sha256(text.encode()).hexdigest()
    if not previous.get("hash"):
        print(f"[{name}] premier passage, contenu enregistré")
        send_telegram(f"👀 Surveillance démarrée : {name}\n{url}", dry_run)
    elif digest != previous["hash"]:
        print(f"[{name}] CHANGEMENT détecté")
        diff = summarize_diff(previous.get("text", ""), text)
        send_telegram(f"🔔 Changement sur {name}\n{url}\n\n{diff}", dry_run)
    else:
        print(f"[{name}] inchangé")
        if previous.get("error"):
            send_telegram(f"✅ {name} est de nouveau accessible\n{url}", dry_run)
    return {"hash": digest, "text": text, "error": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="affiche les alertes au lieu de les envoyer et ne modifie pas state.json",
    )
    args = parser.parse_args()

    if not args.dry_run and not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        sys.exit("TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent être définis (ou utilise --dry-run).")

    sites = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))["sites"]
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}

    # Les sites retirés de sites.yaml disparaissent aussi de l'état.
    new_state = {site["name"]: check_site(site, state.get(site["name"], {}), args.dry_run) for site in sites}

    if not args.dry_run:
        STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
