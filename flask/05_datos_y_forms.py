from flask import Flask, request, redirect, url_for, render_template

app = Flask(__name__, template_folder='.')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        return redirect(url_for('mostrar_usuario', username=usuario))
    return render_template('ej04_login.html')

@app.route('/usuario/<username>')
def mostrar_usuario(username):
    return render_template('ej04_usuario.html', username=username)

if __name__ == '__main__':
    app.run()