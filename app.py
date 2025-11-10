from flask import Flask, render_template, request, redirect, url_for, flash
import pymysql
from db import get_conn
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

# ============================ DASHBOARD ============================
@app.get("/")
def index():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM member")
        members = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM room")
        rooms = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM booking")
        bookings = cur.fetchone()["c"]

    return render_template("index.html", members=members, rooms=rooms, bookings=bookings)

# ============================= MEMBERS =============================
@app.get("/members")
def members_list():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT member_id, full_name, email, status
            FROM member
            ORDER BY member_id DESC
        """)
        rows = cur.fetchall()
    return render_template("members_list.html", rows=rows)

@app.get("/member/new")
def member_new_form():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT company_id, name FROM company ORDER BY name")
        companies = cur.fetchall()
    return render_template("member_form.html", companies=companies)

@app.post("/member/new")
def member_create():
    full_name  = request.form["full_name"].strip()
    email      = request.form["email"].strip().lower()
    phone      = request.form.get("phone", "").strip()
    company_id = request.form.get("company_id")

    if not full_name or not email:
        flash("Full name and email are required.", "warning")
        return redirect(url_for("member_new_form"))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM member WHERE email=%s", (email,))
        if cur.fetchone():
            flash("Email already exists. Please use a different one.", "warning")
            return redirect(url_for("member_new_form"))

        try:
            cur.execute(
                "INSERT INTO member(company_id, full_name, email, phone, status) "
                "VALUES (%s, %s, %s, %s, 'ACTIVE')",
                (company_id, full_name, email, phone),
            )
            conn.commit()
            flash("Member created.", "success")
        except pymysql.err.IntegrityError as e:
            conn.rollback()
            if e.args and e.args[0] == 1062:
                flash("Email already exists. Please use a different one.", "warning")
                return redirect(url_for("member_new_form"))
            raise
    return redirect(url_for("members_list"))

# ----- Members: Edit / Update / Delete -----
@app.get("/member/<int:member_id>/edit")
def member_edit(member_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM member WHERE member_id=%s", (member_id,))
        member = cur.fetchone()
        if not member:
            flash("Member not found.", "warning")
            return redirect(url_for("members_list"))
        cur.execute("SELECT company_id, name FROM company ORDER BY name")
        companies = cur.fetchall()
    return render_template("member_form.html", member=member, companies=companies)

@app.post("/member/<int:member_id>/edit")
def member_update(member_id):
    full_name  = request.form["full_name"].strip()
    email      = request.form["email"].strip().lower()
    phone      = request.form.get("phone","").strip()
    company_id = request.form.get("company_id")

    if not full_name or not email:
        flash("Full name and email are required.", "warning")
        return redirect(url_for("member_edit", member_id=member_id))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM member WHERE email=%s AND member_id<>%s", (email, member_id))
        if cur.fetchone():
            flash("Email already exists. Please use a different one.", "warning")
            return redirect(url_for("member_edit", member_id=member_id))

        try:
            cur.execute("""
                UPDATE member
                SET company_id=%s, full_name=%s, email=%s, phone=%s
                WHERE member_id=%s
            """, (company_id, full_name, email, phone, member_id))
            conn.commit()
            flash("Member updated.", "success")
        except pymysql.err.IntegrityError as e:
            conn.rollback()
            flash(f"Update failed: {e}", "danger")
    return redirect(url_for("members_list"))

@app.post("/member/<int:member_id>/delete")
def member_delete(member_id):
    with get_conn() as conn, conn.cursor() as cur:
        # Soft delete: only allow if no future bookings
        cur.execute("""
            SELECT 1 FROM booking 
            WHERE member_id=%s AND start_time > NOW() LIMIT 1
        """, (member_id,))
        if cur.fetchone():
            flash("Cannot deactivate: member has future bookings.", "warning")
            return redirect(url_for("members_list"))

        cur.execute("UPDATE member SET status='INACTIVE' WHERE member_id=%s", (member_id,))
        conn.commit()
        flash("Member deactivated.", "success")
    return redirect(url_for("members_list"))

# =============================== ROOMS ==============================
@app.get("/rooms")
def rooms_list():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT room_id, room_name, kind, capacity, hourly_rate
            FROM room
            ORDER BY room_id DESC
        """)
        rows = cur.fetchall()
    return render_template("rooms_list.html", rows=rows)

@app.get("/room/new")
def room_new_form():
    return render_template("room_form.html")

