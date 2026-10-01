import kivy
from kivy.config import Config

# La calculadora se controla por teclado; evita eventos espurios del touchpad.
Config.remove_option('input', 'mouse')
Config.remove_option('input', '%(name)s')

from kivy.app import App
from kivy.core.window import Window

class CalculadoraApp(App):

    _ultimo_fue_resultado = False

    def build(self):
        Window.bind(on_key_down=self.manejar_tecla)
        return self.root

    def on_stop(self):
        Window.unbind(on_key_down=self.manejar_tecla)

    def manejar_tecla(self, window, keycode, scancode, codepoint, modifiers):
        tecla = codepoint or {
            13: 'enter',
            27: 'escape',
            8: 'backspace',
            127: 'delete',
        }.get(keycode, '')
        if tecla in '0123456789':
            self.presionar_numero(tecla)
        elif tecla in '+-*/':
            self.presionar_operacion(tecla)
        elif tecla in ('enter', 'numpadenter'):
            self.presionar_igual()
        elif tecla in ('backspace', 'delete'):
            self.root.ids.entrada.text = self.root.ids.entrada.text[:-1]
        elif tecla in ('escape', 'c'):
            self.presionar_clear()
        else:
            return False
        return True

    def presionar_numero(self, texto):
        entrada = self.root.ids.entrada
        if self._ultimo_fue_resultado:
            entrada.text = texto
            self._ultimo_fue_resultado = False
        else:
            entrada.text += texto

    def presionar_operacion(self, op):
        entrada = self.root.ids.entrada
        self._ultimo_fue_resultado = False
        entrada.text += op

    def presionar_igual(self):
        entrada = self.root.ids.entrada
        try:
            resultado = eval(entrada.text)
            if isinstance(resultado, float) and resultado.is_integer():
                entrada.text = str(int(resultado))
            else:
                entrada.text = str(resultado)
        except Exception:
            entrada.text = "Error"
        self._ultimo_fue_resultado = True

    def presionar_clear(self):
        self.root.ids.entrada.text = ''
        self._ultimo_fue_resultado = False


if __name__ == '__main__':
    CalculadoraApp().run()