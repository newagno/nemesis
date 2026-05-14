import os
from eth_account import Account
from typing import List, Dict, Any

def load_wallets(file_path: str) -> List[Dict[str, str]]:
    wallets = []
    if not os.path.exists(file_path):
        return wallets
    
    with open(file_path, "r") as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            pk = line.strip()
            if not pk or pk.startswith("#"):
                continue
            try:
                acc = Account.from_key(pk)
                addr = acc.address
                
                # Custom naming logic
                if addr.lower() == "0x8B3657e0a27BccD0d93c73DE19Ee1471923Ea03d".lower():
                    name = "MM"
                elif addr.lower() == "0x4C06F9735dD261948332a691456EF0e611e91ad6".lower():
                    name = "665"
                else:
                    name = f"Wallet_{i+1}"
                    
                wallets.append({"pk": pk, "address": addr, "name": name})
            except Exception as e:
                print(f"[Wallets] Error parsing key at line {i+1}: {e}")
                
    return wallets