@app.post("/room/new")
def room_create():
    name     = request.form["room_name"].strip()
    kind     = request.form["kind"]
    capacity = request.form.get("capacity", "0").strip()
    rate     = request.form.get("hourly_rate", "0").strip()

    if not name:
        flash("Room name is required.", "warning")
        return redirect(url_for("room_new_form"))

    try:
        capacity = int(capacity)
        rate     = float(rate)
    except ValueError:
        flash("Capacity must be an integer and Rate/hr must be numeric.", "warning")
        return redirect(url_for("room_new_form"))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM room WHERE room_name=%s", (name,))
        if cur.fetchone():
            flash("Room name already exists.", "warning")
            return redirect(url_for("room_new_form"))

        try:
            cur.execute(
                "INSERT INTO room(room_name, kind, capacity, hourly_rate) "
                "VALUES (%s, %s, %s, %s)",
                (name, kind, capacity, rate),
            )
            conn.commit()
            flash("Room created.", "success")
        except pymysql.err.IntegrityError as e:
            conn.rollback()
            if e.args and e.args[0] == 1062:
                flash("Room name already exists.", "warning")
                return redirect(url_for("room_new_form"))
            raise
    return redirect(url_for("rooms_list"))

# ----- Rooms: Edit / Update / Delete -----
@app.get("/room/<int:room_id>/edit")
def room_edit(room_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM room WHERE room_id=%s", (room_id,))
        room = cur.fetchone()
        if not room:
            flash("Room not found.", "warning")
            return redirect(url_for("rooms_list"))
    return render_template("room_form.html", room=room)

@app.post("/room/<int:room_id>/edit")
def room_update(room_id):
    name     = request.form["room_name"].strip()
    kind     = request.form["kind"]
    capacity = request.form.get("capacity", "0").strip()
    rate     = request.form.get("hourly_rate", "0").strip()

    if not name:
        flash("Room name is required.", "warning")
        return redirect(url_for("room_edit", room_id=room_id))

    try:
        capacity = int(capacity)
        rate = float(rate)
    except ValueError:
        flash("Capacity must be an integer and Rate/hr must be numeric.", "warning")
        return redirect(url_for("room_edit", room_id=room_id))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM room WHERE room_name=%s AND room_id<>%s", (name, room_id))
        if cur.fetchone():
            flash("Room name already exists.", "warning")
            return redirect(url_for("room_edit", room_id=room_id))

        try:
            cur.execute("""
                UPDATE room
                SET room_name=%s, kind=%s, capacity=%s, hourly_rate=%s
                WHERE room_id=%s
            """, (name, kind, capacity, rate, room_id))
            conn.commit()
            flash("Room updated.", "success")
        except pymysql.err.IntegrityError as e:
            conn.rollback()
            flash(f"Update failed: {e}", "danger")
    return redirect(url_for("rooms_list"))

@app.post("/room/<int:room_id>/delete")
def room_delete(room_id):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute("DELETE FROM room WHERE room_id=%s", (room_id,))
            conn.commit()
            flash("Room deleted.", "success")
        except pymysql.err.IntegrityError:
            conn.rollback()
            flash("Cannot delete: room has related bookings.", "warning")
    return redirect(url_for("rooms_list"))

# =========================== BOOKINGS LIST ==========================
@app.get("/bookings")
def bookings_list():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT b.booking_id,
                   r.room_name   AS room,
                   m.full_name   AS member,
                   b.start_time, b.end_time, b.status
            FROM booking b
            JOIN room   r ON r.room_id   = b.room_id
            JOIN member m ON m.member_id = b.member_id
            ORDER BY b.booking_id DESC
        """)
        rows = cur.fetchall()
    return render_template("bookings_list.html", rows=rows)

# ================================
# BOOKINGS: NEW (form + create)
# ================================
@app.get("/booking/new")
def booking_new():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT member_id, full_name FROM member ORDER BY full_name")
        members = cur.fetchall()
        cur.execute("SELECT room_id, room_name FROM room ORDER BY room_name")
        rooms = cur.fetchall()
    return render_template("booking_form.html", members=members, rooms=rooms)

@app.post("/booking/new")
def booking_create():
    member_id = request.form["member_id"]
    room_id   = request.form["room_id"]
    start     = request.form["start_time"].strip()   # "YYYY-MM-DD HH:MM:SS"
    end       = request.form["end_time"].strip()

    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO booking(member_id, room_id, start_time, end_time, status)
                VALUES (%s,%s,%s,%s,'CONFIRMED')
            """, (member_id, room_id, start, end))
            conn.commit()
            flash("Booking created.", "success")
        except pymysql.err.OperationalError as e:
            conn.rollback()
            # 1644 = SIGNAL from trigger (e.g., overlap)
            if e.args and e.args[0] == 1644:
                msg = e.args[1] if len(e.args) > 1 and e.args[1] else \
                      "Room already has a booking in that time range."
                flash(msg, "warning")
            else:
                raise
        except pymysql.err.IntegrityError:
            conn.rollback()
            flash("Please select a valid member and room.", "warning")

    return redirect(url_for("bookings_list"))

