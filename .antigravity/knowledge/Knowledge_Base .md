Ти створюєш Python-бота для тестнету Nemesis.trade (V1 Testnet на Ethereum Sepolia).

Попередні два боти (Tempo та ARC), код яких лежить у папці knowledge/, мають таку архітектуру:

- src/core/ — logger, rng (мульберрі32 + seed), utils, types, telegram
- src/actions/ — всі on-chain дії (approve, swap, deploy, faucet тощо)
- src/runner/ — runner.ts (планування дій, цикли, delays, state.json, wallets)
- src/user.settings.ts + runner.config.ts — зручний конфіг для юзера
- wallets.txt — приватні ключі (ніколи не комітити)
- Telegram-управління: /run, /runtempo, /runarc + звіти після циклів + повідомлення про помилки

Бот має бути максимально схожий за стилем:
- рандомізовані затримки (human-like)
- збереження стану після кожної дії
- кілька гаманців
- cycles + delays
- кольоровий лог + JSON-лог
- graceful shutdown
- анти-сибіл (широкі діапазони, різні паузи, не однакові суми)

Тепер робимо новий бот — **NemesisTestnetBot** на чистому Python (web3.py + python-telegram-bot або aiogram).

Мета бота: автоматизувати тестнет-активність на https://nemesis.trade/trade
Основні дії, які потрібні:
- перевіряти баланс ETH + USDC
- swap (ETH ↔ USDC, інші токени)
- long/short з левериджем
- add/remove liquidity в OMM-пули
- faucet-check (якщо ETH/USDC < поріг — пропускати)

RPC: Sepolia (Alchemy або Google Cloud faucet)
Фаусети: https://cloud.google.com/application/web3/faucet/ethereum/sepolia та Alchemy.

Структура проекту має бути такою самою, як у попередніх ботах, тільки на Python.