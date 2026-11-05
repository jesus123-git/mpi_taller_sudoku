# Tarea 2: repartir ramas de cada tablero

Implementa una versión MPI en esta carpeta. Con `--all`, el proceso coordinador lee los 30 IDs de `seeds.txt` en orden. Para cada tablero, crea tareas a partir de opciones válidas de las primeras casillas vacías y reparte esas ramas entre procesos. Espera a que termine ese tablero antes de comenzar el siguiente: **los tableros se procesan secuencialmente y las ramas de cada tablero en paralelo**.

Cada proceso explora su rama con backtracking y comunica el resultado. Cuando se encuentra una solución, los demás deben dejar de buscar ese tablero. Muestra el estado y el tiempo parcial de cada ID al terminarlo, además del tiempo total de los 30. Conserva la opción `--id` para resolver un solo tablero.

Añade aquí los comandos para ejecutar `--id` y `--all` con el contenedor. Incluye `--allow-run-as-root --use-hwthread-cpus --oversubscribe` en `mpiexec`, como en la calibración. Compara el tiempo total de `--all` con la versión secuencial y registra los resultados en `../INFORME.md`.

## Implementación

`mpi_ramas.py` recorre los 30 IDs en orden, uno después de otro. Para cada tablero,
el líder (rank 0) genera las ramas con `generar_ramas` (definida en `mpi_ramas.py`):
rellena las primeras casillas vacías con sus valores válidos hasta tener al menos
4 ramas por proceso, y las reparte con `send` (reparto cíclico). Cada proceso,
el líder incluido, explora sus ramas con el mismo backtracking de `../sudoku.py`.

Antes de buscar, cada proceso deja una recepción pendiente con `irecv`; cada 2000
colocaciones la consulta con `test()`. El proceso que encuentra la solución avisa
con `send` a todo el grupo (también a sí mismo) y los demás abandonan ese tablero.
Después todos reportan su estado al líder y el líder responde el veredicto: eso
sincroniza el fin del tablero antes de empezar el siguiente. Si nadie encuentra
solución, el líder envía el aviso de cierre, de modo que siempre hay exactamente
un aviso por proceso y por tablero y nada queda pendiente.

Primitivas MPI usadas: `send`, `recv`, `irecv` (con `test` y `wait`), tags,
`MPI.ANY_SOURCE` y `barrier`.

## Ejecución (desde la raíz del proyecto, reemplaza `N` por el valor calibrado)

PowerShell:

```powershell
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_ramas.py --all
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_ramas.py --id 7
```

macOS/Linux: cambia `${PWD}` por `$(pwd)`.
