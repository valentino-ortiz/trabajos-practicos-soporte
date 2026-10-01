from flask import Flask
app = Flask(__name__)

@app.route('/')
def inicio():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pagina de inicio</title>
    </head>
    <body>
        <h1>Pagina de inicio</h1>
        <a href="/usuario/ejemplo">Ver usuario ejemplo</a>
        <a href="/usuario/admin">Ver usuario admin</a>
    </body>
    </html>
    '''

@app.route('/usuario/<username>')
def mostrar_usuario(username):
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Perfil de {username}</title>
    </head>
    <body>
        <h1>Usuario: {username}</h1>
        <p>Esta es la pagina del usuario {username}</p>
        <a href="/">Volver al inicio</a>
    </body>
    </html>
    '''


if __name__ == '__main__':
    app.run()