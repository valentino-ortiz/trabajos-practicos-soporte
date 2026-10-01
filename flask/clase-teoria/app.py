import os
import sqlite3
from flask import Flask, request, render_template, redirect

app = Flask(__name__)

def init_db():
    db_path = 'libros.db'
    db_exists = os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if not db_exists:
        # Si el archivo no existe, créalo con la tabla
        cursor.execute('''
            CREATE TABLE libro (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                libro TEXT NOT NULL,
                reseña TEXT
            )
        ''')
        conn.commit()
    else:
        # Si existe, verificar que la tabla existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='libro'")
        if not cursor.fetchone():
            # Si no existe, crearla
            cursor.execute('''
                CREATE TABLE libro (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    libro TEXT NOT NULL,
                    reseña TEXT
                )
            ''')
            conn.commit()
    conn.close()

# Inicializamos la base de datos al arrancar la app
init_db()

@app.route('/')
def root():
    db = sqlite3.connect('libros.db')
    cursor = db.cursor()
    cursor.execute('SELECT * FROM libro ORDER BY id DESC')
    libros = cursor.fetchall()
    db.close()
    return render_template('libros.html', libros=libros)

@app.route('/libros/<int:_id>')
def libro(_id):
    db = sqlite3.connect('libros.db')  
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM libro WHERE id=?', (_id,))
    libro = cursor.fetchone()
    
    db.close()
    if libro:
        return render_template('post.html', libro=libro)
    return redirect('/')

@app.route('/create')
def create():
    return render_template('create.html')

@app.route('/edit/<int:_id>')
def edit(_id):
    db = sqlite3.connect('libros.db')
    cursor = db.cursor()
    cursor.execute('SELECT * FROM libro WHERE id=?', (_id,))
    libro_data = cursor.fetchone()
    db.close()
    
    if libro_data:
        return render_template('edit.html', libro=libro_data[1], reseña=libro_data[2], _id=libro_data[0])
    return redirect('/')

@app.route('/insert', methods=['POST'])
def insert():
    db = sqlite3.connect('libros.db')  
    cursor = db.cursor()
    
    # Se obtienen datos del formulario vía POST (request.form)
    libro = request.form.get('libro')
    reseña = request.form.get('reseña')
    
    cursor.execute('INSERT INTO libro (libro, reseña) VALUES (?, ?)', (libro, reseña))
    db.commit()
    db.close()
    return redirect('/')

@app.route('/update/<int:_id>', methods=['POST'])
def update(_id):
    db = sqlite3.connect('libros.db')  
    cursor = db.cursor()
    
    libro = request.form.get('libro')
    reseña = request.form.get('reseña')
    
    cursor.execute('UPDATE libro SET libro=?, reseña=? WHERE id=?', (libro, reseña, _id))
    db.commit()
    db.close()
    return redirect('/')

@app.route('/delete/<int:_id>', methods=['POST'])
def delete(_id):
    db = sqlite3.connect('libros.db')  
    cursor = db.cursor()
    
    cursor.execute('DELETE FROM libro WHERE id=?', (_id,))
    db.commit()
    db.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, threaded=True)