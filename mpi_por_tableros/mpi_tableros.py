"""Reparte los tableros entre los procesos con MPI y mide el tiempo total."""

import argparse
import sys
import time
from pathlib import Path

from mpi4py import MPI

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from baseline_secuencial import leer_seeds
from sudoku import resolver_con_tiempo


def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    parser = argparse.ArgumentParser(description="Sudoku MPI: reparto de tableros.")
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt")
    sel = parser.add_mutually_exclusive_group()
    sel.add_argument("--id", dest="id", help="resolver solo este ID")
    sel.add_argument("--all", action="store_true", help="resolver todos los IDs")
    args = parser.parse_args()

    if rank == 0:
        seeds = leer_seeds(args.archivo)
        if args.id:
            if args.id not in seeds:
                parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
            tareas = [(args.id, seeds[args.id])]
        else:
            tareas = list(seeds.items())
        partes = [tareas[i::size] for i in range(size)]
    else:
        partes = None

    comm.Barrier()
    inicio = time.perf_counter()

    mias = comm.scatter(partes, root=0)

    resultados = []
    for nombre, original in mias:
        tablero = [fila[:] for fila in original]
        resuelto, segundos = resolver_con_tiempo(tablero)
        resultados.append((nombre, resuelto, segundos, rank))
        print(f"[rank {rank}] ID {nombre}: {'Resuelto' if resuelto else 'Sin solución'} "
              f"en {segundos:.3f} s", flush=True)

    todos = comm.gather(resultados, root=0)
    total_real = time.perf_counter() - inicio

    if rank == 0:
        planos = sorted((r for lista in todos for r in lista), key=lambda r: int(r[0]))
        print("\n=== Resumen (ordenado por ID) ===")
        for nombre, resuelto, segundos, quien in planos:
            print(f"ID {nombre}: {'Resuelto' if resuelto else 'Sin solución'} "
                  f"| {segundos:.6f} s | rank {quien}")
        resueltos = sum(1 for r in planos if r[1])
        print(f"\nProcesos: {size}")
        print(f"Tableros procesados: {len(planos)} (resueltos: {resueltos})")
        print(f"Suma de tiempos por proceso (solo referencia): {sum(r[2] for r in planos):.6f} s")
        print(f"Tiempo total real: {total_real:.6f} segundos")


if __name__ == "__main__":
    main()
