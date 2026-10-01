'use strict';

/* ── Estado de la sesión de cocina ───────────────────────────────────────── */
const estado = {
    recetaId: null,
    pasoActual: 0,
    totalPasos: 1,
    audioActualUrl: null,
    cargando: false,
    reconocimiento: null,
    grabador: null,
    streamMic: null,
    usandoRespaldo: false,
    micActivo: false,
    audioPausandoMic: false,
    acento: (localStorage.getItem('chefvoz_acento') || 'es|com.ar').includes('|') ? 
             (localStorage.getItem('chefvoz_acento') || 'es|com.ar') : 
             `es|${localStorage.getItem('chefvoz_acento') || 'com.ar'}`
};

/* ── Referencias DOM ─────────────────────────────────────────────────────── */
const dom = {
    titulo:        () => document.getElementById('cocina-titulo-receta'),
    contador:      () => document.getElementById('cocina-contador-pasos'),
    textoPaso:     () => document.getElementById('cocina-texto-paso'),
    estadoAudio:   () => document.getElementById('cocina-estado-audio'),
    audio:         () => document.getElementById('cocina-audio'),
    progresoFill:  () => document.getElementById('cocina-progreso-fill'),
    btnAnterior:   () => document.getElementById('btn-anterior'),
    btnSiguiente:  () => document.getElementById('btn-siguiente'),
};

/* ── Inicialización ──────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('cocina-app');
    estado.recetaId = parseInt(app?.dataset?.recetaId, 10);

    if (!estado.recetaId || isNaN(estado.recetaId)) {
        mostrarError('ID de receta inválido.');
        return;
    }

    const selectAcento = document.getElementById('select-acento');
    if (selectAcento) selectAcento.value = estado.acento;

    cargarPasoActual();
    registrarAtajosTeclado();
    registrarGestosTactiles();
    inicializarReconocimientoVoz();
});

/* ── Cambio de Acento ────────────────────────────────────────────────────── */
function cambiarAcento(nuevoAcento) {
    estado.acento = nuevoAcento;
    localStorage.setItem('chefvoz_acento', nuevoAcento);
    cargarPasoActual(); // Recargar el paso actual con el nuevo acento
}

/* ── Cargar Estado desde el Servidor (FASE 6) ────────────────────────────── */
async function cargarPasoActual() {
    if (estado.cargando) return;
    estado.cargando = true;

    dom.estadoAudio().innerHTML = `<div class="spinner"></div> Preparando paso...`;
    dom.btnSiguiente().disabled = true;
    dom.btnAnterior().disabled = true;

    try {
        const url = `/api/recetas/${estado.recetaId}/sesion/paso/${estado.pasoActual}?acento=${estado.acento}`;
        const respuesta = await fetch(url);
        
        const datos = await respuesta.json();
        if (!respuesta.ok) throw new Error(datos.error || 'Error al cargar el paso');
        
        estado.totalPasos = datos.total_pasos;
        estado.audioActualUrl = datos.url_audio;
        
        // Titulo de la receta
        if (datos.titulo) {
            dom.titulo().textContent = datos.titulo;
        }

        // Animación del texto y renderizado (Lista para ingredientes, texto para pasos)
        if (datos.es_primero && datos.ingredientes && datos.ingredientes.length > 0) {
            let htmlList = `<div class="text-left inline-block w-full max-w-2xl"><ul class="list-disc list-inside space-y-3 mb-6 text-primary-container">`;
            datos.ingredientes.forEach(ing => {
                const cant = ing.cantidad ? `${ing.cantidad} ${ing.unidad || ''}`.trim() : '';
                const nombreStr = cant ? `<strong>${cant}</strong> de ${ing.nombre}` : ing.nombre;
                htmlList += `<li>${nombreStr}</li>`;
            });
            htmlList += `</ul><p class="text-on-surface-variant text-label-md mt-6">Cuando tengas todo listo, avanzá al primer paso.</p></div>`;
            dom.textoPaso().innerHTML = htmlList;
        } else {
            dom.textoPaso().textContent = datos.texto;
        }
        
        dom.textoPaso().style.animation = 'none';
        requestAnimationFrame(() => {
            dom.textoPaso().style.animation = 'fadeIn 0.3s ease';
        });

        // Contadores y barra
        const pasoDisplay = estado.pasoActual === 0 ? "Intro" : estado.pasoActual;
        const totalDisplay = estado.totalPasos - 1;
        dom.contador().textContent = estado.pasoActual === 0 ? "Ingredientes" : `Paso ${pasoDisplay} de ${totalDisplay}`;
        
        dom.progresoFill().style.width = `${datos.progreso_porcentaje}%`;

        // Botones UI
        dom.btnAnterior().disabled = datos.es_primero;
        
        const iconoSig = dom.btnSiguiente().querySelector('.material-symbols-outlined');
        const spanTextSig = dom.btnSiguiente().querySelector('.font-label-md');
        
        if (datos.es_ultimo) {
            if (iconoSig) iconoSig.textContent = 'check_circle';
            if (spanTextSig) spanTextSig.textContent = 'Finalizar';
        } else {
            if (iconoSig) iconoSig.textContent = 'arrow_forward';
            if (spanTextSig) spanTextSig.textContent = 'Siguiente';
        }
        dom.btnSiguiente().disabled = false;

        // Audio Management
        if (datos.error_audio) {
            dom.estadoAudio().innerHTML = `⚠️ Sin audio (${datos.error_audio})`;
        } else {
            dom.estadoAudio().innerHTML = '';
            reproducirAudio(datos.url_audio);
        }

    } catch (error) {
        mostrarError(`Error de conexión: ${error.message}`);
        dom.btnAnterior().disabled = false;
        dom.btnSiguiente().disabled = false;
    } finally {
        estado.cargando = false;
    }
}

