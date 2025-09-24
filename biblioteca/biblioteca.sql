CREATE TABLE IF NOT EXISTS prestamo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    grado TEXT NOT NULL,
    curso TEXT NOT NULL,
    libro TEXT NOT NULL,
    dias INTEGER NOT NULL,
    correo TEXT NOT NULL,
    fecha_prestamo TEXT,
    devuelto INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS libro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    autor TEXT NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS usuario (
    correo TEXT PRIMARY KEY,
    nombre TEXT
);

