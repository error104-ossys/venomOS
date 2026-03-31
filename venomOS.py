
#!/usr/bin/env python3
import os, sys, sqlite3, hashlib, socket, subprocess, platform, re
import json, time, threading, psutil, netifaces, requests, colorama
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import ipaddress
from scapy.all import ARP, Ether, srp

# Initialize colorama for cross-platform colors
colorama.init()

# =========================
# CONFIG
# =========================
APP_NAME = "ENTERPRISE SECURITY SUITE v2.0"
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
BLOCKED_HOSTS_FILE = "/etc/hosts.backup"  # Backup original hosts

IS_LINUX = platform.system().lower() == "linux"
IS_WSL = "microsoft" in platform.uname().release.lower()

USERNAME = "ADMIN"  # Change this to your desired username display

# Color themes
THEMES = {
    'grey_black': {'bg': '\033[100m', 'fg': '\033[97m', 'reset': '\033[0m'},
    'gold_black': {'bg': '\033[43m', 'fg': '\033[30m', 'reset': '\033[0m'},
    'green_black': {'bg': '\033[42m', 'fg': '\033[30m', 'reset': '\033[0m'},
    'white_black': {'bg': '\033[47m', 'fg': '\033[30m', 'reset': '\033[0m'},
    'red_black': {'bg': '\033[41m', 'fg': '\033[97m', 'reset': '\033[0m'}
}
current_theme = THEMES['green_black']

# =========================
# DATABASE
# =========================
class DB:
    def __init__(self):
        self.path = DATA_DIR / "security.db"
        self.init_db()

    def connect(self):
        return sqlite3.connect(self.path)

    def init_db(self):
        with self.connect() as con:
            c = con.cursor()
            # Users table
            c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, created_at TEXT)")
            
            # Logs table
            c.execute("CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY, time TEXT, action TEXT, details TEXT)")
            
            # Blocked domains
            c.execute("CREATE TABLE IF NOT EXISTS blocked_domains(id INTEGER PRIMARY KEY, domain TEXT UNIQUE, blocked_at TEXT, reason TEXT)")
            
            # Social media accounts
            c.execute("CREATE TABLE IF NOT EXISTS social_accounts(id INTEGER PRIMARY KEY, platform TEXT, username TEXT, added_at TEXT, last_login TEXT, login_location TEXT, login_device TEXT)")
            
            # Suspicious files
            c.execute("CREATE TABLE IF NOT EXISTS suspicious_files(id INTEGER PRIMARY KEY, filepath TEXT UNIQUE, reason TEXT, detected_at TEXT, status TEXT DEFAULT 'pending')")
            
            # Firewall rules
            c.execute("CREATE TABLE IF NOT EXISTS firewall_rules(id INTEGER PRIMARY KEY, port INTEGER, protocol TEXT, action TEXT, added_at TEXT)")
            
            # Network scans
            c.execute("CREATE TABLE IF NOT EXISTS network_scans(id INTEGER PRIMARY KEY, scan_time TEXT, ip TEXT, hostname TEXT, mac TEXT, device_type TEXT)")

db = DB()

# =========================
# UTILITIES
# =========================
def colored_print(msg, color='white', bold=False):
    colors = {
        'grey': '\033[90m', 'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
        'blue': '\033[94m', 'purple': '\033[95m', 'cyan': '\033[96m', 'white': '\033[97m'
    }
    end = '\033[1m' if bold else ''
    print(f"{current_theme['bg']}{colors.get(color, colors['white'])}{end}{msg}{current_theme['reset']}", end='')

def log_action(action, details=""):
    timestamp = datetime.now().isoformat()
    with db.connect() as con:
        con.execute("INSERT INTO logs (time, action, details) VALUES(?,?,?)", 
                   (timestamp, action, details))
    colored_print(f"[{datetime.now().strftime('%H:%M:%S')}] {action}\n", 'green')

def get_local_ip():
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except:
        return "127.0.0.1"

def backup_hosts():
    if not os.path.exists(BLOCKED_HOSTS_FILE):
        try:
            subprocess.run(["sudo", "cp", "/etc/hosts", BLOCKED_HOSTS_FILE], check=True)
        except:
            pass