/* ── Acciones de botones ─────────────────────────────────────────────────── */
function accionSiguiente() {
    if (estado.pasoActual >= estado.totalPasos - 1) {
        mostrarFinalizacion();
        return;
    }
    estado.pasoActual++;
    cargarPasoActual();
}

function accionAnterior() {
    if (estado.pasoActual <= 0) return;
    estado.pasoActual--;
    cargarPasoActual();
}

function accionRepetir() {
    if (estado.audioActualUrl) {
        reproducirAudio(estado.audioActualUrl);
    }
}

function accionSalir() {
    window.location.href = '/';
}

function togglePausaAudio() {
    const audio = dom.audio();
    const icono = document.getElementById('icono-pausa');
    const texto = document.getElementById('texto-pausa');
    
    if (!audio.src) return;

    if (audio.paused) {
        audio.play();
        if (icono) icono.textContent = 'pause';
        if (texto) texto.textContent = 'Pausar';
    } else {
        audio.pause();
        if (icono) icono.textContent = 'play_arrow';
        if (texto) texto.textContent = 'Reproducir';
    }
}

/* ── Audio ───────────────────────────────────────────────────────────────── */
function reproducirAudio(url) {
    if (!url) return;
    const audio = dom.audio();
    audio.src = url;
    audio.load();
    audio.play().then(() => {
        const icono = document.getElementById('icono-pausa');
        const texto = document.getElementById('texto-pausa');
        if (icono) icono.textContent = 'pause';
        if (texto) texto.textContent = 'Pausar';
    }).catch(err => {
        console.warn('Autoplay bloqueado:', err);
        dom.estadoAudio().innerHTML = `Toca 'Repetir' para reproducir el audio.`;
        const icono = document.getElementById('icono-pausa');
        const texto = document.getElementById('texto-pausa');
        if (icono) icono.textContent = 'play_arrow';
        if (texto) texto.textContent = 'Reproducir';
    });
}

/* ── Finalización ────────────────────────────────────────────────────────── */
function mostrarFinalizacion() {
    dom.textoPaso().textContent = '🎉 ¡Receta completada! Buen provecho.';
    dom.estadoAudio().innerHTML = '';
    dom.btnSiguiente().disabled = true;
    dom.contador().textContent = '¡Finalizado!';
    dom.progresoFill().style.width = '100%';
}

