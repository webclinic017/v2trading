# V2TRADING - Advanced Algorithmic Trading Platform

## Overview
Custom-built algorithmic trading platform for research, backtesting and automated trading. Trading engine capable of processing tick data, managing trades, and supporting backtesting in a highly accurate and efficient manner.

## Key Features
- **Trading Engine**: At the core of the platform is a trading engine that processes tick data in real time. This engine is responsible for aggregating data and managing the execution of trades, ensuring precision and speed in trade placement and execution.

- **High-Fidelity Backtesting Environment**: ability to backtest strategies with 1:1 precision - meaning a tick-by-tick backtesting. This level of precision in backtesting, down to millisecond accuracy, mirrors live trading environments and is vital for developing and testing high-frequency trading strategies.

- **Custom Data Aggregation:** The platform includes a data aggregator that allows for custom aggregation rules. This flexibility supports a variety of data analysis approaches, including non-time based bars and other unique criteria.

- **Indicators** Contains inbuild [tulipy](https://tulipindicators.org/list) [ta-lib](https://ta-lib.github.io/ta-lib-python/) and templates for custom build multioutputs stateful indicators.

- **Machine Learning Integration:** Recently, the platform has expanded to incorporate machine learning capabilities. This includes modules for both training and inference, supporting the complete ML lifecycle. These ML models can be utilized within trading strategies for classification and exploiting statistical advantages.

**Technology Stack**
**Backend and API:** The backbone of the platform is built with Python, utilizing libraries such as FastAPI, NumPy, Keras, and JAX, ensuring high performance and scalability.
**Frontend:** The client-side is developed with Vanilla JavaScript and jQuery, employing LightweightCharts for charting purposes. Additional modules enhance the platform's functionality. The frontend is slated for a future refactoring to modern frameworks like Vue.js and Vuetify for a more robust user interface.

While the platform is fully functional and growing, ongoing development is planned, particularly in the realm of frontend enhancements and further integration of advanced machine learning techniques.

**Contributions**
Contributions to this project are welcome. Whether it's improving the frontend, enhancing the backend capabilities, or experimenting with new trading strategies and machine learning models, your input can help take this platform to the next level.

This repository represents a sophisticated and evolving tool for algorithmic traders, offering precision, speed, and a level of customization that is unparalleled in open-source systems. Join us in shaping the future of algorithmic trading.

<p align="center">
  Main screen with entry/exit points and stoploss lines<br>
  <img width="700" alt="Main screen with entry/exit points and stoploss lines" src="https://github.com/drew2323/v2trading/assets/28433232/751d5b0e-ef64-453f-8e76-89a39db679c5">
</p>

<p align="center">
  Main screen with tick based indicators<br>
  <img width="700" alt="Main screen with tick based indicators" src="https://github.com/drew2323/v2trading/assets/28433232/4bf6128c-9b36-4e88-9da1-5a33319976a1">
</p>

<p align="center">
  Indicator editor<br>
  <img width="700" alt="Indicator editor" src="https://github.com/drew2323/v2trading/assets/28433232/cc417393-7b88-4eea-afcb-3a00402d0a8d">
</p>

<p align="center">
  Strategy editor<br>
  <img width="700" alt="Strategy editor" src="https://github.com/drew2323/v2trading/assets/28433232/74f67e7a-1efc-4f63-b763-7827b2337b6a">
</p>

<p align="center">
  Strategy analytical tools<br>
  <img width="700" alt="Strategy analytical tools" src="https://github.com/drew2323/v2trading/assets/28433232/4bf8b3c3-e430-4250-831a-e5876bb6b743">
</p>


# Installation Instructions
This document outlines the steps for installing and setting up the necessary environment for the application. These instructions are applicable for both Windows and Linux operating systems. Please follow the steps carefully to ensure a smooth setup.

## Prerequisites
Before beginning the installation process, ensure the following prerequisites are met:

- Git Bash: Required for cloning the repository and executing shell commands.
- TA-Lib Library:
  - Windows: Download and build the TA-Lib library. Install Visual Studio Community with the Visual C++ feature. Navigate to `C:\ta-lib\c\make\cdr\win32\msvc` in the command prompt and build the library using the available makefile.
  - Linux: Install TA-Lib using your distribution's package manager or compile from source following the instructions available on the TA-Lib GitHub repository.
- VSCode: Ensure VSCode is installed and the Python interpreter is properly set.
- Alpaca Paper Trading Account: Create an account at [Alpaca Markets](https://alpaca.markets/) and generate `API_KEY` and `SECRET_KEY` for your paper trading account.

## Installation Steps
**Clone the Repository:** Clone the remote repository to your local machine.
   `git clone git@github.com:drew2323/v2trading.git <name_of_local_folder>`
**Install Python:** Ensure Python 3.10.11 is installed on your system.
**Create a Virtual Environment:** Set up a Python virtual environment.
   `python -m venv <path_to_venv_folder>`
**Activate Virtual Environment:**
   - Windows: `source ./<venv_folder>/Scripts/activate`
   - Linux: `source ./<venv_folder>/bin/activate`
**Install Dependencies:** Install the program requirements.
   pip install -r requirements.txt
   Note: It's permissible to comment out references to `keras` and `tensorflow` modules, as well as the `ml-room` repository in `requirements.txt`.
**Branching:** Establish and switch to a new branch for your modifications.
**Environment Variables:** In `run.sh`, modify the `VIRTUAL_ENV_DIR` and `PYTHON_TO_USE` variables as necessary.
**Configuration:** In `v2realbot/config.py`, update the `DATA_DIR` path using the `user_data_dir` function with an additional `author` parameter.
   `DATA_DIR = user_data_dir("v2realbot", "david")`
**jQuery Script Tag:** In `v2realbot/static/index.html`, use the jQuery script tag without `integrity` and `crossorigin` attributes.
**Git Staging:** Add modified files to the git staging area.
    git add .
**Commit Changes:** Commit your changes with an appropriate message.
    git commit -m '<commit_message>'
**Data Directory:** Navigate to `DATA_DIR` and create folders: `aggcache`, `tradecache`, and `models`.
**Media and Static Folders:** Create `media` and `static` folders one level above the repository directory. Also create `.env` file there.
**Database Setup:** Create the `v2trading.db` file using SQL commands from `v2trading_create_db.sql`.
```
    import sqlite3
    with open("v2trading_create_db.sql", "r") as f:
        sql_statements = f.read()
    conn = sqlite3.connect('v2trading.db')
    cursor = conn.cursor()
    cursor.executescript(sql_statements)
    conn.commit()
    conn.close()
```
Ensure the `config_table` is not empty by making an initial entry.
Environment Variables for API Keys: in .env file create environment variables for `ACCOUNT1_PAPER_API_KEY` and `ACCOUNT1_PAPER_SECRET_KEY` with values from your Alpaca account.
**Start the Application:** Run `main.py` in VSCode to start the application.
**Accessing the Application: **If the uvicorn server runs successfully at `http://0.0.0.0:8000`, access the application at `http://localhost:8000/static/`.
**Database Configuration:** Add dynamic button and JS configurations to the `config_table` in `v2trading.db` via the "Config" section on the main page.
Please replace placeholders (e.g., `<name_of_local_folder>`, `<path_to_venv_folder>`) with your actual paths and details. Follow these instructions to ensure the application is set up correctly and ready for use.

## Environmental variables
Trading platform can support N different accounts. Their API keys are stored as environmental variables in .env file located in the root directory.
Account for trading api is selected when each strategy is run. However for realtime websocket data), always ACCOUNT1 is used for all strategies. The data point selection (iex vs sip) is set by LIVE_DATA_FEED environment variable.  

.env file should contain:

```
ACCOUNT1_LIVE_API_KEY=<ACCOUNT1_LIVE_API_KEY>
ACCOUNT1_LIVE_SECRET_KEY=<ACCOUNT1_LIVE_SECRET_KEY>
ACCOUNT1_LIVE_FEED=sip
ACCOUNT1_PAPER_API_KEY=<ACCOUNT1_PAPER_API_KEY>
ACCOUNT1_PAPER_SECRET_KEY=<ACCOUNT1_PAPER_SECRET_KEY>
ACCOUNT1_PAPER_FEED=sip
ACCOUNT2_PAPER_API_KEY=<ACCOUNT2_PAPER_API_KEY>
ACCOUNT2_PAPER_SECRET_KEY=ACCOUNT2_PAPER_SECRET_KEY<>
ACCOUNT2_PAPER_FEED=iex
WEB_API_KEY=<pass-for-webapi>
```