# =========================
# AUTH SYSTEM
# =========================
class Auth:
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def setup_first_user(self):
        with db.connect() as con:
            if not con.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                colored_print("\n🔐 FIRST TIME SETUP - CREATE ADMIN ACCOUNT\n", 'yellow', True)
                username = input("👤 Admin Username: ").strip()
                password = input("🔑 Admin Password: ").strip()
                timestamp = datetime.now().isoformat()
                con.execute("INSERT INTO users (username, password, created_at) VALUES(?,?,?)",
                           (username, self.hash_password(password), timestamp))
                log_action("Admin account created", f"Username: {username}")
                colored_print("✅ Admin account created successfully!\n", 'green', True)

    def login(self):
        colored_print("\n🔐 ENTERPRISE SECURITY SUITE - LOGIN\n", 'yellow', True)
        username = input("👤 Username: ").strip()
        password = input("🔑 Password: ").strip()
        
        with db.connect() as con:
            result = con.execute("SELECT * FROM users WHERE username=? AND password=?",
                               (username, self.hash_password(password))).fetchone()
        
        if result:
            log_action("User login successful", f"Username: {username}")
            colored_print(f"✅ Welcome {username}! Security Suite activated.\n", 'green', True)
            return True
        else:
            log_action("Login failed - invalid credentials")
            colored_print("❌ Access denied! Invalid credentials.\n", 'red', True)
            return False

auth = Auth()

# =========================
# THEME CHANGER
# =========================
def change_theme():
    colored_print("\n🎨 THEME SELECTOR\n", 'cyan', True)
    for i, (name, _) in enumerate(THEMES.items(), 1):
        colored_print(f"{i}. {name.replace('_', ' ').title()}\n", 'white')
    
    try:
        choice = int(input("Select theme (1-5): ")) - 1
        theme_names = list(THEMES.keys())
        if 0 <= choice < len(theme_names):
            global current_theme
            current_theme = THEMES[theme_names[choice]]
            log_action("Theme changed", theme_names[choice])
            colored_print(f"✅ Theme changed to {theme_names[choice].replace('_', ' ').title()}\n", 'green', True)
        else:
            colored_print("❌ Invalid choice!\n", 'red')
    except:
        colored_print("❌ Invalid input!\n", 'red')

# =========================
# FIREWALL SYSTEM
# =========================
def firewall_menu():
    while True:
        colored_print("\n🛡️  ADVANCED FIREWALL CONTROL\n", 'red', True)
        print("1. Block Port")
        print("2. Unblock Port")
        print("3. List Rules")
        print("4. Flush All Rules")
        print("5. Back")
        choice = input("\n> ").strip()

        if choice == "1":
            port = input("Port to block: ").strip()
            protocol = input("Protocol (tcp/udp/all): ").strip().lower() or "tcp"
            try:
                subprocess.run(["sudo", "iptables", "-A", "INPUT", "-p", protocol, "--dport", port, "-j", "DROP"], check=True)
                timestamp = datetime.now().isoformat()
                with db.connect() as con:
                    con.execute("INSERT INTO firewall_rules VALUES(NULL,?,?,?,?)", 
                               (int(port), protocol, "BLOCK", timestamp))
                log_action(f"Blocked port {port}/{protocol}")
                colored_print(f"✅ Port {port}/{protocol} blocked!\n", 'green')
            except:
                colored_print("❌ Failed to block port (sudo required)\n", 'red')

        elif choice == "2":
            port = input("Port to unblock: ").strip()
            protocol = input("Protocol (tcp/udp): ").strip().lower() or "tcp"
            try:
                subprocess.run(["sudo", "iptables", "-D", "INPUT", "-p", protocol, "--dport", port, "-j", "DROP"], check=True)
                with db.connect() as con:
                    con.execute("DELETE FROM firewall_rules WHERE port=? AND protocol=?", (int(port), protocol))
                log_action(f"Unblocked port {port}/{protocol}")
                colored_print(f"✅ Port {port}/{protocol} unblocked!\n", 'green')
            except:
                colored_print("❌ Failed to unblock port\n", 'red')

        elif choice == "3":
            with db.connect() as con:
                rules = con.execute("SELECT * FROM firewall_rules").fetchall()
            if rules:
                colored_print("📋 ACTIVE FIREWALL RULES:\n", 'yellow')
                for rule in rules:
                    colored_print(f"  Port: {rule[1]} | Protocol: {rule[2]} | Action: {rule[3]}\n", 'white')
            else:
                colored_print("ℹ️  No active firewall rules\n", 'blue')

        elif choice == "4":
            confirm = input("⚠️  Flush ALL firewall rules? (y/N): ").lower()
            if confirm == 'y':
                try:
                    subprocess.run(["sudo", "iptables", "-F"], check=True)
                    with db.connect() as con:
                        con.execute("DELETE FROM firewall_rules")
                    log_action("All firewall rules flushed")
                    colored_print("✅ All firewall rules cleared!\n", 'green')
                except:
                    colored_print("❌ Failed to flush rules\n", 'red')

        elif choice == "5":
            break

