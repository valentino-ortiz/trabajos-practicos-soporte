"""
Módulo de base de datos de ChefVoz.

Stub inicial para FASE 0. La implementación completa se realiza en FASE 4.
Contiene solo la inicialización de tablas necesaria para que Flask arranque.
"""

import os
import sqlite3
from typing import Optional

import config


class Database:
    """
    Gestiona la conexión y operaciones con la base de datos SQLite.

    Stub de FASE 0: solo implementa init_db() para crear las tablas
    y permitir el arranque de Flask. El resto de métodos se implementa en FASE 4.
    """

    def __init__(self, ruta_db: Optional[str] = None) -> None:
        """
        Inicializa la instancia de Database.

        Args:
            ruta_db: Ruta al archivo SQLite. Si es None, usa la ruta de config.
        """
        self.ruta_db = ruta_db or config.RUTA_DB
        # Asegurar que el directorio de la DB exista
        os.makedirs(os.path.dirname(self.ruta_db), exist_ok=True)

    def _conectar(self) -> sqlite3.Connection:
        """
        Crea y retorna una conexión a la base de datos con row_factory configurado.

        Returns:
            Conexión SQLite con sqlite3.Row como row_factory.
        """
        conexion = sqlite3.connect(self.ruta_db)
        conexion.row_factory = sqlite3.Row
        # Habilitar claves foráneas
        conexion.execute("PRAGMA foreign_keys = ON")
        return conexion

    def init_db(self) -> None:
        """
        Crea las tablas de la base de datos si no existen.

        Tablas creadas:
            - recetas       : datos principales de cada receta
            - ingredientes  : ingredientes asociados a cada receta
            - pasos         : pasos de preparación de cada receta
        """
        sql_crear_tablas = """
        CREATE TABLE IF NOT EXISTS recetas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo          TEXT    NOT NULL,
            texto_original  TEXT,
            fuente          TEXT    DEFAULT 'manual',
            url             TEXT,
            fecha_creacion  TEXT    DEFAULT (datetime('now', 'localtime')),
            favorita        INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ingredientes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            receta_id   INTEGER NOT NULL,
            nombre      TEXT    NOT NULL,
            cantidad    TEXT,
            unidad      TEXT,
            orden       INTEGER DEFAULT 0,
            FOREIGN KEY (receta_id) REFERENCES recetas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pasos (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            receta_id               INTEGER NOT NULL,
            numero                  INTEGER NOT NULL,
            descripcion             TEXT    NOT NULL,
            duracion_estimada_seg   INTEGER DEFAULT 0,
            FOREIGN KEY (receta_id) REFERENCES recetas(id) ON DELETE CASCADE
        );
        """
        try:
            with self._conectar() as conexion:
                conexion.executescript(sql_crear_tablas)
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al inicializar la base de datos: {error}") from error

    # ── CRUD de Recetas ────────────────────────────────────────────────────────

    def guardar_receta(self, datos: dict) -> int:
        """
        Guarda una nueva receta completa (cabecera, ingredientes y pasos).
        Usa transacciones para asegurar integridad.
        """
        sql_receta = '''
            INSERT INTO recetas (titulo, texto_original, fuente, url)
            VALUES (?, ?, ?, ?)
        '''
        sql_ingrediente = '''
            INSERT INTO ingredientes (receta_id, nombre, cantidad, unidad, orden)
            VALUES (?, ?, ?, ?, ?)
        '''
        sql_paso = '''
            INSERT INTO pasos (receta_id, numero, descripcion, duracion_estimada_seg)
            VALUES (?, ?, ?, ?)
        '''

        try:
            with self._conectar() as conn:
                # 1. Insertar la cabecera
                cursor = conn.execute(
                    sql_receta,
                    (
                        datos.get("titulo", "Receta sin título"),
                        datos.get("texto_original", ""),
                        datos.get("fuente", "manual"),
                        datos.get("url", "")
                    )
                )
                receta_id = cursor.lastrowid

                # 2. Insertar ingredientes
                ingredientes = datos.get("ingredientes", [])
                for i, ing in enumerate(ingredientes, 1):
                    conn.execute(
                        sql_ingrediente,
                        (
                            receta_id,
                            ing.get("nombre", ""),
                            ing.get("cantidad", ""),
                            ing.get("unidad", ""),
                            ing.get("orden", i)
                        )
                    )

                # 3. Insertar pasos
                pasos = datos.get("pasos", [])
                for i, paso in enumerate(pasos, 1):
                    conn.execute(
                        sql_paso,
                        (
                            receta_id,
                            paso.get("numero", i),
                            paso.get("descripcion", ""),
                            paso.get("duracion_estimada_seg", 0)
                        )
                    )
                    
                return receta_id
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al guardar la receta: {error}") from error

    def actualizar_receta(self, receta_id: int, datos: dict):
        """
        Actualiza una receta existente.
        Sobrescribe el título, elimina los ingredientes/pasos anteriores y guarda los nuevos.
        """
        sql_update_receta = '''
            UPDATE recetas 
            SET titulo = ?, fuente = ?, url = ?
            WHERE id = ?
        '''
        sql_delete_ingredientes = 'DELETE FROM ingredientes WHERE receta_id = ?'
        sql_delete_pasos = 'DELETE FROM pasos WHERE receta_id = ?'
        sql_ingrediente = '''
            INSERT INTO ingredientes (receta_id, nombre, cantidad, unidad, orden)
            VALUES (?, ?, ?, ?, ?)
        '''
        sql_paso = '''
            INSERT INTO pasos (receta_id, numero, descripcion, duracion_estimada_seg)
            VALUES (?, ?, ?, ?)
        '''
        try:
            with self._conectar() as conn:
                # 1. Actualizar receta
                conn.execute(
                    sql_update_receta,
                    (
                        datos.get("titulo", "Sin Título"),
                        datos.get("fuente", "manual"),
                        datos.get("url", ""),
                        receta_id
                    )
                )

                # 2. Eliminar viejos
                conn.execute(sql_delete_ingredientes, (receta_id,))
                conn.execute(sql_delete_pasos, (receta_id,))

                # 3. Insertar nuevos ingredientes
                ingredientes = datos.get("ingredientes", [])
                for i, ing in enumerate(ingredientes, 1):
                    conn.execute(
                        sql_ingrediente,
                        (
                            receta_id,
                            ing.get("nombre", ""),
                            ing.get("cantidad", ""),
                            ing.get("unidad", ""),
                            ing.get("orden", i)
                        )
                    )

                # 4. Insertar nuevos pasos
                pasos = datos.get("pasos", [])
                for i, paso in enumerate(pasos, 1):
                    conn.execute(
                        sql_paso,
                        (
                            receta_id,
                            paso.get("numero", i),
                            paso.get("descripcion", ""),
                            paso.get("duracion_estimada_seg", 0)
                        )
                    )
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al actualizar la receta: {error}") from error

    def obtener_recetas(self) -> list[dict]:
        """
        Devuelve la lista de todas las recetas (para la página de inicio),
        incluyendo conteos de pasos e ingredientes, ordenadas por favoritas 
        y fecha de creación.
        """
        sql = '''
            SELECT 
                r.id, r.titulo, r.fuente, r.url, r.fecha_creacion, r.favorita,
                (SELECT COUNT(*) FROM ingredientes WHERE receta_id = r.id) as total_ingredientes,
                (SELECT COUNT(*) FROM pasos WHERE receta_id = r.id) as total_pasos
            FROM recetas r
            ORDER BY r.favorita DESC, r.id DESC
        '''
        try:
            with self._conectar() as conn:
                cursor = conn.execute(sql)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al obtener recetas: {error}") from error

    def obtener_receta_completa(self, receta_id: int) -> Optional[dict]:
        """
        Obtiene los datos completos de una receta por su ID.
        Devuelve None si no existe.
        """
        sql_receta = "SELECT * FROM recetas WHERE id = ?"
        sql_ingredientes = "SELECT * FROM ingredientes WHERE receta_id = ? ORDER BY orden"
        sql_pasos = "SELECT * FROM pasos WHERE receta_id = ? ORDER BY numero"
        
        try:
            with self._conectar() as conn:
                cursor = conn.execute(sql_receta, (receta_id,))
                fila_receta = cursor.fetchone()
                
                if not fila_receta:
                    return None
                    
                receta = dict(fila_receta)
                
                # Cargar ingredientes
                cursor = conn.execute(sql_ingredientes, (receta_id,))
                receta["ingredientes"] = [dict(row) for row in cursor.fetchall()]
                
                # Cargar pasos
                cursor = conn.execute(sql_pasos, (receta_id,))
                receta["pasos"] = [dict(row) for row in cursor.fetchall()]
                
                return receta
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al obtener receta {receta_id}: {error}") from error

    def eliminar_receta(self, receta_id: int) -> bool:
        """
        Elimina una receta (ingredientes y pasos se borran por CASCADE).
        Retorna True si se borró algo, False si no existía.
        """
        sql = "DELETE FROM recetas WHERE id = ?"
        try:
            with self._conectar() as conn:
                cursor = conn.execute(sql, (receta_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al eliminar receta {receta_id}: {error}") from error

    def toggle_favorita(self, receta_id: int) -> Optional[bool]:
        """
        Invierte el estado de 'favorita' (0 a 1 o 1 a 0).
        Retorna el nuevo estado (True/False) o None si no existe.
        """
        sql_select = "SELECT favorita FROM recetas WHERE id = ?"
        sql_update = "UPDATE recetas SET favorita = ? WHERE id = ?"
        
        try:
            with self._conectar() as conn:
                cursor = conn.execute(sql_select, (receta_id,))
                fila = cursor.fetchone()
                
                if not fila:
                    return None
                    
                nuevo_estado = 0 if fila["favorita"] else 1
                conn.execute(sql_update, (nuevo_estado, receta_id))
                return bool(nuevo_estado)
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al actualizar favorita {receta_id}: {error}") from error
