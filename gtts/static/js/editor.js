/**
 * editor.js — ChefVoz
 *
 * Stub de FASE 0: estructura de funciones y carga inicial.
 * La implementación completa se realiza en FASE 6.
 */

'use strict';

/* ── Estado local ────────────────────────────────────────────────────────── */
let tabActiva = 'texto';       // 'texto' | 'url'
let previewActual = null;      // Datos del último preview generado
let editandoId = null;         // ID de la receta que se está editando (si aplica)

/* ── Inicialización ──────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    // Si estamos en el Dashboard
    if (document.getElementById('lista-recetas')) {
        cargarListaRecetas();
    }
    
    // Si estamos en el Formulario (Nueva Receta)
    if (document.getElementById('manual-titulo')) {
        const urlParams = new URLSearchParams(window.location.search);
        const editId = urlParams.get('edit');
        if (editId) {
            cargarRecetaParaEditar(editId);
        }
    }
});

/* ── Cambio de tab de formulario ─────────────────────────────────────────── */
function cambiarTab(tab) {
    tabActiva = tab;

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('activo', 'bg-surface-container-high', 'text-on-surface', 'shadow-sm');
        btn.classList.add('text-on-surface-variant');
    });
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('oculto'));

    const activeBtn = document.getElementById(`tab-${tab}`);
    if(activeBtn) {
        activeBtn.classList.add('activo', 'bg-surface-container-high', 'text-on-surface', 'shadow-sm');
        activeBtn.classList.remove('text-on-surface-variant');
    }
    
    const activePanel = document.getElementById(`panel-${tab}`);
    if(activePanel) {
        activePanel.classList.remove('oculto');
    }
}

/* ── Preview de receta ───────────────────────────────────────────────────── */
async function previsualizarReceta() {
    const cuerpo = obtenerCuerpoFormulario();
    if (!cuerpo) return;

    const btnPreview = document.getElementById('btn-preview');
    btnPreview.disabled = true;
    btnPreview.innerHTML = '<span class="material-symbols-outlined text-[20px] animate-spin">sync</span> Procesando...';

    try {
        const respuesta = await fetch('/api/recetas/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo),
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            mostrarToast(`Error: ${datos.error || 'Error al procesar'}`, 'error');
            return;
        }

        previewActual = datos;
        mostrarPreview(datos);
        document.getElementById('btn-guardar').disabled = false;
        mostrarToast('✅ Receta analizada correctamente', 'exito');

    } catch (error) {
        mostrarToast('❌ Error de conexión', 'error');
        console.error('Error en preview:', error);
    } finally {
        btnPreview.disabled = false;
        btnPreview.innerHTML = '<span class="material-symbols-outlined text-[20px]">preview</span> Previsualizar';
    }
}

/* ── Guardar receta ──────────────────────────────────────────────────────── */
async function guardarReceta() {
    const btnGuardar = document.getElementById('btn-guardar');
    btnGuardar.disabled = true;
    btnGuardar.innerHTML = '<span class="material-symbols-outlined text-[20px] animate-spin">sync</span> Guardando...';

    const titulo = document.getElementById('edit-titulo')?.value || previewActual?.titulo || 'Receta';
    const ingTexto = document.getElementById('edit-ingredientes')?.value || '';
    const pasosTexto = document.getElementById('edit-pasos')?.value || '';

    const textoEditado = `${titulo}\n\nIngredientes:\n${ingTexto}\n\nPreparación:\n${pasosTexto}`;

    try {
        const resParse = await fetch('/api/recetas/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto: textoEditado }),
        });
        const recetaFinal = await resParse.json();

        if (!resParse.ok) throw new Error(recetaFinal.error || 'Error al re-parsear');

        if (previewActual && previewActual.url) {
            recetaFinal.url = previewActual.url;
            recetaFinal.fuente = previewActual.fuente;
        }

        const url_endpoint = editandoId ? `/api/recetas/${editandoId}` : '/api/recetas';
        const method = editandoId ? 'PUT' : 'POST';

        const respuesta = await fetch(url_endpoint, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(recetaFinal),
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            mostrarToast(`Error: ${datos.error || 'Error al guardar'}`, 'error');
            return;
        }

        mostrarToast(editandoId ? '🎉 Receta actualizada exitosamente' : '🎉 Receta guardada exitosamente', 'exito');
        editandoId = null; 
        
        setTimeout(() => {
            window.location.href = "/";
        }, 1500);

    } catch (error) {
        mostrarToast('❌ Error de conexión o guardado', 'error');
        console.error('Error al guardar:', error);
    } finally {
        btnGuardar.disabled = false;
        btnGuardar.innerHTML = '<span class="material-symbols-outlined text-[20px]">save</span> Guardar Receta';
    }
}