/* ── Atajos de teclado ───────────────────────────────────────────────────── */
function registrarAtajosTeclado() {
    document.addEventListener('keydown', (evento) => {
        if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

        switch (evento.code) {
            case 'Space':
            case 'Enter':
                evento.preventDefault();
                if (!dom.btnSiguiente().disabled) {
                    accionSiguiente();
                } else if (estado.pasoActual >= estado.totalPasos - 1) {
                    // Si ya finalizó, salir
                    accionSalir();
                }
                break;
            case 'KeyP':
                togglePausaAudio();
                break;
            case 'KeyR':
                accionRepetir();
                break;
            case 'KeyA':
            case 'ArrowLeft':
                if (!dom.btnAnterior().disabled) accionAnterior();
                break;
            case 'Escape':
                accionSalir();
                break;
        }
    });
}

/* ── Gestos táctiles (swipe) ─────────────────────────────────────────────── */
function registrarGestosTactiles() {
    let inicioY = 0;
    let inicioX = 0;
    const UMBRAL_SWIPE = 60; // px mínimos para activar swipe

    document.addEventListener('touchstart', (e) => {
        inicioY = e.touches[0].clientY;
        inicioX = e.touches[0].clientX;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        const deltaY = inicioY - e.changedTouches[0].clientY;
        const deltaX = Math.abs(inicioX - e.changedTouches[0].clientX);

        if (Math.abs(deltaY) > UMBRAL_SWIPE && Math.abs(deltaY) > deltaX) {
            if (deltaY > 0) {
                if (!dom.btnSiguiente().disabled) accionSiguiente();
            } else {
                if (!dom.btnAnterior().disabled) accionAnterior();
            }
        }
    }, { passive: true });
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function mostrarError(mensaje) {
    const el = dom.textoPaso();
    if (el) el.textContent = `❌ ${mensaje}`;
    console.error(mensaje);
}

/* ── Control por Voz ─────────────────────────────────────────────────────── */
function inicializarReconocimientoVoz() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn('Se usará el respaldo MediaRecorder para reconocimiento de voz');
        return;
    }

    estado.reconocimiento = new SpeechRecognition();
    estado.reconocimiento.lang = 'es-AR';
    estado.reconocimiento.continuous = true;
    estado.reconocimiento.interimResults = false;

    estado.reconocimiento.onstart = () => {
        if (!estado.audioPausandoMic) {
            document.getElementById('btn-mic').classList.add('voice-active');
            document.getElementById('mic-icon').textContent = 'mic';
            document.getElementById('mic-status').textContent = 'Escuchando...';
        }
    };

    estado.reconocimiento.onerror = (evento) => {
        console.warn('🗣️ Error en micrófono:', evento.error);
        if (evento.error === 'not-allowed' || evento.error === 'service-not-allowed') {
            iniciarRespaldoMic();
        } else if (evento.error === 'audio-capture') {
            estado.micActivo = false;
            estado.audioPausandoMic = false;
            document.getElementById('btn-mic').classList.remove('voice-active');
            document.getElementById('mic-icon').textContent = 'mic_off';
            document.getElementById('mic-status').textContent = 'Sin micrófono';
            mostrarToast('No se encontró un micrófono disponible.', 'error');
        } else if (evento.error !== 'no-speech') {
            mostrarToast('Error de micrófono: ' + evento.error, 'error');
        }
    };

    estado.reconocimiento.onend = () => {
        if (estado.micActivo && !estado.audioPausandoMic) {
            // Reiniciar con un pequeño retardo evita bloqueos en Chrome tras error de 'no-speech'
            setTimeout(() => {
                if (estado.micActivo && !estado.audioPausandoMic) {
                    iniciarReconocimiento();
                }
            }, 250);
        } else if (!estado.micActivo) {
            document.getElementById('btn-mic').classList.remove('voice-active');
            document.getElementById('mic-icon').textContent = 'mic_off';
            document.getElementById('mic-status').textContent = 'Inactivo';
        }
    };

    estado.reconocimiento.onresult = (evento) => {
        if (estado.audioPausandoMic) return;

        const ultimoResultado = evento.results[evento.results.length - 1];
        if (ultimoResultado.isFinal) {
            const comando = ultimoResultado[0].transcript.trim().toLowerCase();
            console.log('🗣️ Comando detectado:', comando);
            mostrarToast('Escuché: "' + comando + '"', 'info');
            procesarComandoVoz(comando);
        }
    };

    // Sincronización con el Audio (Prevenir eco)
    const audio = dom.audio();
    audio.addEventListener('play', () => {
        if (estado.micActivo && estado.reconocimiento) {
            estado.audioPausandoMic = true;
            try { estado.reconocimiento.stop(); } catch(e) {}
            document.getElementById('mic-status').textContent = 'Robot hablando...';
        }
    });

    audio.addEventListener('ended', reanudarMic);
    audio.addEventListener('pause', reanudarMic);
}

