"""MPI hibrido: los IDs se reparten entre GRUPOS de procesos y, dentro de cada
grupo, los procesos se reparten las ramas del tablero asignado.

  N procesos, --grupo G  ->  N // G grupos de G procesos (el ultimo absorbe el resto).
  El primer proceso de cada grupo (lider) coordina las ramas de sus tableros y
  tambien trabaja. El rank 0 global reune los estados con gather.
"""

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

    parser = argparse.ArgumentParser(description="Sudoku MPI hibrido: grupos de procesos.")
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt")
    parser.add_argument("--grupo", type=int, default=2,
                        help="procesos por grupo (por defecto 2)")
    sel = parser.add_mutually_exclusive_group()
    sel.add_argument("--id", dest="id", help="resolver solo este ID")
    sel.add_argument("--all", action="store_true", help="resolver todos los IDs")
    args = parser.parse_args()

    g = max(1, min(args.grupo, size))
    n_grupos = size // g
    # numero de grupo de cada proceso (el ultimo grupo absorbe el resto)
    color = min(rank // g, n_grupos - 1)
    miembros = [r for r in range(size) if min(r // g, n_grupos - 1) == color]
    es_lider = (rank == miembros[0])

    seeds = leer_seeds(args.archivo)
    if args.id:
        if args.id not in seeds:
            parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
        tareas = [(args.id, seeds[args.id])]
    else:
        tareas = list(seeds.items())
    mis_tareas = tareas[color::n_grupos]          # reparto ciclico de IDs entre grupos

    comm.Barrier()
    inicio_total = time.perf_counter()

    resultados = []
    for nombre, original in mis_tareas:
        inicio = time.perf_counter()
        resuelto = resolver_en_grupo(comm, miembros, original if es_lider else None)
        segundos = time.perf_counter() - inicio
        if es_lider:
            resultados.append((nombre, resuelto, segundos, color))
            print(f"[grupo {color}] ID {nombre}: {'Resuelto' if resuelto else 'Sin solución'} "
                  f"en {segundos:.3f} s", flush=True)

    todos = comm.gather(resultados, root=0)
    total = time.perf_counter() - inicio_total

    if rank == 0:
        planos = sorted((r for lista in todos for r in lista), key=lambda r: int(r[0]))
        print("\n=== Resumen (ordenado por ID) ===")
        for nombre, resuelto, segundos, quien in planos:
            print(f"ID {nombre}: {'Resuelto' if resuelto else 'Sin solución'} "
                  f"| {segundos:.6f} s | grupo {quien}")
        resueltos = sum(1 for r in planos if r[1])
        resto = " (el último absorbe el resto)" if size % g else ""
        print(f"\nProcesos: {size} | grupos: {n_grupos} de {g} procesos{resto}")
        print(f"Tableros procesados: {len(planos)} (resueltos: {resueltos})")
        print(f"Tiempo total real: {total:.6f} segundos")


if __name__ == "__main__":
    main()
