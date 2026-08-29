#!/usr/bin/env python3
"""Genera el hash bcrypt de una contraseña, para pegarlo en USUARIOS_PERMITIDOS.

El comentario de app.py mandaba a este script desde hace tiempo, pero el
script no existía -- así que cambiar una contraseña obligaba a improvisar,
que es justo como terminan las contraseñas escritas en texto plano.

    python3 tools/hash_password.py

La contraseña se pide sin eco y NUNCA se pasa por argumento: lo que se
escribe en la línea de comandos queda en el historial del shell.
"""
import getpass
import sys

try:
    import bcrypt
except ImportError:
    sys.exit("Falta bcrypt. Instálalo con:  pip install bcrypt")


def main():
    clave = getpass.getpass("Contraseña nueva: ")
    if not clave.strip():
        sys.exit("Vacía. No se generó nada.")
    if clave != getpass.getpass("Repítela: "):
        sys.exit("No coinciden. No se generó nada.")
    if len(clave) < 8:
        print("Aviso: menos de 8 caracteres. Se genera igual, pero es corta.\n")

    # La app compara con  bcrypt.checkpw(clave.strip().encode(), hash)
    # así que aquí se aplica el mismo .strip(): si no, una contraseña con
    # un espacio al final generaría un hash que la app nunca validaría.
    hash_bcrypt = bcrypt.hashpw(clave.strip().encode(), bcrypt.gensalt(12)).decode()
    print("\nPega esto en el campo \"hash\" del usuario, en USUARIOS_PERMITIDOS:\n")
    print(f'    "hash": "{hash_bcrypt}",\n')


if __name__ == "__main__":
    main()
