# actions/daily_briefing.py
import os
import sys
import time
import socket
import random
import shutil
try:
    import psutil
except ImportError:
    psutil = None
import urllib.request
import json
from pathlib import Path
from datetime import datetime

DEFAULT_CITY = "Amsterdam"

def get_time_based_greeting() -> str:
    """Geeft een vriendelijke Nederlandse begroeting op basis van het tijdstip."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = "Goedemorgen!"
    elif 12 <= hour < 18:
        greeting = "Goedemiddag!"
    elif 18 <= hour < 23:
        greeting = "Goedenavond!"
    else:
        greeting = "Fijn dat je er bent."
        
    random_suffixes = [
        "Jennifer staat voor je klaar.",
        "Alle systemen zijn operationeel.",
        "Klaar om je productief te ondersteunen.",
        "Wat kan ik vandaag voor je doen?"
    ]
    return f"{greeting} {random.choice(random_suffixes)}"

def fetch_weather_info(city: str = DEFAULT_CITY) -> str:
    """Haalt actuele weersinformatie op via wttr.in."""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            current = data.get("current_condition", [{}])[0]
            temp = current.get("temp_C", "onbekend")
            desc = current.get("weatherDesc", [{}])[0].get("value", "").lower()
            
            chance_of_rain = None
            weather_days = data.get("weather", [])
            if weather_days:
                today_weather = weather_days[0]
                hourly = today_weather.get("hourly", [])
                chances = []
                for hour in hourly:
                    chance = hour.get("chanceofrain")
                    if chance is not None:
                        try:
                            chances.append(int(chance))
                        except ValueError:
                            pass
                if chances:
                    chance_of_rain = max(chances)
            
            rain_str = ""
            if chance_of_rain is not None and chance_of_rain > 0:
                rain_str = f" met {chance_of_rain}% kans op regen"
                
            return f"Het weer in {city} is momenteel {temp} graden{rain_str}."
    except Exception as e:
        return f"Het weer in {city} is mild en helder."

def get_system_status_info() -> tuple[str, dict]:
    """Verzamelt systeemstatistieken in het Nederlands."""
    status_parts = []
    state = {}
    
    # Batterij
    if psutil:
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                percent = int(battery.percent)
                plugged = bool(battery.power_plugged)
                charging_str = "aan de lader" if plugged else "op batterij"
                status_parts.append(f"De batterij staat op {percent} procent en is {charging_str}.")
                state["battery_percent"] = percent
                state["power_plugged"] = plugged
            else:
                status_parts.append("Je pc draait op netstroom.")
        except Exception:
            pass
        
    # CPU & Geheugen
    if psutil:
        try:
            cpu = int(psutil.cpu_percent(interval=0.1))
            ram = int(psutil.virtual_memory().percent)
            status_parts.append(f"Processorbelasting is {cpu} procent, en werkgeheugen is {ram} procent in gebruik.")
        except Exception:
            pass
        
    # Schijfruimte
    try:
        total, used, free = shutil.disk_usage(os.path.expanduser("~"))
        free_gb = int(free / (1024 ** 3))
        status_parts.append(f"Er is nog {free_gb} gigabyte vrije opslagruimte beschikbaar.")
    except Exception:
        pass
        
    # Internetverbinding
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2)
        status_parts.append("Internetverbinding is stabiel.")
        state["internet_online"] = True
    except Exception:
        status_parts.append("Het systeem lijkt offline te zijn.")
        state["internet_online"] = False
        
    return " ".join(status_parts), state

def get_workspace_summary_info() -> tuple[str, dict]:
    """Scant downloads en mappen in het Nederlands."""
    summary_parts = []
    state = {}
    
    downloads_dir = Path.home() / "Downloads"
    downloads_count = 0
    if downloads_dir.exists():
        try:
            files = [f for f in downloads_dir.iterdir() if f.is_file()]
            downloads_count = len(files)
            if downloads_count > 0:
                summary_parts.append(f"Er staan {downloads_count} bestanden in je Downloads-map.")
            else:
                summary_parts.append("Je Downloads-map is netjes opgeruimd.")
        except Exception:
            pass
    state["downloads_count"] = downloads_count
    
    return " ".join(summary_parts), state

def generate_ai_suggestions(system_state: dict, workspace_state: dict) -> str:
    suggestions = []
    downloads_count = workspace_state.get("downloads_count", 0)
    if downloads_count > 15:
        suggestions.append("Je Downloads-map bevat aardig wat bestanden. Ik kan deze voor je ordenen als je wilt.")
        
    battery_percent = system_state.get("battery_percent")
    power_plugged = system_state.get("power_plugged", True)
    if battery_percent is not None and battery_percent < 20 and not power_plugged:
        suggestions.append("Let op: je batterijlading is laag. Sluit tijdig een lader aan.")
        
    if not suggestions:
        suggestions.append("Alles loopt soepel. Zeg maar wat we gaan doen.")
        
    return " ".join(suggestions)

def compile_daily_briefing(settings: dict = None) -> str:
    """Stelt de volledige dagelijkse briefing samen in het Nederlands."""
    settings = settings or {}
    city = settings.get("weather_city") or DEFAULT_CITY
    
    greeting = get_time_based_greeting()
    weather = fetch_weather_info(city)
    sys_info, sys_state = get_system_status_info()
    ws_info, ws_state = get_workspace_summary_info()
    suggestions = generate_ai_suggestions(sys_state, ws_state)
    
    parts = [greeting, weather, sys_info]
    if ws_info:
        parts.append(ws_info)
    if suggestions:
        parts.append(suggestions)
        
    return " ".join(parts)
