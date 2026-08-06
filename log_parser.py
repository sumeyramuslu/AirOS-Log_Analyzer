"""AirOS 8 log parser — dakika bazlı zaman çizelgesi."""

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

LOG_LINE_RE = re.compile(
    r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<source>[\w\-\.]+)(?:\[(?P<pid>\d+)\])?\s*:\s*(?P<message>.+)$"
)

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

EVENT_PATTERNS = [
    ("Reboot", [
        r"system:\s*Start",
        r"syslogd started",
        r"Fastrestart complete",
        r"reboot",
        r"kernel:\s*\[.*\]\s*Linux version",
    ]),
    ("Ethernet Down", [
        r"interface=eth\d+\s+link=DOWN",
        r"eth\d+.*link.*down",
        r"Ethernet.*down",
    ]),
    ("Ethernet Up", [
        r"interface=eth\d+\s+link=UP",
        r"eth\d+.*link.*up",
        r"Ethernet.*up",
    ]),
    ("DHCP", [
        r"DHCPDISCOVER",
        r"DHCPOFFER",
        r"DHCPREQUEST",
        r"DHCPACK",
        r"DHCPNAK",
        r"dnsmasq-dhcp",
        r"DHCP, IP range",
        r"DHCP, sockets bound",
    ]),
    ("Authentication", [
        r"Authenticated Station",
        r"Received auth.*Successful",
        r"Sending auth.*Successful",
        r"Registered node",
        r"assoc_resp.*Successful",
    ]),
    ("Deauthentication", [
        r"Deauthenticated Station",
        r"Received deauth",
        r"Expired node",
        r"Sending deauth",
    ]),
    ("DFS CAC", [
        r"Channel Availability Check",
    ]),
    ("DFS", [
        r"\bDFS\b",
        r"radar detected",
    ]),
    ("Radar", [
        r"radar",
        r"Radar",
    ]),
    ("NTP", [
        r"ntpclient",
        r"NTP",
        r"ntpd",
    ]),
    ("Login", [
        r"Password auth succeeded",
        r"login.*succeeded",
        r"User .* logged in",
    ]),
    ("Login Failed", [
        r"Bad password attempt",
        r"login.*failed",
        r"auth.*failed",
        r"Authentication failed",
    ]),
    ("Wireless Disconnect", [
        r"Deauthenticated",
        r"Received deauth",
        r"Expired node",
        r"disassoc",
    ]),
    ("Link Down", [
        r"link=DOWN",
        r"Link Down",
    ]),
    ("Link Up", [
        r"link=UP",
        r"Link Up",
    ]),
    ("Channel Change", [
        r"Channel Change",
        r"changed channel",
        r"Set Channel:",
    ]),
    ("Signal Problems", [
        r"signal.*low",
        r"weak signal",
        r"SNR",
        r"noise floor",
        r"link quality",
    ]),
    ("System Service", [
        r"^init:",
        r"syslogd",
        r"dnsmasq\[",
        r"FileSystem:",
        r"provmode:",
        r"lighttpd\[",
        r"dropbear\[",
        r"udapi-server",
        r"ulogger\[",
        r"ustatsd\[",
        r"hostapd",
        r"ubntspecd",
    ]),
    ("Wireless Event", [
        r"wireless:",
        r"Scan request",
        r"Set Mode:",
    ]),
]

CATEGORY_MAP = {
    "Reboot": "System",
    "Ethernet Down": "Ethernet",
    "Ethernet Up": "Ethernet",
    "Link Down": "Ethernet",
    "Link Up": "Ethernet",
    "DHCP": "System",
    "Authentication": "Authentication",
    "Deauthentication": "Authentication",
    "Login": "Authentication",
    "Login Failed": "Authentication",
    "Wireless Disconnect": "Wireless",
    "DFS CAC": "DFS/Radar",
    "DFS": "DFS/Radar",
    "Radar": "DFS/Radar",
    "Channel Change": "Wireless",
    "Signal Problems": "Wireless",
    "NTP": "System",
    "System Service": "System",
    "Wireless Event": "Wireless",
}

