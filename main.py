import asyncio
import sys
import os
from src.core.logger import logger
from src.core.telegram import TelegramClient
from src.runner.config import load_config
from src.runner.runner import run_cycle

async def main():
    logger.info("Initializing NemesisTestnetBot...")
    
    try:
        cfg = load_config()
    except Exception as e:
        logger.error(f"Помилка завантаження конфігурації: {e}")
        return

    tg = TelegramClient(cfg["telegram"]["botToken"], cfg["telegram"]["chatId"])
    
    current_cycle = 1
    total_cycles = cfg.get("cycles", 1)
    
    # Флаг для запобігання паралельних запусків
    running = False
    
    async def on_run_command():
        nonlocal running, current_cycle
        if running:
            await tg.send_message("⚠️ <b>Бот вже виконує цикл!</b> Будь ласка, зачекайте завершення.")
            logger.warning("Бот вже виконує цикл!")
            return
            
        running = True
        logger.info(f"🚀 Запуск циклу {current_cycle}...")
        await tg.send_message(f"🚀 <b>Запуск циклу {current_cycle}...</b>\nЦе може зайняти деякий час.")
        
        try:
            results = await run_cycle(cfg, current_cycle)
            
            # Надіслати звіт в Telegram
            report = tg.build_cycle_report(current_cycle, total_cycles, results)
            await tg.send_message(report)
            
            current_cycle += 1
            if total_cycles != 0 and current_cycle > total_cycles:
                logger.info("🎉 Всі цикли завершено!")
                current_cycle = 1 
            
        except Exception as e:
            logger.error(f"Помилка виконання циклу: {e}")
        finally:
            running = False
            logger.info("⏸️ Чекаю команди /runnemesis")

    # Start Telegram polling in background
    logger.info("📡 Запуск Telegram polling...")
    polling_task = asyncio.create_task(tg.start_polling(on_run_command, run_command="/runnemesis"))
    
    logger.info("✅ Бот готов і запускається!")
    await tg.send_message("🚀 <b>Бот Nemesis запущено!</b>\n\nПерший цикл починається автоматично...")
    
    # Trigger first run immediately
    asyncio.create_task(on_run_command())
    
    # Keep the main loop alive
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Зупинка бота...")
        tg.stop()
        polling_task.cancel()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
