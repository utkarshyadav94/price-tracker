# E-Commerce Price & Stock Tracker

A simple Streamlit app that lets you track product prices and stock status from e-commerce product pages.

## Features

- Add a product URL and target price
- Scrape the latest price and stock status
- View tracked products in a table
- See historical price trends over time
- Optional Telegram notifications for price changes

## Requirements

- Python 3.10+
- Dependencies listed in requirements.txt

## Setup

1. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```powershell
   playwright install
   ```

4. Optional: configure Telegram environment variables:
   ```powershell
   $env:TELEGRAM_BOT_TOKEN="your_token"
   $env:TELEGRAM_CHAT_ID="your_chat_id"
   ```

## Run the app

```powershell
streamlit run app.py
```

Then open the local URL shown in the terminal, usually http://localhost:8501.

## Project structure

- app.py: Streamlit UI
- scraper.py: scraping logic
- tracker_engine.py: scheduled tracking logic
- database.py: database operations
- telegram_bot.py: Telegram integration
- config.py: configuration settings

## Notes

- The app stores local data in the data folder and database files.
- These files are ignored by Git via .gitignore.