function reanudarMic() {
    if (estado.micActivo && estado.audioPausandoMic) {
        estado.audioPausandoMic = false;
        // Si ya tenemos el stream activo, retomamos la grabación directamente
        // sin pedir permisos de nuevo (evita NotAllowedError por doble getUserMedia)
        if (estado.usandoRespaldo && estado.streamMic) {
            grabarFragmentoMic();
        } else {
            iniciarRespaldoMic();
        }
    }
}

function iniciarReconocimiento() {
    if (estado.usandoRespaldo) return;
    try {
        estado.reconocimiento.start();
    } catch (error) {
        console.warn('No se pudo iniciar el reconocimiento:', error);
        document.getElementById('mic-status').textContent = 'Error al iniciar';
        mostrarToast(`No se pudo iniciar el micrófono: ${error.name || error.message}`, 'error');
    }
}

async function iniciarRespaldoMic() {
    if (estado.usandoRespaldo || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        estado.micActivo = false;
        mostrarToast('Este navegador no permite reconocimiento ni grabación de audio.', 'error');
        return;
    }

    try {
        estado.streamMic = await navigator.mediaDevices.getUserMedia({ audio: true });
        estado.usandoRespaldo = true;
        grabarFragmentoMic();
    } catch (error) {
        estado.micActivo = false;
        document.getElementById('btn-mic').classList.remove('voice-active');
        document.getElementById('mic-icon').textContent = 'mic_off';

        let mensajeCorto = 'Sin micrófono';
        let mensajeToast;

        if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
            mensajeCorto = 'Sin dispositivo';
            mensajeToast = '⚠️ No se detectó ningún micrófono. Conectá uno y volvé a intentarlo.';
        } else if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            mensajeCorto = 'Permiso denegado';
            mensajeToast = '🔒 Permiso de micrófono denegado. Hacé clic en el candado de la barra de direcciones y permitilo.';
        } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
            mensajeCorto = 'Dispositivo ocupado';
            mensajeToast = '🎙️ El micrófono está siendo usado por otra aplicación. Cerrala e intentá de nuevo.';
        } else if (error.name === 'OverconstrainedError') {
            mensajeCorto = 'Config. inválida';
            mensajeToast = '⚙️ La configuración de audio solicitada no es compatible con este micrófono.';
        } else {
            mensajeCorto = 'Error (' + error.name + ')';
            mensajeToast = `No se pudo abrir el micrófono: ${error.name} — ${error.message}`;
        }

        document.getElementById('mic-status').textContent = mensajeCorto;
        mostrarToast(mensajeToast, 'error');
        console.error('🎙️ Error al acceder al micrófono:', error.name, error.message);
    }
}