TURKISH_EXPLANATIONS = {
    "Reboot": "Cihaz yeniden başlatıldı veya sistem servisleri yeniden yüklendi.",
    "Ethernet Down": "Ethernet bağlantısı kesildi. Kablo veya port bağlantısını kontrol edin.",
    "Ethernet Up": "Ethernet bağlantısı yeniden kuruldu.",
    "Link Down": "Ağ bağlantısı kesildi.",
    "Link Up": "Ağ bağlantısı yeniden kuruldu.",
    "DHCP": "DHCP işlemi gerçekleşti — istemciye IP adresi atandı veya talep edildi.",
    "Authentication": "Kablosuz istemci başarıyla kimlik doğrulaması yaptı ve ağa bağlandı.",
    "Deauthentication": "Kablosuz istemci bağlantısı sonlandırıldı.",
    "Wireless Disconnect": "Kablosuz istemci bağlantısı kesildi.",
    "DFS CAC": "DFS kanal uygunluk kontrolü başlatıldı veya tamamlandı.",
    "DFS": "DFS (Dinamik Frekans Seçimi) olayı tespit edildi.",
    "Radar": "Radar sinyali algılandı — kanal değişimi gerekebilir.",
    "NTP": "NTP zaman senkronizasyonu işlemi gerçekleşti.",
    "Login": "Web arayüzüne başarılı giriş yapıldı.",
    "Login Failed": "Web arayüzüne yanlış parola ile giriş denemesi yapıldı.",
    "Channel Change": "Kablosuz kanal değiştirildi.",
    "Signal Problems": "Sinyal kalitesi ile ilgili bir uyarı tespit edildi.",
    "System Service": "Sistem servisi başlatıldı, durduruldu veya yeniden yapılandırıldı.",
    "Wireless Event": "Kablosuz radyo ile ilgili bir olay kaydedildi.",
}

LEVEL_RULES = {
    "Login Failed": "ERROR",
    "Ethernet Down": "WARNING",
    "Link Down": "WARNING",
    "Deauthentication": "WARNING",
    "Wireless Disconnect": "WARNING",
    "Signal Problems": "WARNING",
    "Radar": "WARNING",
    "DFS": "WARNING",
    "Authentication": "INFO",
    "Ethernet Up": "INFO",
    "Link Up": "INFO",
    "Login": "INFO",
    "DHCP": "INFO",
    "Reboot": "INFO",
    "NTP": "INFO",
    "DFS CAC": "INFO",
    "Channel Change": "INFO",
    "System Service": "INFO",
    "Wireless Event": "INFO",
}


def classify_event(message: str) -> str:
    for event_name, patterns in EVENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return event_name
    return "Other"


def get_level(event: str, message: str) -> str:
    if event in LEVEL_RULES:
        return LEVEL_RULES[event]
    msg_lower = message.lower()
    if any(w in msg_lower for w in ("error", "fail", "bad password", "invalid")):
        return "ERROR"
    if any(w in msg_lower for w in ("warn", "down", "deauth", "reset", "exited")):
        return "WARNING"
    return "INFO"


def get_turkish_explanation(event: str, message: str) -> str:
    if event in TURKISH_EXPLANATIONS:
        base = TURKISH_EXPLANATIONS[event]
        if event == "Login Failed":
            m = re.search(r"for '(\w+)' from ([\d\.]+)", message)
            if m:
                return f"{base} Kullanıcı: {m.group(1)}, IP: {m.group(2)}."
        if event == "Login":
            m = re.search(r"for '(\w+)' from ([\d\.]+)", message)
            if m:
                return f"{base} Kullanıcı: {m.group(1)}, IP: {m.group(2)}."
        if event == "Authentication":
            m = re.search(r"Station\s+([\w:]+)", message, re.I)
            if m:
                return f"{base} MAC: {m.group(1)}."
        if event in ("Ethernet Down", "Ethernet Up", "Link Down", "Link Up"):
            m = re.search(r"interface=(\w+)", message)
            if m:
                return f"{base} Arayüz: {m.group(1)}."
        if event == "DHCP":
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([\w:]+)", message)
            if m:
                return f"{base} IP: {m.group(1)}, MAC: {m.group(2)}."
        return base
    if "syslogd" in message or "init:" in message or "dnsmasq" in message:
        return "Sistem servisi başlatıldı veya yapılandırıldı."
    if "wireless:" in message.lower():
        return "Kablosuz radyo ile ilgili bir olay kaydedildi."
    if "httpd" in message or "lighttpd" in message:
        return "Web sunucusu ile ilgili bir olay kaydedildi."
    return "Genel sistem olayı — detay için ham log satırına bakın."