# =========================
# LINK BLOCKER
# =========================
def block_link_menu():
    while True:
        colored_print("\n🔗 DOMAIN & LINK BLOCKER\n", 'purple', True)
        print("1. Block Domain/Link")
        print("2. Unblock Domain")
        print("3. List Blocked Domains")
        print("4. Back")
        choice = input("\n> ").strip()

        if choice == "1":
            url = input("Enter domain/link to block: ").strip()
            domain = urlparse(url).netloc or url
            reason = input("Reason for blocking (optional): ").strip()
            
            backup_hosts()
            try:
                with open("/etc/hosts", "a") as f:
                    f.write(f"\n127.0.0.1 {domain}\n0.0.0.0 {domain}\n")
                timestamp = datetime.now().isoformat()
                with db.connect() as con:
                    con.execute("INSERT OR IGNORE INTO blocked_domains (domain, blocked_at, reason) VALUES(?,?,?)",
                               (domain, timestamp, reason))
                log_action(f"Blocked domain: {domain}", reason)
                colored_print(f"✅ {domain} blocked successfully!\n", 'green')
            except PermissionError:
                colored_print("❌ Permission denied! Run with sudo or as root\n", 'red')

        elif choice == "2":
            domain = input("Domain to unblock: ").strip()
            try:
                # Restore from backup if exists
                if os.path.exists(BLOCKED_HOSTS_FILE):
                    subprocess.run(["sudo", "cp", BLOCKED_HOSTS_FILE, "/etc/hosts"], check=True)
                with db.connect() as con:
                    con.execute("DELETE FROM blocked_domains WHERE domain=?", (domain,))
                log_action(f"Unblocked domain: {domain}")
                colored_print(f"✅ {domain} unblocked!\n", 'green')
            except:
                colored_print("❌ Failed to unblock domain\n", 'red')

        elif choice == "3":
            with db.connect() as con:
                blocked = con.execute("SELECT * FROM blocked_domains").fetchall()
            if blocked:
                colored_print("📋 BLOCKED DOMAINS:\n", 'yellow')
                for domain in blocked:
                    colored_print(f"  ❌ {domain[1]} ({domain[3] or 'No reason'})\n", 'white')
            else:
                colored_print("ℹ️  No blocked domains\n", 'blue')

        elif choice == "4":
            break

# =========================
# NETWORK SCANNER
# =========================
def scan_network():
    colored_print("\n🌐 NETWORK SCANNER\n", 'cyan', True)
    base_ip = get_local_ip().rsplit('.', 1)[0] + '.'
    
    colored_print(f"🔍 Scanning network {base_ip}0/24...\n", 'yellow')
    log_action("Network scan started", f"Range: {base_ip}0/24")
    
    try:
        # Use scapy for ARP scan (more reliable)
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=base_ip+"0/24"), timeout=2, verbose=0)
        devices = []
        
        for sent, received in ans:
            device_info = {
                'ip': received.psrc,
                'mac': received.hwsrc,
                'hostname': socket.gethostbyaddr(received.psrc)[0] if socket.gethostbyaddr(received.psrc) else 'Unknown'
            }
            devices.append(device_info)
            
            # Log to database
            with db.connect() as con:
                con.execute("INSERT INTO network_scans VALUES(NULL,?,?,?,?)",
                           (datetime.now().isoformat(), received.psrc, device_info['hostname'], received.hwsrc))
        
        colored_print(f"✅ Scan complete! Found {len(devices)} devices:\n", 'green')
        for device in devices:
            device_type = identify_device_type(device['mac'])
            colored_print(f"  📱 {device['hostname']} | {device['ip']} | {device['mac'][:17]}... | {device_type}\n", 'white')
            
        log_action("Network scan completed", f"Found {len(devices)} devices")
        
    except Exception as e:
        colored_print(f"❌ Scan failed: {str(e)}\n", 'red')
        # Fallback ping scan
        for i in range(1, 255):
            ip = f"{base_ip}{i}"
            response = os.system(f"ping -c 1 -W 1 {ip} > /dev/null 2>&1")
            if response == 0:
                colored_print(f"  📱 Device found: {ip}\n", 'white')

