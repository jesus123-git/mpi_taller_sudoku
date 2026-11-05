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
from sudoku import puede_colocar                  # noqa: E402

# --- Reparto de las ramas de UN tablero entre un grupo de procesos ---
# Una "rama" es el tablero con las primeras casillas vacias ya rellenadas con
# una combinacion valida. Cada proceso explora sus ramas con backtracking y el
# que encuentra la solucion avisa a los demas del grupo para que dejen de buscar.

TAG_TRABAJO = 1     # el lider envia las ramas
TAG_AVISO = 2       # "este tablero ya se resolvio, dejen de buscar"
TAG_RESULTADO = 3   # los miembros le dicen al lider si la encontraron
TAG_VEREDICTO = 4   # el lider le dice a todos si el tablero se resolvio

RAMAS_POR_PROCESO = 4   # se crean al menos 4 ramas por proceso
NODOS_ENTRE_REVISIONES = 2000


def primera_vacia(tablero):
    """Devuelve (fila, columna) de la primera casilla vacia, o None."""
    for f in range(9):
        for c in range(9):
            if tablero[f][c] == 0:
                return f, c
    return None


def generar_ramas(tablero, minimo):
    """Rellena la primera casilla vacia con cada valor valido, y repite
    hasta tener al menos `minimo` ramas."""
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
    """Mismo backtracking de sudoku.resolver, pero cada cierto numero de
    colocaciones pregunta hay_aviso(); si es True se detiene.
    Devuelve True solo si encontro la solucion."""
    contador = [0]
    detenido = [False]

    def buscar():
        for fila in range(9):
            for columna in range(9):
                if tablero[fila][columna] != 0:
                    continue
                for valor in range(1, 10):
                    if puede_colocar(tablero, fila, columna, valor):
                        tablero[fila][columna] = valor
                        contador[0] += 1
                        if contador[0] % NODOS_ENTRE_REVISIONES == 0 and hay_aviso():
                            detenido[0] = True
                            return False
                        if buscar():
                            return True
                        if detenido[0]:
                            return False
                        tablero[fila][columna] = 0   # retroceso
                return False
        return True                                  # no quedan casillas vacias

    return buscar()


def resolver_en_grupo(comm, miembros, tablero):
    """Resuelve un tablero con los procesos de `miembros` (lista de ranks).
    miembros[0] es el lider: reparte las ramas y tambien trabaja.
    Todos los miembros deben llamar a la funcion. `tablero` solo importa en el lider.
    Devuelve True en todos los miembros si el tablero se resolvio."""
    yo = comm.Get_rank()
    lider = miembros[0]
    cuantos = len(miembros)

    # 1) El lider crea las ramas y las reparte con send (reparto ciclico).
    if yo == lider:
        ramas = generar_ramas(tablero, RAMAS_POR_PROCESO * cuantos)
        for i, m in enumerate(miembros):
            if m != lider:
                comm.send(ramas[i::cuantos], dest=m, tag=TAG_TRABAJO)
        mis_ramas = ramas[0::cuantos]
    else:
        mis_ramas = comm.recv(source=lider, tag=TAG_TRABAJO)

    # 2) Cada uno deja una recepcion pendiente (irecv) para enterarse si
    #    alguien encuentra la solucion, y la revisa con test() mientras busca.
    espera_aviso = comm.irecv(source=MPI.ANY_SOURCE, tag=TAG_AVISO)
    estado = {"aviso": False}

    def hay_aviso():
        if not estado["aviso"]:
            estado["aviso"], _ = espera_aviso.test()
        return estado["aviso"]

    # 3) Cada uno explora sus ramas (el lider tambien).
    encontre = 0
    for rama in mis_ramas:
        if hay_aviso():
            break
        if resolver_con_aviso(rama, hay_aviso):
            encontre = 1
            # Los tableros tienen solucion unica, asi que solo un proceso llega
            # aqui. Avisa a todo el grupo, incluido el mismo.
            for m in miembros:
                comm.send("listo", dest=m, tag=TAG_AVISO)
            break

    # 4) Todos le reportan al lider y el lider responde con el veredicto.
    #    Tambien sirve de sincronizacion: nadie sigue hasta que todos terminaron.
    if yo == lider:
        total = encontre
        for m in miembros:
            if m != lider:
                total += comm.recv(source=m, tag=TAG_RESULTADO)
        if total == 0:
            # Nadie la encontro, asi que nadie aviso: el lider cierra las
            # recepciones pendientes para que quede un aviso por miembro.
            for m in miembros:
                comm.send("nada", dest=m, tag=TAG_AVISO)
        for m in miembros:
            if m != lider:
                comm.send(total, dest=m, tag=TAG_VEREDICTO)
    else:
        comm.send(encontre, dest=lider, tag=TAG_RESULTADO)
        total = comm.recv(source=lider, tag=TAG_VEREDICTO)

    # 5) Cada miembro atiende su aviso. Hubo exactamente uno por miembro, asi
    #    que no queda nada pendiente para el tablero siguiente.
    espera_aviso.wait()
    return total > 0


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
