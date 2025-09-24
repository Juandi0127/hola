from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'ENSDB123'  # Secrey key for session management

DATABASE = 'biblioteca.db'

# --- Database Setup ---

def get_db_connection():
    """Create a database connection with row factory for dict-like access."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def crear_tablas():
    """Create database tables if they don't exist."""
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS libro (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                autor TEXT NOT NULL,
                editorial TEXT NOT NULL,
                stock INTEGER NOT NULL,
                seccion TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS prestamo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                grado TEXT NOT NULL,
                curso TEXT NOT NULL,
                libro_id INTEGER NOT NULL,
                dias INTEGER NOT NULL,
                correo TEXT NOT NULL,
                fecha_prestamo TEXT NOT NULL,
                devuelto INTEGER DEFAULT 0,
                FOREIGN KEY(libro_id) REFERENCES libro(id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reseña (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                libro_id INTEGER NOT NULL,
                correo TEXT NOT NULL,
                calificacion INTEGER NOT NULL,
                comentario TEXT,
                fecha TEXT NOT NULL,
                FOREIGN KEY(libro_id) REFERENCES libro(id)
            )
        ''')
        conn.commit()

def aplicar_migraciones():
    """Apply database migrations for new columns."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Check if 'reseñado' column exists in 'prestamo'
        cursor.execute("PRAGMA table_info(prestamo)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'reseñado' not in columns:
            print("Applying migration: Adding 'reseñado' to 'prestamo' table.")
            conn.execute('ALTER TABLE prestamo ADD COLUMN reseñado INTEGER DEFAULT 0')
            conn.commit()

# --- User Routes ---

@app.route('/', methods=['GET', 'POST'])
def login():
    """User login page. Requires an institutional email."""
    if 'correo' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        correo = request.form['correo']
        if correo.endswith('@ensdbexcelencia.edu.co'):
            session['correo'] = correo
            return redirect(url_for('dashboard'))
        else:
            flash('Debes usar tu correo institucional para iniciar sesión.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """User dashboard, shows available books, recommendations, and sections."""
    if 'correo' not in session:
        return redirect(url_for('login'))
    
    search_query = request.args.get('search', '')
    conn = get_db_connection()

    # --- Recommended Books ---
    # Get most popular books (most loans)
    libros_populares = conn.execute('''
        SELECT l.id, l.titulo, l.autor, COUNT(p.libro_id) as total_prestamos
        FROM libro l
        JOIN prestamo p ON l.id = p.libro_id
        GROUP BY l.id, l.titulo, l.autor
        ORDER BY total_prestamos DESC
        LIMIT 5
    ''').fetchall()

    # Get top-rated books (best average rating)
    libros_mejor_calificados = conn.execute('''
        SELECT l.id, l.titulo, l.autor, AVG(r.calificacion) as avg_rating
        FROM libro l
        JOIN reseña r ON l.id = r.libro_id
        GROUP BY l.id, l.titulo, l.autor
        ORDER BY avg_rating DESC
        LIMIT 5
    ''').fetchall()
    
    # --- Book Sections ---
    if search_query:
        libros = conn.execute(
            "SELECT * FROM libro WHERE stock > 0 AND (titulo LIKE ? OR autor LIKE ? OR seccion LIKE ? OR editorial LIKE ?)",
            (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')
        ).fetchall()
        secciones = {'Resultados de la Búsqueda': libros} if libros else {}
    else:
        libros = conn.execute('SELECT * FROM libro WHERE stock > 0 ORDER BY seccion, titulo').fetchall()
        secciones = {}
        for libro in libros:
            secciones.setdefault(libro['seccion'], []).append(libro)
        
    conn.close()
    return render_template(
        'dashboard.html', 
        correo=session['correo'], 
        secciones=secciones, 
        search=search_query,
        libros_populares=libros_populares,
        libros_mejor_calificados=libros_mejor_calificados
    )

@app.route('/libro/<int:libro_id>')
def libro_detalle(libro_id):
    """Book detail page with reviews and average rating."""
    if 'correo' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    libro = conn.execute('SELECT * FROM libro WHERE id = ?', (libro_id,)).fetchone()

    if not libro:
        flash('El libro no fue encontrado.', 'error')
        return redirect(url_for('dashboard'))

    # Fetch reviews
    reseñas = conn.execute(
        'SELECT * FROM reseña WHERE libro_id = ? ORDER BY fecha DESC', (libro_id,)
    ).fetchall()

    # Calculate average rating
    avg_rating_result = conn.execute(
        'SELECT AVG(calificacion) as avg FROM reseña WHERE libro_id = ?', (libro_id,)
    ).fetchone()
    avg_rating = round(avg_rating_result['avg'], 1) if avg_rating_result['avg'] else 0
    
    conn.close()
    return render_template('libro_detalle.html', libro=libro, reseñas=reseñas, avg_rating=avg_rating)

@app.route('/prestar/<int:libro_id>', methods=['GET', 'POST'])
def prestar(libro_id):
    """Loan request page for a specific book."""
    if 'correo' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    libro = conn.execute('SELECT * FROM libro WHERE id = ? AND stock > 0', (libro_id,)).fetchone()

    if not libro:
        flash('El libro no está disponible o no existe.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        grado = request.form['grado']
        curso = request.form['curso']
        dias = int(request.form['dias'])
        
        if dias <= 0 or dias > 62:
            flash('El número de días para el préstamo debe ser entre 1 y 62.', 'error')
            return render_template('prestar.html', libro=libro)

        fecha_prestamo = datetime.now().strftime('%Y-%m-%d')
        
        conn.execute(
            'INSERT INTO prestamo (nombre, grado, curso, libro_id, dias, correo, fecha_prestamo) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (nombre, grado, curso, libro_id, dias, session['correo'], fecha_prestamo)
        )
        conn.execute('UPDATE libro SET stock = stock - 1 WHERE id = ?', (libro_id,))
        conn.commit()
        conn.close()
        
        flash(f'¡Préstamo del libro "{libro["titulo"]}" solicitado con éxito!', 'success')
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('prestar.html', libro=libro)

@app.route('/perfil')
def perfil():
    """User profile page showing active and past loans."""
    if 'correo' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user_email = session['correo']
    
    # Active loans
    prestamos_activos_raw = conn.execute(
        '''SELECT p.*, l.titulo AS libro, l.autor 
           FROM prestamo p JOIN libro l ON p.libro_id = l.id 
           WHERE p.correo = ? AND p.devuelto = 0''', (user_email,)
    ).fetchall()

    prestamos_activos = []
    hoy = datetime.now()
    for p in prestamos_activos_raw:
        p_dict = dict(p)
        fecha_inicio = datetime.strptime(p['fecha_prestamo'], '%Y-%m-%d')
        fecha_fin = fecha_inicio + timedelta(days=int(p['dias']))
        dias_restantes = (fecha_fin - hoy).days + 1
        p_dict['fecha_devolucion'] = fecha_fin.strftime('%Y-%m-%d')
        p_dict['dias_restantes'] = dias_restantes if dias_restantes >= 0 else -1
        prestamos_activos.append(p_dict)

    # Loan history
    historial = conn.execute(
        '''SELECT p.*, l.titulo AS libro 
           FROM prestamo p JOIN libro l ON p.libro_id = l.id 
           WHERE p.correo = ? ORDER BY p.fecha_prestamo DESC''', (user_email,)
    ).fetchall()
    
    conn.close()
    return render_template('perfil.html', correo=user_email, prestamos=prestamos_activos, historial=historial)

@app.route('/escribir_reseña/<int:prestamo_id>', methods=['GET', 'POST'])
def escribir_reseña(prestamo_id):
    """Review submission page for a loaned book."""
    if 'correo' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    prestamo = conn.execute('SELECT * FROM prestamo WHERE id = ?', (prestamo_id,)).fetchone()

    # Security checks
    if not prestamo or prestamo['correo'] != session['correo'] or not prestamo['devuelto']:
        flash('No puedes reseñar este libro.', 'error')
        return redirect(url_for('perfil'))
    if prestamo['reseñado']:
        flash('Ya has reseñado este préstamo.', 'error')
        return redirect(url_for('perfil'))

    libro = conn.execute('SELECT * FROM libro WHERE id = ?', (prestamo['libro_id'],)).fetchone()

    if request.method == 'POST':
        calificacion = request.form.get('calificacion')
        comentario = request.form.get('comentario')
        
        if not calificacion:
            flash('Debes seleccionar una calificación.', 'error')
            return render_template('escribir_reseña.html', libro=libro, prestamo=prestamo)

        fecha_reseña = datetime.now().strftime('%Y-%m-%d')
        conn.execute(
            'INSERT INTO reseña (libro_id, correo, calificacion, comentario, fecha) VALUES (?, ?, ?, ?, ?)',
            (libro['id'], session['correo'], calificacion, comentario, fecha_reseña)
        )
        conn.execute('UPDATE prestamo SET reseñado = 1 WHERE id = ?', (prestamo_id,))
        conn.commit()
        conn.close()

        flash('¡Gracias por tu reseña!', 'success')
        return redirect(url_for('perfil'))

    conn.close()
    return render_template('escribir_reseña.html', libro=libro, prestamo=prestamo)

@app.route('/logout')
def logout():
    """Log out the current user."""
    session.pop('correo', None)
    flash('Has cerrado sesión.', 'success')
    return redirect(url_for('login'))

# --- Admin Routes ---

ADMIN_PASSWORD = 'ENSDB123'

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if 'admin' in session:
        return redirect(url_for('admin_panel'))
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Contraseña incorrecta.', 'error')
    return render_template('admin_login.html')

@app.route('/admin_panel')
def admin_panel():
    """Admin main dashboard."""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin_panel.html')

@app.route('/admin_libros', methods=['GET', 'POST'])
def admin_libros():
    """Admin page to manage (add, view) books."""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    if request.method == 'POST' and request.form.get('_method') != 'DELETE':
        titulo = request.form['titulo']
        autor = request.form['autor']
        editorial = request.form['editorial']
        stock = request.form['stock']
        seccion = request.form['seccion']
        conn.execute(
            'INSERT INTO libro (titulo, autor, editorial, stock, seccion) VALUES (?, ?, ?, ?, ?)',
            (titulo, autor, editorial, stock, seccion)
        )
        conn.commit()
        flash(f'Libro "{titulo}" añadido correctamente.', 'success')

    libros = conn.execute('SELECT * FROM libro ORDER BY seccion, titulo').fetchall()
    conn.close()
    return render_template('admin_libros.html', libros=libros)

@app.route('/admin_editar_libro/<int:libro_id>', methods=['GET', 'POST'])
def admin_editar_libro(libro_id):
    """Admin page to edit an existing book."""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    if request.method == 'POST':
        titulo = request.form['titulo']
        autor = request.form['autor']
        editorial = request.form['editorial']
        stock = request.form['stock']
        seccion = request.form['seccion']
        
        conn.execute(
            'UPDATE libro SET titulo = ?, autor = ?, editorial = ?, stock = ?, seccion = ? WHERE id = ?',
            (titulo, autor, editorial, stock, seccion, libro_id)
        )
        conn.commit()
        conn.close()
        
        flash(f'Libro "{titulo}" actualizado correctamente.', 'success')
        return redirect(url_for('admin_libros'))

    libro = conn.execute('SELECT * FROM libro WHERE id = ?', (libro_id,)).fetchone()
    conn.close()
    
    if libro is None:
        flash('El libro no fue encontrado.', 'error')
        return redirect(url_for('admin_libros'))
        
    return render_template('admin_editar_libro.html', libro=libro)

@app.route('/admin_eliminar_libro/<int:libro_id>', methods=['POST'])
def admin_eliminar_libro(libro_id):
    """Admin route to delete a book, with safeguards."""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    
    # Check for related loans
    loan_count = conn.execute('SELECT COUNT(*) FROM prestamo WHERE libro_id = ?', (libro_id,)).fetchone()[0]
    
    if loan_count > 0:
        flash(f'No se puede eliminar este libro porque tiene un historial de {loan_count} préstamo(s). Para darlo de baja, edítalo y pon su stock a 0.', 'error')
    else:
        libro = conn.execute('SELECT titulo FROM libro WHERE id = ?', (libro_id,)).fetchone()
        conn.execute('DELETE FROM libro WHERE id = ?', (libro_id,))
        conn.commit()
        flash(f'Libro "{libro["titulo"]}" eliminado permanentemente ya que no tenía préstamos asociados.', 'success')
        
    conn.close()
    return redirect(url_for('admin_libros'))

@app.route('/admin_prestamos')
def admin_prestamos():
    """Admin page to view and manage active loans."""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    prestamos_raw = conn.execute(
        '''SELECT p.*, l.titulo as libro 
           FROM prestamo p JOIN libro l ON p.libro_id = l.id
           WHERE p.devuelto = 0 
           ORDER BY p.fecha_prestamo'''
    ).fetchall()
    
    prestamos_list = []
    hoy = datetime.now()
    for p in prestamos_raw:
        p_dict = dict(p)
        fecha_inicio = datetime.strptime(p['fecha_prestamo'], '%Y-%m-%d')
        fecha_fin = fecha_inicio + timedelta(days=int(p['dias']))
        dias_restantes = (fecha_fin - hoy).days + 1
        p_dict['dias_restantes'] = dias_restantes
        prestamos_list.append(p_dict)

    conn.close()
    return render_template('admin_prestamos.html', prestamos=prestamos_list)

@app.route('/devolver_prestamo/<int:prestamo_id>', methods=['POST'])
def devolver_prestamo(prestamo_id):
    """Marks a loan as returned and increments book stock."""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    prestamo = conn.execute('SELECT libro_id FROM prestamo WHERE id = ?', (prestamo_id,)).fetchone()
    
    if prestamo:
        conn.execute('UPDATE prestamo SET devuelto = 1 WHERE id = ?', (prestamo_id,))
        conn.execute('UPDATE libro SET stock = stock + 1 WHERE id = ?', (prestamo['libro_id'],))
        conn.commit()
        flash('Préstamo marcado como devuelto y libro repuesto al stock.', 'success')
    else:
        flash('No se encontró el préstamo.', 'error')
        
    conn.close()
    return redirect(url_for('admin_prestamos'))

@app.route('/admin_historial')
def admin_historial():
    """Admin page to view the complete history of all loans."""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    search_query = request.args.get('search', '')
    conn = get_db_connection()

    base_query = '''SELECT p.*, l.titulo as libro 
                     FROM prestamo p JOIN libro l ON p.libro_id = l.id'''
    params = []

    if search_query:
        base_query += " WHERE p.nombre LIKE ? OR p.correo LIKE ? OR l.titulo LIKE ? OR p.fecha_prestamo LIKE ?"
        params = [f'%{search_query}%'] * 4
    
    base_query += " ORDER BY p.fecha_prestamo DESC"

    prestamos = conn.execute(base_query, params).fetchall()
    conn.close()
    
    return render_template('admin_historial.html', prestamos=prestamos, search=search_query)

@app.route('/admin_estadisticas')
def admin_estadisticas():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    libros_populares = conn.execute('''
        SELECT l.titulo, COUNT(p.libro_id) as total
        FROM prestamo p JOIN libro l ON p.libro_id = l.id
        GROUP BY l.titulo
        ORDER BY total DESC
        LIMIT 5
    ''').fetchall()
    usuarios_activos = conn.execute('''
        SELECT nombre, correo, COUNT(*) as total
        FROM prestamo
        GROUP BY correo
        ORDER BY total DESC
        LIMIT 5
    ''').fetchall()
    total_prestamos = conn.execute('SELECT COUNT(*) FROM prestamo').fetchone()[0]
    total_libros = conn.execute('SELECT SUM(stock) FROM libro').fetchone()[0]
    conn.close()
    
    return render_template('admin_estadisticas.html',
                           libros_populares=libros_populares,
                           usuarios_activos=usuarios_activos,
                           total_prestamos=total_prestamos,
                           total_libros=total_libros or 0)

@app.route('/logout_admin')
def logout_admin():
    """Log out the current admin."""
    session.pop('admin', None)
    flash('Has cerrado la sesión de administrador.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    crear_tablas()
    aplicar_migraciones()
    app.run(debug=True)
