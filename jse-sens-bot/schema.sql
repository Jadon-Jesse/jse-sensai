DROP TABLE IF EXISTS sens;

CREATE TABLE sens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    filename TEXT NOT NULL,
    gptreview TEXT NOT NULL
);