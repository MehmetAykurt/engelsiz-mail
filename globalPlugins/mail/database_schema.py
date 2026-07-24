# -*- coding: utf-8 -*-
"""Engelsiz Mail SQLite şeması ve sürümlü göç tanımları."""


SCHEMA_VERSION = 8
BODY_PARSER_VERSION = 3


MIGRATION_1 = (
    """
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL COLLATE NOCASE,
        provider TEXT NOT NULL DEFAULT 'imap',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(email)
    )
    """,
    """
    CREATE TABLE folders (
        id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        imap_name TEXT NOT NULL,
        display_name TEXT NOT NULL,
        uidvalidity INTEGER,
        uidnext INTEGER,
        highest_modseq INTEGER,
        message_count INTEGER NOT NULL DEFAULT 0,
        unseen_count INTEGER NOT NULL DEFAULT 0,
        special_use TEXT,
        is_selectable INTEGER NOT NULL DEFAULT 1 CHECK (is_selectable IN (0, 1)),
        last_synced_at INTEGER,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(account_id, imap_name)
    )
    """,
    """
    CREATE TABLE messages (
        id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        gmail_message_id TEXT,
        gmail_thread_id TEXT,
        rfc_message_id TEXT,
        in_reply_to TEXT,
        references_header TEXT,
        subject TEXT NOT NULL DEFAULT '',
        sender TEXT NOT NULL DEFAULT '',
        recipients_to TEXT NOT NULL DEFAULT '',
        recipients_cc TEXT NOT NULL DEFAULT '',
        reply_to TEXT NOT NULL DEFAULT '',
        sent_at INTEGER,
        internal_date INTEGER,
        size_bytes INTEGER,
        preview TEXT NOT NULL DEFAULT '',
        has_attachments INTEGER NOT NULL DEFAULT 0 CHECK (has_attachments IN (0, 1)),
        headers_complete INTEGER NOT NULL DEFAULT 0 CHECK (headers_complete IN (0, 1)),
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE folder_messages (
        id INTEGER PRIMARY KEY,
        folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
        message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
        uidvalidity INTEGER NOT NULL,
        uid INTEGER NOT NULL,
        flags TEXT NOT NULL DEFAULT '',
        is_seen INTEGER NOT NULL DEFAULT 0 CHECK (is_seen IN (0, 1)),
        is_flagged INTEGER NOT NULL DEFAULT 0 CHECK (is_flagged IN (0, 1)),
        is_answered INTEGER NOT NULL DEFAULT 0 CHECK (is_answered IN (0, 1)),
        is_draft INTEGER NOT NULL DEFAULT 0 CHECK (is_draft IN (0, 1)),
        is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
        is_present INTEGER NOT NULL DEFAULT 1 CHECK (is_present IN (0, 1)),
        last_seen_at INTEGER NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(folder_id, uidvalidity, uid),
        UNIQUE(folder_id, message_id)
    )
    """,
    """
    CREATE TABLE message_bodies (
        message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
        plain_text TEXT NOT NULL DEFAULT '',
        html_text TEXT,
        raw_size_bytes INTEGER,
        fetched_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE attachments (
        id INTEGER PRIMARY KEY,
        message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
        part_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
        content_id TEXT,
        size_bytes INTEGER,
        sha256 TEXT,
        local_path TEXT,
        download_state TEXT NOT NULL DEFAULT 'not_downloaded'
            CHECK (download_state IN ('not_downloaded', 'downloading', 'downloaded', 'failed')),
        downloaded_at INTEGER,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(message_id, part_path)
    )
    """,
    """
    CREATE TABLE sync_state (
        folder_id INTEGER PRIMARY KEY REFERENCES folders(id) ON DELETE CASCADE,
        last_seen_uid INTEGER NOT NULL DEFAULT 0,
        initial_sync_complete INTEGER NOT NULL DEFAULT 0
            CHECK (initial_sync_complete IN (0, 1)),
        sync_cursor TEXT,
        last_started_at INTEGER,
        last_completed_at INTEGER,
        last_error TEXT,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at INTEGER NOT NULL
    )
    """,
    "CREATE INDEX idx_folders_account ON folders(account_id)",
    "CREATE INDEX idx_messages_account_date ON messages(account_id, internal_date DESC, id DESC)",
    "CREATE INDEX idx_messages_account_subject ON messages(account_id, subject COLLATE NOCASE)",
    "CREATE INDEX idx_messages_account_sender ON messages(account_id, sender COLLATE NOCASE)",
    "CREATE UNIQUE INDEX idx_messages_gmail_id ON messages(account_id, gmail_message_id) WHERE gmail_message_id IS NOT NULL",
    "CREATE INDEX idx_messages_rfc_id ON messages(account_id, rfc_message_id) WHERE rfc_message_id IS NOT NULL",
    "CREATE INDEX idx_folder_messages_list ON folder_messages(folder_id, is_present, uid DESC)",
    "CREATE INDEX idx_folder_messages_message ON folder_messages(message_id)",
    "CREATE INDEX idx_attachments_message ON attachments(message_id)",
    "CREATE UNIQUE INDEX idx_attachments_local_path ON attachments(local_path) WHERE local_path IS NOT NULL",
)


MIGRATION_2 = (
    "ALTER TABLE messages ADD COLUMN date_header TEXT",
)


MIGRATION_3 = (
    "ALTER TABLE message_bodies ADD COLUMN attachments_cached INTEGER NOT NULL DEFAULT 0 CHECK (attachments_cached IN (0, 1))",
)


MIGRATION_4 = (
    """
    CREATE TABLE pending_deletions (
        id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        operation_type TEXT NOT NULL CHECK (operation_type IN ('trash', 'permanent')),
        source_folder TEXT NOT NULL,
        source_category TEXT NOT NULL DEFAULT '',
        source_uid INTEGER NOT NULL,
        gmail_message_id TEXT,
        trash_folder TEXT NOT NULL,
        source_label TEXT NOT NULL DEFAULT '',
        remove_source_label INTEGER NOT NULL DEFAULT 0
            CHECK (remove_source_label IN (0, 1)),
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(account_id, operation_type, source_folder, source_uid)
    )
    """,
    "CREATE INDEX idx_pending_deletions_account ON pending_deletions(account_id, created_at, id)",
    "CREATE INDEX idx_pending_deletions_gmail_id ON pending_deletions(account_id, gmail_message_id) WHERE gmail_message_id IS NOT NULL",
)


MIGRATION_5 = (
    "ALTER TABLE pending_deletions ADD COLUMN source_uidvalidity INTEGER",
    "ALTER TABLE pending_deletions ADD COLUMN permanent_delete_started INTEGER NOT NULL DEFAULT 0 CHECK (permanent_delete_started IN (0, 1))",
)


MIGRATION_6 = (
    "ALTER TABLE pending_deletions ADD COLUMN request_token TEXT NOT NULL DEFAULT ''",
)


MIGRATION_7 = (
    "ALTER TABLE message_bodies ADD COLUMN parser_version INTEGER NOT NULL DEFAULT 1",
)


MIGRATION_8 = (
    "CREATE INDEX idx_messages_account_thread_date ON messages(account_id, gmail_thread_id, internal_date DESC, id DESC) WHERE gmail_thread_id IS NOT NULL",
)


MIGRATIONS = {
    1: MIGRATION_1,
    2: MIGRATION_2,
    3: MIGRATION_3,
    4: MIGRATION_4,
    5: MIGRATION_5,
    6: MIGRATION_6,
    7: MIGRATION_7,
    8: MIGRATION_8,
}
