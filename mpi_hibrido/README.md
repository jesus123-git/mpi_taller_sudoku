# Tarea 3: combinar tableros y ramas

Implementa una versión MPI en esta carpeta. Reparte los IDs entre grupos de procesos y permite que los procesos de cada grupo exploren ramas distintas del tablero asignado.

Registra el tiempo total de los 30 IDs y explica cómo elegiste el tamaño de los grupos. Añade aquí el comando para ejecutar tu implementación con el contenedor. Incluye `--allow-run-as-root --use-hwthread-cpus --oversubscribe` en `mpiexec`, como en la calibración.

## Implementación

`mpi_hibrido.py` arma los grupos con aritmética de rangos, sin comunicadores nuevos:
con `N` procesos y `--grupo G` se forman `N // G` grupos de `G` procesos consecutivos
(si `N` no es múltiplo de `G`, el último grupo absorbe el resto). Cada proceso calcula
la lista de miembros de su grupo y el primero de esa lista es el líder.

Los 30 IDs se reparten cíclicamente entre los grupos. Dentro de cada grupo se aplica
el reparto de ramas de `../ramas_comun.py`: el líder genera las ramas, las envía con
`send`, también busca, y el primero que encuentra la solución avisa al resto del grupo.
Los grupos trabajan de forma independiente, y los avisos solo se envían a miembros del
mismo grupo, así que no se cruzan mensajes entre grupos. Al final el rank 0 global reúne
los estados con `gather` y reporta el tiempo total real.

Primitivas MPI usadas: `send`, `recv`, `irecv` (con `test` y `wait`), tags,
`MPI.ANY_SOURCE`, `gather` y `barrier`.

## Cómo elegir el tamaño de los grupos

Con `N = 8` los tamaños de grupo que dividen a `N` son 1, 2, 4 y 8. Los extremos
coinciden con las otras dos tareas: `G = 1` equivale a repartir solo tableros y
`G = 8` a repartir solo ramas, así que los casos propios del híbrido son `G = 2`
y `G = 4`. Se mide cada uno tres veces con `--all` y se escoge el de menor mediana.

| `G` (procesos por grupo) | Grupos | Repeticiones (s) | Mediana (s) |
| ---: | ---: | --- | ---: |
| 2 | 4 | 82,531 / 82,960 / 79,808 | 82,531 |
| 4 | 2 | 82,687 / 69,805 / 82,412 | 82,412 |

Valor elegido: **G = 4**, por ser la menor mediana.

Advertencia honesta sobre esa elección: la diferencia entre las dos medianas es
de 0,119 s sobre unos 82 s, es decir 0,14%, mientras que las repeticiones de una
misma configuración varían hasta un 15% (de 69,805 s a 82,687 s con G = 4). La
diferencia entre G = 2 y G = 4 queda muy por debajo del ruido de medición del
equipo, así que lo correcto es decir que ambos tamaños de grupo rinden igual en
este equipo y que se escogió G = 4 solo por el valor medido.

## Ejecución (desde la raíz del proyecto, reemplaza `N` y `G`)

```powershell
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/mpi_hibrido.py --all --grupo G
```

macOS/Linux: cambia `${PWD}` por `$(pwd)`.