/* ── Cargar lista de recetas ─────────────────────────────────────────────── */
async function cargarListaRecetas() {
    const contenedor = document.getElementById('lista-recetas');
    const estadoCarga = document.getElementById('estado-carga-recetas');
    if (!contenedor || !estadoCarga) return;

    estadoCarga.classList.remove('oculto');
    contenedor.innerHTML = '';

    try {
        const respuesta = await fetch('/api/recetas');
        const datos = await respuesta.json();

        estadoCarga.classList.add('oculto');

        if (!respuesta.ok || datos.error) {
            contenedor.innerHTML = `<p class="text-center w-full col-span-full py-8 text-error">⚠️ No se pudo cargar las recetas</p>`;
            return;
        }

        if (datos.length === 0) {
            contenedor.innerHTML = `
                <div class="col-span-full flex flex-col items-center justify-center py-16 text-on-surface-variant">
                    <span class="material-symbols-outlined text-6xl mb-4 text-surface-variant" style="font-variation-settings: 'FILL' 1;">restaurant</span>
                    <p class="font-headline-md text-[18px]">Todavía no tienes recetas guardadas</p>
                    <p class="font-body-md mt-2">¡Agrega tu primera receta desde el menú!</p>
                </div>`;
            return;
        }

        datos.forEach(receta => {
            contenedor.appendChild(crearTarjetaReceta(receta));
        });

    } catch (error) {
        estadoCarga.classList.add('oculto');
        contenedor.innerHTML = `<p class="text-center w-full col-span-full py-8 text-error">❌ Error de conexión</p>`;
        console.error('Error al cargar recetas:', error);
    }
}

/* ── Crear tarjeta de receta ─────────────────────────────────────────────── */
function crearTarjetaReceta(receta) {
    const card = document.createElement('div');
    card.className = "bg-surface-container-high rounded-xl overflow-hidden border border-outline-variant shadow-sm hover:shadow-md transition-shadow group relative";
    card.setAttribute('role', 'listitem');
    card.dataset.id = receta.id;

    // Calculamos algunos datos
    const totalPasos = receta.total_pasos || 0;
    const totalIngredientes = receta.total_ingredientes || 0;
    // Estimado de tiempo (solo visual por ahora)
    const tiempoEst = totalPasos * 5; 

    let badgeFavorito = '';
    if (receta.favorita) {
        badgeFavorito = `
        <div class="absolute top-2 right-2 bg-primary text-on-primary rounded-full p-1 shadow-sm cursor-pointer z-10" onclick="toggleFavorita(${receta.id}, this)">
            <span class="material-symbols-outlined text-[16px]" style="font-variation-settings: 'FILL' 1;">star</span>
        </div>`;
    } else {
        badgeFavorito = `
        <div class="absolute top-2 right-2 bg-surface/50 text-on-surface-variant hover:bg-primary hover:text-on-primary rounded-full p-1 shadow-sm cursor-pointer transition-colors z-10" onclick="toggleFavorita(${receta.id}, this)">
            <span class="material-symbols-outlined text-[16px]">star</span>
        </div>`;
    }

    card.innerHTML = `
        <div class="h-40 bg-surface-variant relative overflow-hidden flex items-center justify-center">
            ${badgeFavorito}
            <span class="material-symbols-outlined text-6xl text-outline group-hover:scale-110 transition-transform duration-300">restaurant</span>
        </div>
        <div class="p-4 flex flex-col gap-2">
            <h3 class="font-headline-md text-[18px] text-primary truncate" title="${escapeHtml(receta.titulo)}">${escapeHtml(receta.titulo)}</h3>
            <div class="flex items-center justify-between text-on-surface-variant">
                <div class="flex items-center gap-1 font-label-sm text-label-sm">
                    <span class="material-symbols-outlined text-[16px]">timer</span>
                    ~${tiempoEst} min
                </div>
                <div class="flex items-center gap-1 font-label-sm text-label-sm">
                    <span class="material-symbols-outlined text-[16px]">kitchen</span>
                    ${totalIngredientes} Ingredientes
                </div>
            </div>
            <div class="mt-4 flex gap-2">
                <a href="/cocina/${receta.id}" class="flex-1 bg-primary text-on-primary font-label-md text-label-md py-2 rounded-md hover:brightness-110 transition-colors shadow-sm active:scale-95 text-center flex items-center justify-center gap-1" id="btn-cocinar-${receta.id}">
                    <span class="material-symbols-outlined text-[18px]">skillet</span> Cocinar
                </a>
                <button class="px-3 py-2 border border-outline text-on-surface hover:bg-surface-variant rounded-md transition-colors active:scale-95 flex items-center justify-center" onclick="editarReceta(${receta.id})" id="btn-editar-${receta.id}" aria-label="Editar receta">
                    <span class="material-symbols-outlined text-[20px]">edit</span>
                </button>
                <button class="px-3 py-2 border border-outline text-error hover:bg-error/20 rounded-md transition-colors active:scale-95 flex items-center justify-center" onclick="eliminarReceta(${receta.id})" id="btn-eliminar-${receta.id}" aria-label="Eliminar receta">
                    <span class="material-symbols-outlined text-[20px]">delete</span>
                </button>
            </div>
        </div>
    `;

    return card;
}

