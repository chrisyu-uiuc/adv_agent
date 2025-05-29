-- Schema for the restaurant reservation system

-- Menu items table
CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('food', 'drink')),
    price REAL NOT NULL
);

-- Tables table
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER UNIQUE NOT NULL,
    capacity INTEGER NOT NULL
);

-- Reservations table
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL,
    guest_name TEXT,
    num_guests INTEGER NOT NULL,
    reservation_time TEXT NOT NULL, -- Format: YYYY-MM-DD HH:MM:SS
    FOREIGN KEY(table_id) REFERENCES tables(id)
);
