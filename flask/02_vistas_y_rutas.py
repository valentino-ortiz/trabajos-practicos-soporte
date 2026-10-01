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
        <a href="/acerca">Acerca de la APP</a>
    </body>
    </html>
    '''

@app.route('/acerca')
def acerca():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Acerca de la APP</title>
    </head>
    <body>
        <h1>Acerca de la APP</h1>
        <p>Informacion sobre la app...</p>
        <a href="/">Volver al inicio</a>
    </body>
    </html>
    '''


if __name__ == '__main__':
    app.run()