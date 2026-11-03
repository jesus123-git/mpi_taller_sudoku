# Tarea 1: repartir tableros

Implementa una versión MPI en esta carpeta. Al ejecutar todos los tableros, cada ID debe ser una tarea que pueda asignarse a un proceso. Reutiliza el resolvedor de `../sudoku.py` y reúne los estados en el proceso coordinador.

Registra el tiempo total de ejecución y confirma que se procesaron los 30 IDs. Añade aquí el comando para ejecutar tu implementación con el contenedor. Incluye `--allow-run-as-root --use-hwthread-cpus --oversubscribe` en `mpiexec`, como en la calibración.

## Implementación

`mpi_tableros.py`: el rank 0 lee `seeds.txt`, reparte los IDs de forma cíclica con `scatter` (ID i → proceso i mod N), **resuelve también sus propios tableros** y reúne los estados con `gather`. Reutiliza `resolver_con_tiempo` de `../sudoku.py`. El tiempo total se mide en el rank 0 con `time.perf_counter()` desde después de un `Barrier` hasta que llega el `gather`.

## Ejecución (desde la raíz del proyecto, reemplaza `N` por el valor calibrado)

PowerShell:

```powershell
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_tableros.py --all
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_tableros.py --id 7
```

macOS/Linux: cambia `${PWD}` por `$(pwd)`.