def parse_timestamp(month: str, day: str, time_str: str, year: int = 2025) -> Optional[str]:
    try:
        month_num = MONTHS.get(month, 1)
        dt = datetime(year, month_num, int(day), *map(int, time_str.split(":")))
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def parse_log_content(content: str, year: int = 2025) -> dict:
    lines = content.strip().splitlines()
    entries = []
    event_counts = Counter()
    category_counts = Counter()
    level_counts = Counter()
    minutely = defaultdict(lambda: {"all": 0, "warning": 0, "error": 0})

    for raw_line in lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        match = LOG_LINE_RE.match(raw_line)
        if match:
            groups = match.groupdict()
            message = groups["message"]
            source = groups["source"]
            timestamp = parse_timestamp(groups["month"], groups["day"], groups["time"], year)
            time_display = f"{groups['month']} {groups['day']} {groups['time']}"
        else:
            message = raw_line
            source = "unknown"
            timestamp = None
            time_display = "—"

        event = classify_event(message)
        level = get_level(event, message)
        category = CATEGORY_MAP.get(event, "Other")
        explanation_tr = get_turkish_explanation(event, message)

        entries.append({
            "time": time_display,
            "timestamp": timestamp,
            "level": level,
            "event": event,
            "category": category,
            "explanation_tr": explanation_tr,
            "raw": raw_line,
            "source": source,
        })

        event_counts[event] += 1
        category_counts[category] += 1
        level_counts[level.lower()] += 1

        if timestamp:
            minute_key = timestamp[11:16]
            minutely[minute_key]["all"] += 1
            if level == "WARNING":
                minutely[minute_key]["warning"] += 1
            elif level == "ERROR":
                minutely[minute_key]["error"] += 1

    problems = analyze_problems(entries, event_counts)

    total = len(entries)
    info_count = level_counts.get("info", 0)
    warning_count = level_counts.get("warning", 0)
    error_count = level_counts.get("error", 0)

    top_events = event_counts.most_common(8)
    while len(top_events) < 5:
        top_events.append(("—", 0))

    minutes_sorted = sorted(minutely.keys()) if minutely else ["00:00"]
    timeline = {
        "labels": minutes_sorted,
        "all": [minutely[m]["all"] for m in minutes_sorted],
        "warnings": [minutely[m]["warning"] for m in minutes_sorted],
        "errors": [minutely[m]["error"] for m in minutes_sorted],
    }

    categories = dict(category_counts)
    cat_total = sum(categories.values()) or 1
    distribution = {
        "labels": list(categories.keys()) or ["Veri Yok"],
        "values": list(categories.values()) or [0],
        "percentages": [round(v / cat_total * 100, 1) for v in categories.values()] or [0],
    }

    return {
        "summary": {
            "total": total,
            "info": info_count,
            "warning": warning_count,
            "error": error_count,
            "info_pct": round(info_count / total * 100, 1) if total else 0,
            "warning_pct": round(warning_count / total * 100, 1) if total else 0,
            "error_pct": round(error_count / total * 100, 1) if total else 0,
        },
        "entries": entries,
        "distribution": distribution,
        "timeline": timeline,
        "top_events": [{"name": n, "count": c} for n, c in top_events[:5]],
        "problems": problems,
    }


