"""MPI por ramas: los tableros se resuelven EN ORDEN y, dentro de cada uno,
las ramas se reparten entre todos los procesos (rank 0 incluido)."""

import argparse
import sys
import time
from pathlib import Path

from mpi4py import MPI

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from baseline_secuencial import leer_seeds        # noqa: E402
from ramas_comun import resolver_en_grupo         # noqa: E402


def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    parser = argparse.ArgumentParser(description="Sudoku MPI: reparto de ramas por tablero.")
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt")
    sel = parser.add_mutually_exclusive_group()
    sel.add_argument("--id", dest="id", help="resolver solo este ID")
    sel.add_argument("--all", action="store_true", help="resolver todos los IDs")
    args = parser.parse_args()

    # Todos leen el archivo (es pequeno); solo el rank 0 usa el tablero para crear ramas.
    seeds = leer_seeds(args.archivo)
    if args.id:
        if args.id not in seeds:
            parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
        tareas = [(args.id, seeds[args.id])]
    else:
        tareas = list(seeds.items())

    todos = list(range(size))                # un solo grupo con todos los procesos
    comm.Barrier()
    inicio_total = time.perf_counter()
    resueltos = 0

    for nombre, original in tareas:          # tableros en orden, uno tras otro
        inicio = time.perf_counter()
        resuelto = resolver_en_grupo(comm, todos, original if rank == 0 else None)
        segundos = time.perf_counter() - inicio
        if rank == 0:
            resueltos += 1 if resuelto else 0
            print(f"\nID: {nombre}")
            print("Resuelto" if resuelto else "Sin solución")
            etiqueta = "Tiempo" if args.id else "Tiempo parcial"
            print(f"{etiqueta}: {segundos:.6f} segundos", flush=True)

    total = time.perf_counter() - inicio_total
    if rank == 0:
        print(f"\nProcesos: {size}")
        print(f"Tableros procesados: {len(tareas)} (resueltos: {resueltos})")
        if not args.id:
            print(f"Tiempo total real: {total:.6f} segundos")


if __name__ == "__main__":
    main()
