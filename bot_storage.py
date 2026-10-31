from contextlib import contextmanager
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Iterator


CREATOR_USERNAME = "ibrahimroblox14grm"
CREATOR_ACCOUNT_KEY = "creator"
TRANSFER_FEE = 10
FLAG_REWARD = 50
SALARY_COOLDOWN_SECONDS = 60 * 60
RPS_REWARD = 250
NUMBER_GUESS_REWARD = 300
RAFFLE_REWARD = 30

DATABASE_PATH = Path(__file__).resolve().parent / "data" / "bot.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_key TEXT PRIMARY KEY,
    telegram_user_id INTEGER UNIQUE,
    username TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL,
    card_number TEXT NOT NULL UNIQUE,
    points INTEGER NOT NULL DEFAULT 0 CHECK (points >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flag_games (
    chat_id INTEGER PRIMARY KEY,
    country_code TEXT NOT NULL,
    started_by INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS salary_claims (
    telegram_user_id INTEGER PRIMARY KEY,
    claimed_at INTEGER NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


@contextmanager
def _transaction() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_storage() -> None:
    connection = _connect()
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)
    finally:
        connection.close()


def _allocate_card_number(connection: sqlite3.Connection) -> str:
    while True:
        # 9 is reserved for these non-payment game cards.
        card_number = f"9{secrets.randbelow(10**15):015d}"
        existing = connection.execute(
            "SELECT 1 FROM accounts WHERE card_number = ?",
            (card_number,),
        ).fetchone()
        if existing is None:
            return card_number


def _get_account_key(
    connection: sqlite3.Connection,
    telegram_user_id: int | None,
    username: str | None,
) -> str:
    if telegram_user_id is None:
        return CREATOR_ACCOUNT_KEY

    normalized_username = (username or "").strip().lstrip("@").casefold()
    is_creator_username = normalized_username == CREATOR_USERNAME.casefold()

    current_account = connection.execute(
        "SELECT account_key FROM accounts WHERE telegram_user_id = ?",
        (telegram_user_id,),
    ).fetchone()
    creator_account = connection.execute(
        "SELECT account_key, telegram_user_id FROM accounts WHERE account_key = ?",
        (CREATOR_ACCOUNT_KEY,),
    ).fetchone()

    creator_id_is_unclaimed = (
        creator_account is None
        or creator_account["telegram_user_id"] is None
        or creator_account["telegram_user_id"] == telegram_user_id
    )
    if is_creator_username and creator_id_is_unclaimed:
        if current_account and current_account["account_key"] != CREATOR_ACCOUNT_KEY:
            old_key = current_account["account_key"]
            if creator_account is None:
                connection.execute(
                    "UPDATE accounts SET account_key = ? WHERE account_key = ?",
                    (CREATOR_ACCOUNT_KEY, old_key),
                )
            else:
                old_account = connection.execute(
                    "SELECT points FROM accounts WHERE account_key = ?",
                    (old_key,),
                ).fetchone()
                connection.execute(
                    "UPDATE accounts SET points = points + ? WHERE account_key = ?",
                    (old_account["points"], CREATOR_ACCOUNT_KEY),
                )
                connection.execute(
                    "DELETE FROM accounts WHERE account_key = ?",
                    (old_key,),
                )
        return CREATOR_ACCOUNT_KEY

    if current_account:
        return current_account["account_key"]
    return f"user:{telegram_user_id}"


def _ensure_account(
    connection: sqlite3.Connection,
    telegram_user_id: int | None,
    username: str | None,
    display_name: str,
) -> dict[str, object]:
    account_key = _get_account_key(connection, telegram_user_id, username)
    username_value = (username or "").strip().lstrip("@")
    account = connection.execute(
        "SELECT * FROM accounts WHERE account_key = ?",
        (account_key,),
    ).fetchone()

    if account is None:
        connection.execute(
            """
            INSERT INTO accounts (
                account_key, telegram_user_id, username, display_name, card_number
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                account_key,
                telegram_user_id,
                username_value,
                display_name,
                _allocate_card_number(connection),
            ),
        )
    else:
        connection.execute(
            """
            UPDATE accounts
            SET telegram_user_id = COALESCE(telegram_user_id, ?),
                username = ?,
                display_name = ?
            WHERE account_key = ?
            """,
            (telegram_user_id, username_value, display_name, account_key),
        )

    saved_account = connection.execute(
        "SELECT * FROM accounts WHERE account_key = ?",
        (account_key,),
    ).fetchone()
    return dict(saved_account)


def _ensure_creator_account(connection: sqlite3.Connection) -> dict[str, object]:
    return _ensure_account(
        connection,
        telegram_user_id=None,
        username=CREATOR_USERNAME,
        display_name="Ibrahimroblox14GRM",
    )


def _user_fields(
    telegram_user_id: int,
    username: str | None,
    display_name: str,
) -> tuple[int, str | None, str]:
    return telegram_user_id, username, display_name


def create_or_get_account(
    telegram_user_id: int,
    username: str | None,
    display_name: str,
) -> dict[str, object]:
    with _transaction() as connection:
        account = _ensure_account(
            connection,
            *_user_fields(telegram_user_id, username, display_name),
        )
        return account


def award_points(
    telegram_user_id: int,
    username: str | None,
    display_name: str,
    amount: int,
) -> dict[str, object]:
    if amount <= 0:
        raise ValueError("Award amount must be positive.")

    with _transaction() as connection:
        account = _ensure_account(
            connection,
            telegram_user_id,
            username,
            display_name,
        )
        connection.execute(
            "UPDATE accounts SET points = points + ? WHERE account_key = ?",
            (amount, account["account_key"]),
        )
        updated_account = connection.execute(
            "SELECT * FROM accounts WHERE account_key = ?",
            (account["account_key"],),
        ).fetchone()
        return dict(updated_account)


def deposit_salary(
    telegram_user_id: int,
    username: str | None,
    display_name: str,
    base_salary: int,
    tip: int,
    now: int | None = None,
) -> dict[str, object]:
    claimed_at = int(time.time()) if now is None else now
    with _transaction() as connection:
        previous_claim = connection.execute(
            "SELECT claimed_at FROM salary_claims WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        if previous_claim is not None:
            elapsed = claimed_at - int(previous_claim["claimed_at"])
            remaining_seconds = SALARY_COOLDOWN_SECONDS - elapsed
            if remaining_seconds > 0:
                remaining_minutes = (remaining_seconds + 59) // 60
                return {
                    "status": "cooldown",
                    "remaining_minutes": remaining_minutes,
                }

        account = _ensure_account(
            connection,
            telegram_user_id,
            username,
            display_name,
        )
        total = base_salary + tip
        connection.execute(
            "UPDATE accounts SET points = points + ? WHERE account_key = ?",
            (total, account["account_key"]),
        )
        connection.execute(
            """
            INSERT INTO salary_claims (telegram_user_id, claimed_at)
            VALUES (?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                claimed_at = excluded.claimed_at
            """,
            (telegram_user_id, claimed_at),
        )
        updated_account = connection.execute(
            "SELECT * FROM accounts WHERE account_key = ?",
            (account["account_key"],),
        ).fetchone()
        return {
            "status": "ok",
            "account": dict(updated_account),
            "base_salary": base_salary,
            "tip": tip,
            "total": total,
        }


def get_creator_identity(telegram_user_id: int, username: str | None) -> bool:
    normalized_username = (username or "").strip().lstrip("@").casefold()
    if normalized_username == CREATOR_USERNAME.casefold():
        return True

    connection = _connect()
    try:
        creator_account = connection.execute(
            "SELECT telegram_user_id FROM accounts WHERE account_key = ?",
            (CREATOR_ACCOUNT_KEY,),
        ).fetchone()
        return bool(
            creator_account
            and creator_account["telegram_user_id"] == telegram_user_id
        )
    finally:
        connection.close()


def start_flag_game(chat_id: int, country_code: str, started_by: int) -> None:
    with _transaction() as connection:
        connection.execute(
            """
            INSERT INTO flag_games (chat_id, country_code, started_by)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                country_code = excluded.country_code,
                started_by = excluded.started_by,
                started_at = CURRENT_TIMESTAMP
            """,
            (chat_id, country_code, started_by),
        )


def active_flag_country(chat_id: int) -> str | None:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT country_code FROM flag_games WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return str(row["country_code"]) if row else None
    finally:
        connection.close()


def claim_flag_answer(
    chat_id: int,
    expected_country_code: str,
    normalized_answer: str,
    accepted_answers: set[str],
    telegram_user_id: int,
    username: str | None,
    display_name: str,
) -> dict[str, object] | None:
    if normalized_answer not in accepted_answers:
        return None

    with _transaction() as connection:
        game = connection.execute(
            "SELECT country_code FROM flag_games WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if game is None:
            return None
        if game["country_code"] != expected_country_code:
            return None

        claimed = connection.execute(
            "DELETE FROM flag_games WHERE chat_id = ? AND country_code = ?",
            (chat_id, game["country_code"]),
        )
        if claimed.rowcount != 1:
            return None

        account = _ensure_account(
            connection,
            *_user_fields(telegram_user_id, username, display_name),
        )
        connection.execute(
            "UPDATE accounts SET points = points + ? WHERE account_key = ?",
            (FLAG_REWARD, account["account_key"]),
        )
        updated_account = connection.execute(
            "SELECT * FROM accounts WHERE account_key = ?",
            (account["account_key"],),
        ).fetchone()
        return dict(updated_account)


def transfer_points(
    sender_user_id: int,
    sender_username: str | None,
    sender_display_name: str,
    amount: int,
    recipient_user_id: int | None = None,
    recipient_username: str | None = None,
    recipient_display_name: str | None = None,
    recipient_card_number: str | None = None,
) -> dict[str, object]:
    with _transaction() as connection:
        sender_key = _get_account_key(
            connection,
            sender_user_id,
            sender_username,
        )
        sender = connection.execute(
            "SELECT * FROM accounts WHERE account_key = ?",
            (sender_key,),
        ).fetchone()
        if sender is None:
            return {"status": "no_account"}

        if recipient_card_number:
            recipient = connection.execute(
                "SELECT * FROM accounts WHERE card_number = ?",
                (recipient_card_number.replace(" ", ""),),
            ).fetchone()
            if recipient is None:
                return {"status": "unknown_card"}
            recipient_key = str(recipient["account_key"])
        elif recipient_user_id is not None:
            recipient = _ensure_account(
                connection,
                recipient_user_id,
                recipient_username,
                recipient_display_name or "عضو",
            )
            recipient_key = str(recipient["account_key"])
        else:
            return {"status": "missing_recipient"}

        if recipient_key == sender_key:
            return {"status": "self_transfer"}

        required_balance = amount + TRANSFER_FEE
        if int(sender["points"]) < required_balance:
            return {
                "status": "insufficient_balance",
                "balance": int(sender["points"]),
                "required": required_balance,
            }

        creator = _ensure_creator_account(connection)
        connection.execute(
            "UPDATE accounts SET points = points - ? WHERE account_key = ?",
            (required_balance, sender_key),
        )
        connection.execute(
            "UPDATE accounts SET points = points + ? WHERE account_key = ?",
            (amount, recipient_key),
        )
        connection.execute(
            "UPDATE accounts SET points = points + ? WHERE account_key = ?",
            (TRANSFER_FEE, creator["account_key"]),
        )

        updated_sender = connection.execute(
            "SELECT * FROM accounts WHERE account_key = ?",
            (sender_key,),
        ).fetchone()
        updated_recipient = connection.execute(
            "SELECT * FROM accounts WHERE account_key = ?",
            (recipient_key,),
        ).fetchone()
        updated_creator = connection.execute(
            "SELECT * FROM accounts WHERE account_key = ?",
            (creator["account_key"],),
        ).fetchone()

        return {
            "status": "ok",
            "sender": dict(updated_sender),
            "recipient": dict(updated_recipient),
            "creator": dict(updated_creator),
            "amount": amount,
            "fee": TRANSFER_FEE,
        }