function grabarFragmentoMic() {
    if (!estado.micActivo || !estado.usandoRespaldo) return;
    const partes = [];
    estado.grabador = new MediaRecorder(estado.streamMic);
    estado.grabador.ondataavailable = evento => {
        if (evento.data.size > 0) partes.push(evento.data);
    };
    estado.grabador.onstop = async () => {
        const audio = new Blob(partes, { type: estado.grabador.mimeType || 'audio/webm' });
        const formulario = new FormData();
        formulario.append('audio', audio, 'voz.webm');
        try {
            const respuesta = await fetch('/api/voz/reconocer', { method: 'POST', body: formulario });
            const datos = await respuesta.json();
            if (datos.texto) {
                console.log('Comando detectado (respaldo):', datos.texto);
                mostrarToast(`Escuché: "${datos.texto}"`, 'info');
                procesarComandoVoz(datos.texto.toLowerCase());
            }
        } catch (error) {
            console.warn('Error en respaldo de voz:', error);
        } finally {
            grabarFragmentoMic();
        }
    };
    estado.grabador.start();
    document.getElementById('mic-icon').textContent = 'mic';
    document.getElementById('mic-status').textContent = 'Escuchando...';
    setTimeout(() => {
        if (estado.grabador?.state === 'recording') estado.grabador.stop();
    }, 4000);
}

function detenerRespaldoMic() {
    estado.usandoRespaldo = false;
    if (estado.grabador?.state === 'recording') estado.grabador.stop();
    estado.streamMic?.getTracks().forEach(track => track.stop());
    estado.grabador = null;
    estado.streamMic = null;
}

function procesarComandoVoz(comando) {
    if (comando.includes('siguiente') || comando.includes('próximo') || comando.includes('avanzar') || comando.includes('continuar') || comando.includes('listo') || comando.includes('paso')) {
        if (!dom.btnSiguiente().disabled) accionSiguiente();
    } else if (comando.includes('anterior') || comando.includes('atrás') || comando.includes('volver')) {
        if (!dom.btnAnterior().disabled) accionAnterior();
    } else if (comando.includes('repetir') || comando.includes('de nuevo') || comando.includes('otra vez')) {
        accionRepetir();
    } else if (comando.includes('salir') || comando.includes('terminar')) {
        accionSalir();
    } else if (comando.includes('pausa') || comando.includes('pausar') || comando.includes('detener')) {
        const audio = dom.audio();
        if (!audio.paused) togglePausaAudio();
    } else if (comando.includes('reproducir') || comando.includes('reanudar') || comando.includes('play')) {
        const audio = dom.audio();
        if (audio.paused) togglePausaAudio();
    }
}

function toggleMic() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        alert("Tu navegador no permite grabar audio.");
        return;
    }

    estado.micActivo = !estado.micActivo;
    
    if (estado.micActivo) {
        if (!window.isSecureContext) {
            estado.micActivo = false;
            mostrarToast('El micrófono requiere localhost o HTTPS.', 'error');
            return;
        }

        // Verificar si el audio ya está reproduciéndose al momento de activarlo
        const audio = dom.audio();
        if (audio && !audio.paused && !audio.ended) {
            estado.audioPausandoMic = true;
            document.getElementById('btn-mic').classList.add('voice-active');
            document.getElementById('mic-status').textContent = 'Robot hablando...';
        } else {
            estado.audioPausandoMic = false;
            // En Linux, Brave/Firefox suelen rechazar SpeechRecognition aunque
            // el permiso del micrófono esté concedido. Usar el respaldo directo.
            iniciarRespaldoMic();
        }
    } else {
        mostrarToast('Micrófono desactivado', 'info');
        estado.audioPausandoMic = false;
        detenerRespaldoMic();
        try { estado.reconocimiento.stop(); } catch (e) {}
        document.getElementById('mic-icon').textContent = 'mic_off';
    }
}

// Implementación de Toast para notificaciones visuales
function mostrarToast(mensaje, tipo = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = mensaje;
    toast.className = `toast visible ${tipo}`;
    
    // Si hay un timeout previo, cancelarlo
    if (window.toastTimeout) clearTimeout(window.toastTimeout);
    
    window.toastTimeout = setTimeout(() => {
        toast.classList.remove('visible');
    }, 4000);
}
