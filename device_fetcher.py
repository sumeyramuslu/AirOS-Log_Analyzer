"""AirOS cihazından log verisi çekme (SSH ve HTTP)."""

import re
import socket
from typing import Optional

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

try:
    import requests
    from requests.auth import HTTPBasicAuth
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def fetch_logs_ssh(
    ip: str,
    username: str = "ubnt",
    password: str = "ubnt",
    port: int = 22,
    timeout: int = 10,
) -> tuple[Optional[str], Optional[str]]:
    if not HAS_PARAMIKO:
        return None, "paramiko kütüphanesi yüklü değil. pip install paramiko"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, port=port, username=username, password=password, timeout=timeout, allow_agent=False, look_for_keys=False)
        for cmd in ("cat /var/log/messages 2>/dev/null", "logread 2>/dev/null", "dmesg 2>/dev/null"):
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            output = stdout.read().decode("utf-8", errors="replace").strip()
            if output and len(output) > 50:
                return output, None
        return None, "Cihazda log dosyası bulunamadı veya boş."
    except paramiko.AuthenticationException:
        return None, "Kimlik doğrulama başarısız. Kullanıcı adı/parola kontrol edin."
    except paramiko.SSHException as e:
        return None, f"SSH bağlantı hatası: {e}"
    except socket.timeout:
        return None, "Bağlantı zaman aşımına uğradı."
    except Exception as e:
        return None, f"Bağlantı hatası: {e}"
    finally:
        client.close()


def fetch_logs_http(
    ip: str,
    username: str = "ubnt",
    password: str = "ubnt",
    timeout: int = 10,
) -> tuple[Optional[str], Optional[str]]:
    if not HAS_REQUESTS:
        return None, "requests kütüphanesi yüklü değil."

    urls = [
        f"http://{ip}/log.cgi",
        f"http://{ip}/status.cgi",
    ]
    auth = HTTPBasicAuth(username, password)
    for url in urls:
        try:
            resp = requests.get(url, auth=auth, timeout=timeout, verify=False)
            if resp.status_code == 200 and len(resp.text) > 50:
                text = resp.text
                if "log" in url:
                    return text, None
                logs = re.findall(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}.+", text)
                if logs:
                    return "\n".join(logs), None
        except requests.exceptions.ConnectionError:
            continue
        except Exception:
            continue
    return None, "HTTP üzerinden log alınamadı."


def fetch_device_info(ip: str, username: str = "ubnt", password: str = "ubnt") -> dict:
    info = {"device": "AirOS Cihaz", "ip": ip, "version": "—", "uptime": "—"}
    if not HAS_REQUESTS:
        return info
    try:
        resp = requests.get(
            f"http://{ip}/status.cgi",
            auth=HTTPBasicAuth(username, password),
            timeout=8,
            verify=False,
        )
        if resp.status_code == 200:
            text = resp.text
            for key, pattern in [
                ("device", r"device\.name\s*=\s*['\"]([^'\"]+)"),
                ("version", r"fwversion\s*=\s*['\"]([^'\"]+)"),
                ("uptime", r"uptime\s*=\s*['\"]([^'\"]+)"),
            ]:
                m = re.search(pattern, text)
                if m:
                    info[key] = m.group(1)
    except Exception:
        pass
    return info


def fetch_logs(ip: str, username: str = "ubnt", password: str = "ubnt", method: str = "auto") -> tuple[Optional[str], Optional[str], dict]:
    device_info = fetch_device_info(ip, username, password)

    if method in ("auto", "ssh"):
        content, err = fetch_logs_ssh(ip, username, password)
        if content:
            return content, None, device_info

    if method in ("auto", "http"):
        content, err_http = fetch_logs_http(ip, username, password)
        if content:
            return content, None, device_info
        if method == "http":
            return None, err_http, device_info

    return None, err if method != "http" else err_http, device_info
