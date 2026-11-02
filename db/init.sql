CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    task_points INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE rand_source (
    id SERIAL PRIMARY KEY,
    avail_dt TIMESTAMPTZ,
    rand_val TEXT
);

CREATE TABLE task_type (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    points INTEGER NOT NULL
);

CREATE TABLE period (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    start_dt TIMESTAMPTZ NOT NULL,
    end_dt TIMESTAMPTZ NOT NULL
);

CREATE TABLE raffle (
    id SERIAL PRIMARY KEY,
    period_id INTEGER NOT NULL REFERENCES period(id),
    start_dt TIMESTAMPTZ,
    end_dt TIMESTAMPTZ,
    rand_source_id INTEGER REFERENCES rand_source(id)
);

CREATE TABLE task_set (
    id SERIAL PRIMARY KEY,
    task_type_id INTEGER NOT NULL REFERENCES task_type(id),
    period_id INTEGER NOT NULL REFERENCES period(id),
    manpower_need INTEGER NOT NULL,
    start_dt TIMESTAMPTZ NOT NULL,
    end_dt TIMESTAMPTZ NOT NULL
);

CREATE TABLE assignment (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    task_set_id INTEGER NOT NULL REFERENCES task_set(id),
    status TEXT NOT NULL
);

CREATE TABLE unavailable (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    start_dt TIMESTAMPTZ NOT NULL,
    end_dt TIMESTAMPTZ NOT NULL,
    details TEXT
);

CREATE TABLE log (
    id SERIAL PRIMARY KEY,
    event_name TEXT NOT NULL,
    log_dt TIMESTAMPTZ NOT NULL DEFAULT now(),
    reveal_dt TIMESTAMPTZ,
    details TEXT
);

-- Sample data for the home page and e2e test
INSERT INTO users (name) VALUES ('Alice'), ('Bob');