def analyze_problems(entries: list, event_counts: Counter) -> list:
    problems = []

    eth_down = event_counts.get("Ethernet Down", 0) + event_counts.get("Link Down", 0)
    if eth_down > 0:
        problems.append({
            "status": "warning" if eth_down <= 2 else "error",
            "title": "Ethernet Kabloları",
            "detail": f"Ethernet bağlantısı {eth_down} kez kesilmiş.",
            "description": "Kablo veya port kontrolü önerilir. Fiziksel bağlantıyı ve switch portunu kontrol edin.",
        })
    else:
        problems.append({
            "status": "ok",
            "title": "Ethernet Kabloları",
            "detail": "Ethernet kesintisi tespit edilmedi.",
            "description": "Ethernet bağlantısı stabil görünüyor.",
        })

    login_failed = event_counts.get("Login Failed", 0)
    if login_failed > 0:
        problems.append({
            "status": "warning" if login_failed <= 3 else "error",
            "title": "Yanlış Parola Girişleri",
            "detail": f"Yanlış parola girişi {login_failed} kez tespit edildi.",
            "description": "Yetkisiz erişim denemesi olabilir. Parolayı değiştirmeyi ve erişim IP'lerini kontrol etmeyi düşünün.",
        })
    else:
        problems.append({
            "status": "ok",
            "title": "Yanlış Parola Girişleri",
            "detail": "Başarısız giriş denemesi yok.",
            "description": "Web arayüzüne yetkisiz erişim denemesi görünmüyor.",
        })

    deauth = event_counts.get("Deauthentication", 0) + event_counts.get("Wireless Disconnect", 0)
    if deauth > 0:
        problems.append({
            "status": "info",
            "title": "Kablosuz Bağlantı Kesintileri",
            "detail": f"Kablosuz bağlantı {deauth} kez sonlandırılmış.",
            "description": "İstemciler kendi isteğiyle veya sinyal kaybı nedeniyle ayrılmış olabilir.",
        })
    else:
        problems.append({
            "status": "ok",
            "title": "Kablosuz Bağlantı",
            "detail": "Kablosuz bağlantı kesintisi yok.",
            "description": "Kablosuz istemci bağlantıları stabil.",
        })

    reboot = event_counts.get("Reboot", 0)
    if reboot > 2:
        problems.append({
            "status": "warning",
            "title": "Cihaz Yeniden Başlatma",
            "detail": f"Cihaz {reboot} kez yeniden başlatılmış.",
            "description": "Sık reboot power kesintisi veya yazılım sorununa işaret edebilir.",
        })
    else:
        problems.append({
            "status": "ok",
            "title": "AP Tarafında Reset",
            "detail": "Anormal reset tespit edilmedi.",
            "description": "Cihaz normal çalışma döngüsünde görünüyor.",
        })

    dfs = event_counts.get("DFS", 0) + event_counts.get("Radar", 0) + event_counts.get("Channel Change", 0)
    if dfs > 0:
        problems.append({
            "status": "info",
            "title": "DFS / Kanal Değişimi",
            "detail": f"DFS veya kanal değişimi {dfs} kez kaydedildi.",
            "description": "Radar algılama veya DFS CAC nedeniyle kanal değişimi gerçekleşmiş olabilir.",
        })
    else:
        problems.append({
            "status": "ok",
            "title": "DFS Kaynaklı Kanal Değişimi",
            "detail": "DFS kaynaklı kanal değişimi yok.",
            "description": "Frekans bandında radar veya kanal değişimi olayı görünmüyor.",
        })

    power_issues = sum(1 for e in entries if "power" in e["raw"].lower() or "watchdog" in e["raw"].lower())
    if power_issues > 0:
        problems.append({
            "status": "error",
            "title": "Güç Kesintisi",
            "detail": f"Güç ile ilgili {power_issues} olay tespit edildi.",
            "description": "PoE veya güç kaynağını kontrol edin.",
        })
    else:
        problems.append({
            "status": "ok",
            "title": "Güç Kesintisi",
            "detail": "Güç kesintisi görünmüyor.",
            "description": "Güç kaynağı stabil görünüyor.",
        })

    hw_errors = sum(1 for e in entries if e["level"] == "ERROR" and "fail" in e["raw"].lower())
    if hw_errors > 2:
        problems.append({
            "status": "error",
            "title": "Donanımsal Hata",
            "detail": f"{hw_errors} donanım/hata kaydı tespit edildi.",
            "description": "Detaylı inceleme ve olası donanım değişimi önerilir.",
        })
    else:
        problems.append({
            "status": "ok",
            "title": "Donanımsal Hata",
            "detail": "Donanımsal hata görünmüyor.",
            "description": "Kritik donanım hatası tespit edilmedi.",
        })

    return problems
