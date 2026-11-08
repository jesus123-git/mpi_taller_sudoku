"""Reparte los tableros entre grupos de procesos y las ramas dentro de cada grupo."""

import argparse
import sys
import time
from pathlib import Path

from mpi4py import MPI

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from baseline_secuencial import leer_seeds
from sudoku import puede_colocar

TAG_TRABAJO = 1
TAG_AVISO = 2
TAG_RESULTADO = 3
TAG_VEREDICTO = 4

RAMAS_POR_PROCESO = 4
NODOS_ENTRE_REVISIONES = 2000


def primera_vacia(tablero):
    """Devuelve (fila, columna) de la primera casilla vacía, o None."""
    for f in range(9):
        for c in range(9):
            if tablero[f][c] == 0:
                return f, c
    return None


def generar_ramas(tablero, minimo):
    """Rellena las primeras casillas vacías hasta tener al menos minimo ramas."""
    ramas = [[fila[:] for fila in tablero]]
    for _ in range(8):
        if len(ramas) >= minimo or all(primera_vacia(r) is None for r in ramas):
            break
        nuevas = []
        for rama in ramas:
            pos = primera_vacia(rama)
            if pos is None:
                nuevas.append(rama)
                continue
            f, c = pos
            for valor in range(1, 10):
                if puede_colocar(rama, f, c, valor):
                    copia = [fila[:] for fila in rama]
                    copia[f][c] = valor
                    nuevas.append(copia)
        if not nuevas:
            break
        ramas = nuevas
    return ramas


def resolver_con_aviso(tablero, hay_aviso):
    """Backtracking que se detiene si otro proceso ya encontró la solución."""
    contador = 0
    detenido = False

    def buscar():
        nonlocal contador, detenido
        for fila in range(9):
            for columna in range(9):
                if tablero[fila][columna] != 0:
                    continue
                for valor in range(1, 10):
                    if puede_colocar(tablero, fila, columna, valor):
                        tablero[fila][columna] = valor
                        contador += 1
                        if contador % NODOS_ENTRE_REVISIONES == 0 and hay_aviso():
                            detenido = True
                            return False
                        if buscar():
                            return True
                        if detenido:
                            return False
                        tablero[fila][columna] = 0  # retroceso: probar otro valor
                return False
        return True  # no quedan casillas vacías

    return buscar()


def resolver_en_grupo(comm, miembros, tablero):
    """Resuelve un tablero repartiendo sus ramas entre los procesos de miembros."""
    yo = comm.Get_rank()
    lider = miembros[0]
    cuantos = len(miembros)

    if yo == lider:
        ramas = generar_ramas(tablero, RAMAS_POR_PROCESO * cuantos)
        for i, m in enumerate(miembros):
            if m != lider:
                comm.send(ramas[i::cuantos], dest=m, tag=TAG_TRABAJO)
        mis_ramas = ramas[0::cuantos]
    else:
        mis_ramas = comm.recv(source=lider, tag=TAG_TRABAJO)

    espera_aviso = comm.irecv(source=MPI.ANY_SOURCE, tag=TAG_AVISO)
    estado = {"aviso": False}

    def hay_aviso():
        if not estado["aviso"]:
            estado["aviso"], _ = espera_aviso.test()
        return estado["aviso"]

    encontre = 0
    for rama in mis_ramas:
        if hay_aviso():
            break
        if resolver_con_aviso(rama, hay_aviso):
            encontre = 1
            for m in miembros:
                comm.send("listo", dest=m, tag=TAG_AVISO)
            break

    if yo == lider:
        total = encontre
        for m in miembros:
            if m != lider:
                total += comm.recv(source=m, tag=TAG_RESULTADO)
        if total == 0:
            for m in miembros:
                comm.send("nada", dest=m, tag=TAG_AVISO)
        for m in miembros:
            if m != lider:
                comm.send(total, dest=m, tag=TAG_VEREDICTO)
    else:
        comm.send(encontre, dest=lider, tag=TAG_RESULTADO)
        total = comm.recv(source=lider, tag=TAG_VEREDICTO)

    espera_aviso.wait()
    return total > 0


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
    mis_tareas = tareas[color::n_grupos]

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
