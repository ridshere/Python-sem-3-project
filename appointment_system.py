"""
Appointment Booking & Reminder System
-------------------------------------
A mini project using only the Python standard library.

Features:
  - Book, view, reschedule and cancel appointments
  - Prevents double-booking (30-minute slots)
  - Background thread that shows reminders for upcoming appointments
  - Data stored permanently in a SQLite file (appointments.db)

Run:  python appointment_system.py
"""

import sqlite3
import threading
import time
from datetime import datetime, timedelta

DB_FILE = "appointments.db"
DT_FORMAT = "%Y-%m-%d %H:%M"
SLOT_MINUTES = 30          # length of every appointment
REMINDER_BEFORE_MIN = 60   # remind this many minutes before start
CHECK_INTERVAL_SEC = 30    # how often the reminder thread checks


# ---------- Database ----------
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS appointments (
                   id        INTEGER PRIMARY KEY AUTOINCREMENT,
                   name      TEXT NOT NULL,
                   phone     TEXT NOT NULL,
                   purpose   TEXT,
                   start     TEXT NOT NULL,
                   reminded  INTEGER DEFAULT 0
               )"""
        )


# ---------- Helpers ----------
def parse_dt(text):
    try:
        return datetime.strptime(text.strip(), DT_FORMAT)
    except ValueError:
        return None


def has_conflict(start, ignore_id=None):
    """True if another appointment overlaps the given start time."""
    with get_conn() as conn:
        rows = conn.execute("SELECT id, start FROM appointments").fetchall()
    for row in rows:
        if row["id"] == ignore_id:
            continue
        other = datetime.strptime(row["start"], DT_FORMAT)
        if abs((other - start).total_seconds()) < SLOT_MINUTES * 60:
            return True
    return False


def ask_datetime(prompt):
    while True:
        dt = parse_dt(input(prompt))
        if dt is None:
            print("  Invalid format. Use YYYY-MM-DD HH:MM (e.g. 2026-12-01 14:30)")
        elif dt < datetime.now():
            print("  That time is in the past. Try again.")
        else:
            return dt


# ---------- Core features ----------
def book_appointment():
    name = input("Your name: ").strip()
    phone = input("Phone number: ").strip()
    purpose = input("Purpose of visit: ").strip()
    if not name or not phone:
        print("Name and phone are required.")
        return
    start = ask_datetime("Date & time (YYYY-MM-DD HH:MM): ")
    if has_conflict(start):
        print("Sorry, that slot is already taken. Please pick another time.")
        return
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO appointments (name, phone, purpose, start) VALUES (?,?,?,?)",
            (name, phone, purpose, start.strftime(DT_FORMAT)),
        )
    print(f"Booked! Your appointment ID is {cur.lastrowid}.")


def view_appointments(upcoming_only=True):
    query = "SELECT * FROM appointments"
    params = ()
    if upcoming_only:
        query += " WHERE start >= ?"
        params = (datetime.now().strftime(DT_FORMAT),)
    query += " ORDER BY start"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    if not rows:
        print("No appointments found.")
        return
    print(f"\n{'ID':<4} {'When':<17} {'Name':<15} {'Phone':<13} Purpose")
    print("-" * 65)
    for r in rows:
        print(f"{r['id']:<4} {r['start']:<17} {r['name']:<15} {r['phone']:<13} {r['purpose']}")


def cancel_appointment():
    try:
        appt_id = int(input("Appointment ID to cancel: "))
    except ValueError:
        print("Please enter a number.")
        return
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,))
    print("Cancelled." if cur.rowcount else "No appointment with that ID.")


def reschedule_appointment():
    try:
        appt_id = int(input("Appointment ID to reschedule: "))
    except ValueError:
        print("Please enter a number.")
        return
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    if not row:
        print("No appointment with that ID.")
        return
    new_start = ask_datetime("New date & time (YYYY-MM-DD HH:MM): ")
    if has_conflict(new_start, ignore_id=appt_id):
        print("That slot is already taken.")
        return
    with get_conn() as conn:
        # reset 'reminded' so the new time gets its own reminder
        conn.execute(
            "UPDATE appointments SET start = ?, reminded = 0 WHERE id = ?",
            (new_start.strftime(DT_FORMAT), appt_id),
        )
    print("Rescheduled.")


# ---------- Reminder system ----------
def check_reminders():
    """Print a reminder for every appointment starting soon (once each)."""
    now = datetime.now()
    window_end = now + timedelta(minutes=REMINDER_BEFORE_MIN)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM appointments WHERE reminded = 0 AND start BETWEEN ? AND ?",
            (now.strftime(DT_FORMAT), window_end.strftime(DT_FORMAT)),
        ).fetchall()
        for r in rows:
            mins = int((datetime.strptime(r["start"], DT_FORMAT) - now).total_seconds() // 60)
            print(
                f"\n*** REMINDER: {r['name']} ({r['phone']}) has an appointment "
                f"at {r['start']} - in about {mins} min. Purpose: {r['purpose']} ***"
            )
            conn.execute("UPDATE appointments SET reminded = 1 WHERE id = ?", (r["id"],))


def reminder_worker():
    while True:
        check_reminders()
        time.sleep(CHECK_INTERVAL_SEC)


# ---------- Menu ----------
MENU = """
===== Appointment Booking System =====
1. Book appointment
2. View upcoming appointments
3. View all appointments
4. Reschedule appointment
5. Cancel appointment
6. Exit
"""


def main():
    init_db()
    threading.Thread(target=reminder_worker, daemon=True).start()
    actions = {
        "1": book_appointment,
        "2": lambda: view_appointments(True),
        "3": lambda: view_appointments(False),
        "4": reschedule_appointment,
        "5": cancel_appointment,
    }
    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "6":
            print("Goodbye!")
            break
        action = actions.get(choice)
        action() if action else print("Invalid choice.")


if __name__ == "__main__":
    main()
