import httpx
import asyncio
import datetime
from typing import List, Dict, Any, Optional, Callable, Coroutine

class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.stopped = False
        self.offset = 0

    async def send_message(self, text: str):
        if not self.bot_token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=15.0)
                if resp.status_code != 200:
                    from src.core.logger import logger
                    logger.error(f"[Telegram] Помилка відправки: {resp.text}")
        except Exception as e:
            from src.core.logger import logger
            logger.error(f"[Telegram] Exception: {e}")

    def build_cycle_report(self, cycle: int, total_cycles: int, wallet_results: List[Dict[str, Any]]) -> str:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"🔵 <b>Nemesis Testnet Bot</b>",
            f"📅 {now}",
            f"🔄 Цикл {cycle}/{total_cycles} завершено",
            ""
        ]

        for w in wallet_results:
            addr = f"{w['address'][:6]}...{w['address'][-4:]}"
            lines.append(f"👛 <b>{w['name']}</b> <code>{addr}</code>")
            
            # Detailed stats
            s = w.get("stats", {})
            lines.append(f"   🔄 Swaps: {s.get('swaps', 0)} | 💧 Liq: {s.get('liquidity', 0)}")
            lines.append(f"   📈 Long: {s.get('longs', 0)} | 📉 Short: {s.get('shorts', 0)}")
            
            actions_line = f"   ✅ Дій: {w.get('sessionActions', 0)}"
            errors_count = w.get('sessionErrors', 0)
            if errors_count > 0:
                actions_line += f" | ❌ Помилок: {errors_count}"
            lines.append(actions_line)
            
            lines.append(f"   🏃 Run #{w['runCount']}")
            lines.append("")

        if total_cycles != 0 and cycle < total_cycles:
            lines.append("⏭ Наступний цикл почнеться скоро...")
        else:
            lines.append("🎉 Всі цикли завершено!")
            lines.append("Перезапуск: /runnemesis")

        return "\n".join(lines)

    async def start_polling(self, on_command: Callable[[], Coroutine[Any, Any, None]], run_command: str = "/runnemesis"):
        # Initial offset sync
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset=-1&timeout=0"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok") and data.get("result"):
                        self.offset = data["result"][-1]["update_id"] + 1
        except Exception:
            pass

        while not self.stopped:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.offset}&timeout=30&allowed_updates=[\"message\"]"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=35.0)
                    if resp.status_code != 200:
                        await asyncio.sleep(5)
                        continue
                    
                    data = resp.json()
                    if not data.get("ok"):
                        await asyncio.sleep(5)
                        continue

                    for upd in data.get("result", []):
                        self.offset = upd["update_id"] + 1
                        msg = upd.get("message")
                        if not msg:
                            continue
                        
                        chat_id = str(msg.get("chat", {}).get("id"))
                        if chat_id != self.chat_id:
                            continue
                        
                        text = (msg.get("text") or "").strip().lower()
                        if text in [run_command, "/run", "/start"]:
                            asyncio.create_task(on_command())

            except Exception as e:
                # print(f"[Telegram Polling] Error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self.stopped = True