/* ── Toggle favorita ─────────────────────────────────────────────────────── */
async function toggleFavorita(id, boton) {
    try {
        const respuesta = await fetch(`/api/recetas/${id}/favorita`, { method: 'POST' });
        const datos = await respuesta.json();

        if (respuesta.ok) {
            const esFavorita = datos.favorita;
            boton.classList.toggle('activo', esFavorita);
            const card = boton.closest('.receta-card');
            card.classList.toggle('favorita', esFavorita);
            boton.setAttribute('aria-label',
                esFavorita ? 'Quitar de favoritos' : 'Marcar como favorita');
            mostrarToast(esFavorita ? '⭐ Agregada a favoritos' : '☆ Quitada de favoritos', 'exito');
            
            // Reordenar la lista instantáneamente (el backend ya ordena por favorita)
            await cargarListaRecetas();
        }
    } catch (error) {
        console.error('Error al cambiar favorita:', error);
    }
}

/* ── Editar receta ───────────────────────────────────────────────────────── */
function editarReceta(id) {
    // Redirigir a la página de nueva receta con el parámetro de edición
    window.location.href = `/nueva?edit=${id}`;
}

async function cargarRecetaParaEditar(id) {
    try {
        const res = await fetch(`/api/recetas/${id}`);
        const receta = await res.json();
        if (!res.ok) throw new Error();

        cambiarTab('texto');
        document.getElementById('manual-titulo').value = receta.titulo || '';
        document.getElementById('manual-ingredientes').value = (receta.ingredientes || []).map(ing => {
            const cantidad = ing.cantidad ? `${ing.cantidad} ${ing.unidad || ''}`.trim() : '';
            return cantidad ? `${cantidad} de ${ing.nombre}` : ing.nombre;
        }).join('\n');
        document.getElementById('manual-pasos').value = (receta.pasos || []).map(p => p.descripcion).join('\n\n');

        editandoId = id;
        
        mostrarToast('✏️ Modo edición activado. Modifica los campos y presiona Previsualizar.', 'info');
    } catch {
        mostrarToast('❌ Error al cargar la receta para editar', 'error');
    }
}

/* ── Eliminar receta ─────────────────────────────────────────────────────── */
async function eliminarReceta(id) {
    if (!confirm('¿Eliminar esta receta?')) return;

    try {
        const respuesta = await fetch(`/api/recetas/${id}`, { method: 'DELETE' });

        if (respuesta.ok) {
            mostrarToast('🗑️ Receta eliminada', 'exito');
            await cargarListaRecetas();
        } else {
            mostrarToast('❌ Error al eliminar', 'error');
        }
    } catch (error) {
        mostrarToast('❌ Error de conexión', 'error');
        console.error('Error al eliminar:', error);
    }
}

