from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'ENSDB123'  # clave

DATABASE = 'biblioteca.db'
UPLOAD_FOLDER = os.path.join('static', 'perfiles')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def crear_tablas():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS libro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            autor TEXT NOT NULL,
            stock INTEGER NOT NULL,
            seccion TEXT NOT NULL
        )
    ''')
    c.execute('''
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
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuario (
            correo TEXT PRIMARY KEY,
            nombre TEXT
        )
    ''')
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Página de inicio de sesión
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        # dominio del correo de la normal
        if correo.endswith('@ensdbexcelencia.edu.co'):
            session['correo'] = correo
            return redirect(url_for('dashboard'))
        else:
            flash('Debes usar tu correo institucional')
    return render_template('login.html')

# Página principal después de iniciar sesión
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'correo' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    search = request.form.get('search', '')
    if search:
        libros = conn.execute(
            "SELECT * FROM libro WHERE stock > 0 AND (titulo LIKE ? OR autor LIKE ? OR seccion LIKE ?)",
            (f'%{search}%', f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        libros = conn.execute('SELECT * FROM libro WHERE stock > 0').fetchall()
    conn.close()
    # Agrupar por sección
    secciones = {}
    for libro in libros:
        seccion = libro['seccion']
        secciones.setdefault(seccion, []).append(libro)
    return render_template('dashboard.html', correo=session['correo'], secciones=secciones, search=search)

# Cerrar sesión
@app.route('/logout')
def logout():
    session.pop('correo', None)
    return redirect(url_for('login'))

# Ruta para solicitar préstamo
@app.route('/prestar/<int:libro_id>', methods=['GET', 'POST'])
def prestar(libro_id):
    if 'correo' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    libro = conn.execute('SELECT * FROM libro WHERE id = ?', (libro_id,)).fetchone()
    conn.close()
    if request.method == 'POST':
        nombre = request.form['nombre']
        grado = request.form['grado']
        curso = request.form['curso']
        dias = int(request.form['dias'])
        correo = session['correo']
        fecha_prestamo = datetime.now().strftime('%Y-%m-%d')
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO prestamo (nombre, grado, curso, libro, dias, correo, fecha_prestamo) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (nombre, grado, curso, libro['titulo'], dias, correo, fecha_prestamo)
        )
        # Disminuir stock
        conn.execute('UPDATE libro SET stock = stock - 1 WHERE id = ?', (libro_id,))
        conn.commit()
        conn.close()
        flash('¡Préstamo solicitado con éxito!')
        return redirect(url_for('dashboard'))
    return render_template('prestar.html', libro=libro)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        titulo = request.form['titulo']
        autor = request.form['autor']
        stock = request.form['stock']
        seccion = request.form['seccion']
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO libro (titulo, autor, stock, seccion) VALUES (?, ?, ?, ?)',
            (titulo, autor, stock, seccion)
        )
        conn.commit()
        conn.close()
        flash('Libro añadido correctamente')
    conn = get_db_connection()
    libros = conn.execute('SELECT * FROM libro').fetchall()
    prestamos = conn.execute('SELECT * FROM prestamo').fetchall()
    conn.close()
    return render_template('admin.html', libros=libros, prestamos=prestamos)

@app.route('/prestamo/<int:prestamo_id>')
def detalle_prestamo(prestamo_id):
    conn = get_db_connection()
    prestamo = conn.execute('SELECT * FROM prestamo WHERE id = ?', (prestamo_id,)).fetchone()
    conn.close()
    if prestamo:
        fecha_prestamo = prestamo['fecha_prestamo']
        dias = prestamo['dias']
        if fecha_prestamo:
            fecha_inicio = datetime.strptime(fecha_prestamo, '%Y-%m-%d')
            fecha_fin = fecha_inicio + timedelta(days=int(dias))
            hoy = datetime.now()
            dias_restantes = (fecha_fin - hoy).days
            if dias_restantes < 0:
                dias_restantes = 0
        else:
            dias_restantes = dias
        return render_template('detalle_prestamo.html', prestamo=prestamo, dias_restantes=dias_restantes)
    else:
        flash('Préstamo no encontrado')
        return redirect(url_for('admin'))

ADMIN_PASSWORD = 'ENSDB123'  # contraseña administrador

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Contraseña incorrecta')
    return render_template('admin_login.html')

@app.route('/admin_panel')
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin_panel.html')

@app.route('/admin_libros', methods=['GET', 'POST'])
def admin_libros():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    # Aquí va el código de tu vista actual de admin para libros
    if request.method == 'POST':
        titulo = request.form['titulo']
        autor = request.form['autor']
        stock = request.form['stock']
        seccion = request.form['seccion']
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO libro (titulo, autor, stock, seccion) VALUES (?, ?, ?, ?)',
            (titulo, autor, stock, seccion)
        )
        conn.commit()
        conn.close()
        flash('Libro añadido correctamente')
    conn = get_db_connection()
    libros = conn.execute('SELECT * FROM libro').fetchall()
    conn.close()
    return render_template('admin_libros.html', libros=libros)

@app.route('/admin_prestamos', methods=['GET', 'POST'])
def admin_prestamos():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    prestamos = conn.execute('SELECT * FROM prestamo WHERE devuelto = 0').fetchall()
    conn.close()
    prestamos_list = []
    for prestamo in prestamos:
        fecha_prestamo = prestamo['fecha_prestamo']
        dias = prestamo['dias']
        if fecha_prestamo:
            fecha_inicio = datetime.strptime(fecha_prestamo, '%Y-%m-%d')
            fecha_fin = fecha_inicio + timedelta(days=int(dias))
            hoy = datetime.now()
            dias_restantes = (fecha_fin - hoy).days
            if dias_restantes < 0:
                dias_restantes = 0
        else:
            dias_restantes = dias
        prestamo_dict = dict(prestamo)
        prestamo_dict['dias_restantes'] = dias_restantes
        prestamos_list.append(prestamo_dict)
    return render_template('admin_prestamos.html', prestamos=prestamos_list)

@app.route('/admin_estadisticas')
def admin_estadisticas():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    # Libros más prestados
    libros_populares = conn.execute('''
        SELECT libro, COUNT(*) as total
        FROM prestamo
        GROUP BY libro
        ORDER BY total DESC
        LIMIT 5
    ''').fetchall()
    # Usuarios más activos
    usuarios_activos = conn.execute('''
        SELECT nombre, correo, COUNT(*) as total
        FROM prestamo
        GROUP BY correo
        ORDER BY total DESC
        LIMIT 5
    ''').fetchall()
    # Total de préstamos
    total_prestamos = conn.execute('SELECT COUNT(*) FROM prestamo').fetchone()[0]
    # Total de libros en stock
    total_libros = conn.execute('SELECT SUM(stock) FROM libro').fetchone()[0]
    conn.close()
    return render_template('admin_estadisticas.html',
                           libros_populares=libros_populares,
                           usuarios_activos=usuarios_activos,
                           total_prestamos=total_prestamos,
                           total_libros=total_libros)

@app.route('/logout_admin')
def logout_admin():
    session.pop('admin', None)
    return redirect(url_for('login'))

@app.route('/perfil')
def perfil():
    if 'correo' not in session:
        return redirect(url_for('login'))
    foto = 'escudo.jpg'
    conn = get_db_connection()
    prestamos = conn.execute(
        "SELECT * FROM prestamo WHERE correo = ? AND devuelto = 0", (session['correo'],)
    ).fetchall()
    historial = conn.execute(
        "SELECT * FROM prestamo WHERE correo = ? ORDER BY fecha_prestamo DESC", (session['correo'],)
    ).fetchall()
    conn.close()
    prestamos_activos = []
    hoy = datetime.now()
    for prestamo in prestamos:
        fecha_prestamo = prestamo['fecha_prestamo']
        dias = prestamo['dias']
        if fecha_prestamo:
            fecha_inicio = datetime.strptime(fecha_prestamo, '%Y-%m-%d')
            fecha_fin = fecha_inicio + timedelta(days=int(dias))
            dias_restantes = (fecha_fin - hoy).days
            if dias_restantes < 0:
                dias_restantes = 0
            prestamo_dict = dict(prestamo)
            prestamo_dict['dias_restantes'] = dias_restantes
            prestamo_dict['fecha_devolucion'] = fecha_fin.strftime('%Y-%m-%d')
            prestamos_activos.append(prestamo_dict)
    historial_list = [dict(p) for p in historial]
    return render_template('perfil.html', correo=session['correo'], prestamos=prestamos_activos, historial=historial_list, foto=foto)

@app.route('/devolver_prestamo/<int:prestamo_id>', methods=['POST'])
def devolver_prestamo(prestamo_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    # Marcar como devuelto
    conn.execute('UPDATE prestamo SET devuelto = 1 WHERE id = ?', (prestamo_id,))
    # Reponer el libro al stock
    prestamo = conn.execute('SELECT libro FROM prestamo WHERE id = ?', (prestamo_id,)).fetchone()
    if prestamo:
        conn.execute('UPDATE libro SET stock = stock + 1 WHERE titulo = ?', (prestamo['libro'],))
    conn.commit()
    conn.close()
    flash('Préstamo marcado como devuelto y libro repuesto al stock.')
    return redirect(url_for('admin_prestamos'))

@app.route('/admin_historial', methods=['GET', 'POST'])
def admin_historial():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    search = request.form.get('search', '')
    conn = get_db_connection()
    if search:
        prestamos = conn.execute(
            '''SELECT * FROM prestamo
               WHERE nombre LIKE ? OR correo LIKE ? OR libro LIKE ? OR fecha_prestamo LIKE ?''',
            (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        prestamos = conn.execute('SELECT * FROM prestamo ORDER BY fecha_prestamo DESC').fetchall()
    conn.close()
    return render_template('admin_historial.html', prestamos=prestamos, search=search)

if __name__ == '__main__':
    crear_tablas()
    app.run(debug=True)