# ================================
# BOOKINGS: DELETE (POST)
# ================================
@app.post("/booking/<int:booking_id>/delete")
def booking_delete(booking_id):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute("DELETE FROM booking WHERE booking_id=%s", (booking_id,))
            conn.commit()
            flash("Booking deleted.", "success")
        except pymysql.err.IntegrityError:
            conn.rollback()
            flash("Cannot delete this booking.", "warning")
    return redirect(url_for("bookings_list"))

# ========================= INVOICES + PAYMENTS ======================
@app.get("/invoices")
def invoices_view():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT m.full_name,
                   IFNULL(v.total, 0) AS total,
                   IFNULL(v.paid,  0) AS paid,
                   IFNULL(v.due,   0) AS due
            FROM member m
            LEFT JOIN v_member_balances v ON v.member_id = m.member_id
            ORDER BY m.full_name
        """)
        balances = cur.fetchall()

        cur.execute("""
            SELECT i.invoice_id,
                   i.member_id,
                   m.full_name,
                   i.invoice_date,
                   i.status,
                   fn_invoice_total(i.invoice_id) AS total_amount
            FROM invoice i
            JOIN member m ON m.member_id = i.member_id
            ORDER BY i.invoice_id DESC
            LIMIT 10
        """)
        latest = cur.fetchall()

    return render_template("invoices.html", balances=balances, latest=latest)

@app.post("/invoice/<int:invoice_id>/pay")
def invoice_pay(invoice_id: int):
    amount = request.form.get("amount", "").strip()
    method = request.form.get("method", "CASH")

    try:
        amt = float(amount)
        if amt <= 0:
            flash("Enter a positive amount.", "warning")
            return redirect(url_for("invoices_view"))
    except ValueError:
        flash("Invalid amount.", "warning")
        return redirect(url_for("invoices_view"))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO payment(invoice_id, amount, method) VALUES (%s, %s, %s)",
            (invoice_id, amt, method),
        )
        conn.commit()
    flash("Payment recorded.", "success")
    return redirect(url_for("invoices_view"))

# ========================== QUERIES SHOWCASE ========================
@app.get("/queries")
def queries_page():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT b.booking_id AS id,
                   r.room_name   AS room,
                   m.full_name   AS member,
                   b.start_time, b.end_time
            FROM booking b
            JOIN room   r ON r.room_id   = b.room_id
            JOIN member m ON m.member_id = b.member_id
            ORDER BY b.booking_id DESC
        """)
        join_rows = cur.fetchall()

        cur.execute("""
            SELECT room_id, COUNT(*) AS bookings
            FROM booking
            GROUP BY room_id
            ORDER BY room_id
        """)
        agg_rows = cur.fetchall()

    return render_template("queries.html", join_rows=join_rows, agg_rows=agg_rows)

# ============================== REPORTS =============================
@app.get("/reports")
def reports():
    with get_conn() as conn, conn.cursor() as cur:
        # KPI 1: Active members
        cur.execute("SELECT COUNT(*) AS active_members FROM member WHERE status='ACTIVE'")
        active_members = cur.fetchone()["active_members"]

        # KPI 2: Total revenue (sum of all payments)
        cur.execute("SELECT IFNULL(SUM(amount),0) AS total_revenue FROM payment")
        total_revenue = cur.fetchone()["total_revenue"]

        # Top pending dues (member-wise)
        cur.execute("""
            SELECT i.member_id,
                   SUM(fn_invoice_total(i.invoice_id)) - SUM(fn_invoice_paid_amount(i.invoice_id)) AS due
            FROM invoice i
            GROUP BY i.member_id
            HAVING due > 0
            ORDER BY due DESC
            LIMIT 10
        """)
        dues = cur.fetchall()

        # Revenue by day (last 14 entries)
        cur.execute("""
            SELECT DATE(p.paid_on) AS day, ROUND(SUM(p.amount),2) AS revenue
            FROM payment p
            GROUP BY DATE(p.paid_on)
            ORDER BY day DESC
            LIMIT 14
        """)
        rev_by_day = cur.fetchall()

    return render_template(
        "reports.html",
        active_members=active_members,
        total_revenue=total_revenue,
        dues=dues,
        rev_by_day=rev_by_day
    )

# ================================ MAIN ==============================
if __name__ == "__main__":
    app.run(debug=True)