/* ── Mostrar preview ─────────────────────────────────────────────────────── */
function mostrarPreview(datos) {
    const seccion = document.getElementById('seccion-preview');
    const contenido = document.getElementById('preview-contenido');

    const ingredientesTexto = (datos.ingredientes || []).map(ing => {
        const cantidad = ing.cantidad ? `${ing.cantidad} ${ing.unidad || ''}`.trim() : '';
        return cantidad ? `${cantidad} de ${ing.nombre}` : ing.nombre;
    }).join('\n');

    const pasosTexto = (datos.pasos || []).map(paso => paso.descripcion).join('\n\n');

    const inputClasses = "w-full bg-background border border-surface-variant rounded-md px-4 py-3 text-on-surface font-body-md focus:border-primary-container focus:ring-1 focus:ring-primary-container focus:outline-none mb-4";
    const labelClasses = "block font-label-md text-label-md text-on-surface-variant mb-1 mt-2 flex items-center gap-2";

    contenido.innerHTML = `
        <div class="bg-primary-container/20 text-on-surface p-3 rounded-lg border border-primary-container/30 font-label-md text-label-md mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">edit_note</span>
            <span><strong>Puedes editar los textos a continuación</strong> antes de guardar si hubo algún error al detectarlos.</span>
        </div>
        
        <label class="${labelClasses}"><span class="material-symbols-outlined text-[18px]">title</span> Título</label>
        <input type="text" id="edit-titulo" class="${inputClasses} font-bold text-lg text-primary" value="${escapeHtml(datos.titulo)}">

        <label class="${labelClasses}"><span class="material-symbols-outlined text-[18px] text-secondary">local_dining</span> Ingredientes (uno por línea)</label>
        <textarea id="edit-ingredientes" class="${inputClasses} resize-y" rows="6">${escapeHtml(ingredientesTexto)}</textarea>

        <label class="${labelClasses}"><span class="material-symbols-outlined text-[18px] text-primary-container">restaurant_menu</span> Pasos de preparación (separa cada paso con un salto de línea)</label>
        <textarea id="edit-pasos" class="${inputClasses} resize-y" rows="8">${escapeHtml(pasosTexto)}</textarea>
    `;

    seccion.classList.remove('oculto');
    seccion.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function ocultarPreview() {
    document.getElementById('seccion-preview').classList.add('oculto');
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function obtenerCuerpoFormulario() {
    if (tabActiva === 'texto') {
        const titulo = document.getElementById('manual-titulo').value.trim();
        const ing = document.getElementById('manual-ingredientes').value.trim();
        const pasos = document.getElementById('manual-pasos').value.trim();
        
        if (!titulo || !ing || !pasos) {
            mostrarToast('⚠️ Completa título, ingredientes y pasos', 'error');
            return null;
        }
        
        // Ensamblar texto para que el parser lo estructure (cantidades, unidades, etc)
        const texto = `${titulo}\n\nIngredientes:\n${ing}\n\nPreparación:\n${pasos}`;
        return { texto };
    } else {
        const url = document.getElementById('url-receta').value.trim();
        if (!url) {
            mostrarToast('⚠️ Ingresa una URL', 'error');
            return null;
        }
        return { url };
    }
}

function limpiarFormulario() {
    document.getElementById('manual-titulo').value = '';
    document.getElementById('manual-ingredientes').value = '';
    document.getElementById('manual-pasos').value = '';
    document.getElementById('url-receta').value = '';
    document.getElementById('btn-guardar').disabled = true;
    editandoId = null;
}

function escapeHtml(texto) {
    if (!texto) return '';
    return texto
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatearFecha(fechaStr) {
    if (!fechaStr) return '';
    try {
        const fecha = new Date(fechaStr);
        return fecha.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' });
    } catch { return fechaStr; }
}

let _toastTimer = null;
function mostrarToast(mensaje, tipo = '') {
    const toast = document.getElementById('toast');
    toast.textContent = mensaje;
    toast.className = `toast visible ${tipo}`;
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => toast.classList.remove('visible'), 3000);
}
