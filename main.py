"""Extrator CNPq Lattes: abre a interface gráfica.

Uso: python main.py            (interface)
     python main.py --cli ...  (linha de comando; ver python -m lattes_extrator --help)
"""
import multiprocessing
import sys

if __name__ == "__main__":
    # Necessário no executável (PyInstaller) por causa do processamento em paralelo
    multiprocessing.freeze_support()
    from lattes_extrator.cli import main

    args = sys.argv[1:]
    if args and args[0] == "--cli":
        args = args[1:]
    sys.exit(main(args or None))