def identify_device_type(mac):
    mac_prefixes = {
        '00:50:56': 'VMware',
        '00:0C:29': 'VMware',
        '08:00:27': 'VirtualBox',
        '02:XX:XX': 'iPhone/iPad',
        'D4:XX:XX': 'Samsung',
        'BC:XX:XX': 'Apple',
        'F0:XX:XX': 'Android'
    }
    mac = mac.upper()[:8]
    for prefix, device in mac_prefixes.items():
        if mac.startswith(prefix.replace('X', '')):
            return device
    return 'Unknown'

# =========================
# NETWORK STATUS
# =========================
def network_status():
    colored_print("\n📊 NETWORK STATUS\n", 'blue', True)
    
    # Network interfaces
    colored_print("🔌 NETWORK INTERFACES:\n", 'yellow')
    for interface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                colored_print(f"  {interface}: {addr['addr']}\n", 'white')
    
    # Active connections
    connections = psutil.net_connections()
    colored_print(f"\n🌐 ACTIVE CONNECTIONS: {len(connections)}\n", 'yellow')
    
    suspicious = 0
    for conn in connections[:10]:  # Show top 10
        if conn.raddr:
            status = "ESTABLISHED" if conn.status == 'ESTABLISHED' else conn.status
            colored_print(f"  {conn.laddr.ip}:{conn.laddr.port} → {conn.raddr.ip}:{conn.raddr.port} ({status})\n", 'white')
            if conn.raddr.ip not in ['127.0.0.1', '::1', get_local_ip()]:
                suspicious += 1
    
    if suspicious > 5:
        colored_print(f"⚠️  HIGH NETWORK ACTIVITY DETECTED! ({suspicious} external connections)\n", 'red', True)
        log_action("High network activity", f"{suspicious} suspicious connections")

# =========================
# SYSTEM SCANNER
# =========================
def system_scan_menu():
    while True:
        colored_print("\n🛡️ SYSTEM & FILE SCANNER\n", 'red', True)
        print("1. Full System Scan")
        print("2. Scan Specific File/Folder")
        print("3. View Suspicious Files")
        print("4. Quarantine File")
        print("5. Clear Suspicious")
        print("6. Back")
        choice = input("\n> ").strip()

        if choice == "1":
            scan_system_full()
        elif choice == "2":
            path = input("Enter file/folder path: ").strip()
            scan_file_or_folder(path)
        elif choice == "3":
            view_suspicious_files()
        elif choice == "4":
            quarantine_file()
        elif choice == "5":
            clear_suspicious()
        elif choice == "6":
            break

def scan_system_full():
    colored_print("🔍 FULL SYSTEM SCAN STARTED...\n", 'yellow')
    log_action("Full system scan started")
    suspicious_count = 0
    
    suspicious_patterns = ['.exe', '.bat', '.scr', '.pif', '.com', '.dll', '~$']
    
    for root, dirs, files in os.walk('/home', max_depth=3):  # Limit depth for performance
        for file in files:
            filepath = os.path.join(root, file)
            if any(file.endswith(pattern) for pattern in suspicious_patterns):
                reason = f"Suspicious extension: {file.split('.')[-1]}"
                add_suspicious_file(filepath, reason)
                suspicious_count += 1
                colored_print(f"⚠️  SUSPICIOUS: {filepath}\n")