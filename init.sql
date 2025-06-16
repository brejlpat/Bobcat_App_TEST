-- Tabulka uživatelů
CREATE TABLE IF NOT EXISTS users_ad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT NOT NULL UNIQUE,
    role TEXT DEFAULT 'user',
    registry_date TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Dummy záznam admina, aby bylo možné se přihlásit
INSERT OR IGNORE INTO users_ad (username, email, role)
VALUES ('patrikbrejla', 'patrik.brejla@doosan.com', 'admin');

INSERT OR IGNORE INTO users_ad (username, email, role)
VALUES ('borekmiklas', 'borek.miklas@doosan.com', 'admin');

-- Tabulka login
CREATE TABLE IF NOT EXISTS login (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    token_expiration TEXT,
    login_date TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabulka pro záznam úprav zařízení
CREATE TABLE IF NOT EXISTS device_edit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    channel_name TEXT,
    payload TEXT,  -- SQLite nemá JSONB, použijeme TEXT (parsovat přes Python)
    device_edit_date TEXT DEFAULT CURRENT_TIMESTAMP,
    action TEXT,
    driver TEXT
);

-- Tabulka pro embeddingy
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT,
    device TEXT,
    embedding TEXT,  -- ukládáme JSON list jako string
    ip_address TEXT,
    driver TEXT
);
