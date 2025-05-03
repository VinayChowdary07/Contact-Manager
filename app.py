from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db_config import get_db_connection
import mysql.connector
import re
import csv
from io import StringIO
from flask import Response

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret

# ---------- ROUTES ---------- #

@app.route('/export_contacts')
def export_contacts():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, phone, email, location FROM contacts WHERE user_id = %s", (user_id,))
    contacts = cursor.fetchall()
    cursor.close()
    conn.close()

    # Write CSV to memory
    si = StringIO()
    writer = csv.DictWriter(si, fieldnames=["name", "phone", "email", "location"])
    writer.writeheader()
    writer.writerows(contacts)
    output = si.getvalue()

    # Create response
    return Response(output, mimetype='text/csv', headers={
        "Content-Disposition": "attachment; filename=contacts.csv"
    })


def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email)

# Home/Login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not is_valid_email(username):
            flash('Invalid email format. Please enter a valid email address.', 'danger')
            return render_template('login.html')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect('/dashboard')
        else:
            flash('Invalid username or password')

    return render_template('login.html')

# Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        if not is_valid_email(username):
            flash('Invalid email format. Please enter a valid email address.', 'danger')
            return render_template('signup.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
            flash("Account created! Please log in.")
            return redirect('/')
        except mysql.connector.errors.IntegrityError:
            flash("Username already exists.")
        finally:
            cursor.close()
            conn.close()

    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    allowed_sort_columns = ['name', 'location']
    sort_by = request.args.get('sort', 'name')
    search = request.args.get('search', '').strip()

    if sort_by not in allowed_sort_columns:
        sort_by = 'name'

    # Pagination settings
    page = request.args.get('page', 1, type=int)  # Default to page 1
    per_page = 5  # Number of contacts per page

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Calculate total contacts for pagination (with search)
    if search:
        query = f"""
            SELECT COUNT(*) FROM contacts 
            WHERE user_id = %s AND (
                name LIKE %s OR email LIKE %s OR location LIKE %s
            )
        """
        like_pattern = f"%{search}%"
        cursor.execute(query, (user_id, like_pattern, like_pattern, like_pattern))
    else:
        query = "SELECT COUNT(*) FROM contacts WHERE user_id = %s"
        cursor.execute(query, (user_id,))
    
    total_contacts = cursor.fetchone()['COUNT(*)']
    total_pages = (total_contacts + per_page - 1) // per_page  # Calculate total pages

    # Fetch contacts for the current page (with search)
    offset = (page - 1) * per_page
    if search:
        query = f"""
            SELECT * FROM contacts 
            WHERE user_id = %s AND (
                name LIKE %s OR email LIKE %s OR location LIKE %s
            )
            ORDER BY {sort_by} LIMIT %s OFFSET %s
        """
        cursor.execute(query, (user_id, like_pattern, like_pattern, like_pattern, per_page, offset))
    else:
        query = f"SELECT * FROM contacts WHERE user_id = %s ORDER BY {sort_by} LIMIT %s OFFSET %s"
        cursor.execute(query, (user_id, per_page, offset))

    contacts = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('dashboard.html', contacts=contacts, total_pages=total_pages, current_page=page, search=search)



from flask import flash, redirect, url_for

@app.route('/add', methods=['POST'])
def add_contact():
    if 'user_id' not in session:
        return redirect('/')

    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    location = request.form['location']

    if not is_valid_email(email):
            flash('Invalid email format. Please enter a valid email address.', 'danger')
            return redirect(url_for('dashboard')) 

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check for duplicate phone or email
    cursor.execute("SELECT * FROM contacts WHERE user_id = %s AND (phone = %s OR email = %s)", 
                   (session['user_id'], phone, email))
    existing_contact = cursor.fetchone()
    
    if existing_contact:
        flash("A contact with this phone or email already exists.", "error")
        return redirect(url_for('dashboard'))  # Redirect back to the dashboard

    # If no duplicate, proceed with adding the contact
    cursor.execute(
        "INSERT INTO contacts (user_id, name, phone, email, location) VALUES (%s, %s, %s, %s, %s)",
        (session['user_id'], name, phone, email, location)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))



# Delete Contact
@app.route('/delete/<int:contact_id>')
def delete_contact(contact_id):
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = %s AND user_id = %s", (contact_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/dashboard')

# Edit Contact (Form)
import re
from flask import flash, redirect, url_for

@app.route('/edit/<int:contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        location = request.form['location']

        # ✅ Email Format Validation
        def is_valid_email(email):
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return re.match(pattern, email)

        if not is_valid_email(email):
            flash('Invalid email format. Please enter a valid email address.', 'danger')
            return redirect(url_for('edit_contact', contact_id=contact_id))

        # ✅ Duplicate Check (excluding the current contact)
        cursor.execute("""
            SELECT * FROM contacts 
            WHERE user_id = %s AND (phone = %s OR email = %s) AND id != %s
        """, (session['user_id'], phone, email, contact_id))
        duplicate = cursor.fetchone()

        if duplicate:
            flash('Another contact with the same phone or email already exists.', 'danger')
            return redirect(url_for('edit_contact', contact_id=contact_id))

        # ✅ Perform Update
        cursor.execute(
            "UPDATE contacts SET name=%s, phone=%s, email=%s, location=%s WHERE id=%s AND user_id=%s",
            (name, phone, email, location, contact_id, session['user_id'])
        )
        conn.commit()
        flash('Contact updated successfully.', 'success')
        return redirect('/dashboard')

    # GET: Fetch Contact for Editing
    cursor.execute("SELECT * FROM contacts WHERE id = %s AND user_id = %s", (contact_id, session['user_id']))
    contact = cursor.fetchone()
    cursor.close()
    conn.close()

    if not contact:
        flash('Contact not found.', 'danger')
        return redirect('/dashboard')

    return render_template('edit_contact.html', contact=contact)


# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------- MAIN ---------- #

if __name__ == '__main__':
    app.run(debug=True)
