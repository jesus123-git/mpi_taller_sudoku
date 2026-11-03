# Informe de resultados

Completa este informe después de implementar las tres tareas MPI. Ejecuta las comparaciones con el mismo archivo `seeds.txt`, en el mismo equipo y con el contenedor del taller.

## Entorno

- Equipo: AMD Ryzen 5 5500U (6 núcleos físicos, 12 hilos), Windows con Docker Desktop
- Versión del contenedor: `augustosalazar/slim-mpi:2` (digest `sha256:a196b8fd2aec025fa393bc517ef7f541f4dbe70c8b42c06639289fbb9f7ff94d`)
- Cantidad de repeticiones por medición: 3
- Valor común de `N` elegido: **8** (`detectar_procesos_mpi.py` probó N=1..12 y dio la menor mediana en N=8, con 2,828 s)

## Comparación final con el mismo `N`

Repite tres veces cada ejecución y registra la mediana. Mantén fijo el `N` elegido en todas las filas MPI. Incluye `--allow-run-as-root --use-hwthread-cpus --oversubscribe` en `mpiexec`, igual que en la calibración, para permitir valores de `N` mayores que los slots detectados.

| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración frente a secuencial |
| --- | --- | ---: | ---: | ---: |
| Secuencial | Todos los IDs | 1 | 293,385 | 1,00 |
| MPI por tableros | Todos los IDs | 8 | 84,800 | 3,46 |
| MPI por ramas | Todos los IDs, uno después de otro | 8 | 84,545 | 3,47 |
| MPI híbrido | Todos los IDs, grupos de 4 procesos | 8 | 82,412 | 3,56 |

Calcula la aceleración como `tiempo secuencial / tiempo MPI`. Mide el tiempo MPI desde el inicio del reparto hasta recibir todos los resultados necesarios.

En la fila del híbrido se usó `--grupo 4`; la comparación entre valores de G está en `mpi_hibrido/README.md`.

Las cuatro filas provienen de una misma sesión de medición, para que compartan las mismas condiciones de máquina.

## Variabilidad de las mediciones

El equipo es un portátil, de modo que las repeticiones de una misma configuración
varían de forma apreciable. Se registran las dos sesiones completas que se
ejecutaron, cada una con tres repeticiones por fila:

| Implementación | Sesión 1 (`--grupo 2`) | Sesión 2 (`--grupo 4`) |
| --- | ---: | ---: |
| Secuencial | 333,807 / 295,173 / 267,833 -> **295,173** | 354,935 / 266,359 / 293,385 -> **293,385** |
| MPI por tableros | 85,775 / 75,850 / 74,645 -> **75,850** | 97,073 / 84,725 / 84,800 -> **84,800** |
| MPI por ramas | 89,986 / 96,172 / 81,953 -> **89,986** | 84,923 / 84,545 / 79,364 -> **84,545** |
| MPI híbrido | 82,531 / 82,960 / 79,808 -> **82,531** | 82,687 / 69,805 / 82,412 -> **82,412** |

Las dos medianas del secuencial coinciden (295,173 s y 293,385 s, 0,6% de
diferencia), así que la referencia es estable. Las filas MPI, en cambio, se
mueven hasta un 15% entre repeticiones de la misma configuración. Ese margen es
mayor que las diferencias entre las tres estrategias, y hay que tenerlo presente
al leer las conclusiones.

## Conclusiones

**Qué estrategia obtuvo el menor tiempo para los 30 tableros y cuánto mejoró
respecto a la versión secuencial.**

El menor tiempo medido fue el del híbrido con grupos de 4 procesos: 82,412 s
frente a 293,385 s del secuencial, una aceleración de 3,56x. Sin embargo, las
tres implementaciones quedaron entre 82 y 85 s en esa sesión, y en la sesión
anterior la más rápida fue el reparto por tableros con 75,850 s (3,89x). Como
las diferencias entre estrategias son menores que la variación entre
repeticiones, los datos no permiten declarar una ganadora clara. Lo que sí es
consistente en las dos sesiones es que cualquiera de las tres reduce el tiempo
a aproximadamente la cuarta parte del secuencial, con aceleraciones entre 3,3x
y 3,9x.

Conviene notar que la aceleración se queda lejos de 8 aún usando N=8. El equipo
tiene 6 núcleos físicos y 12 hilos, de modo que con 8 procesos hay
sobresuscripción: dos procesos comparten núcleo y no rinden como dos núcleos
independientes. Parte de la pérdida no es atribuible a MPI sino al hardware
disponible. La calibración ya lo insinuaba: entre N=4 (4,034 s) y N=8 (2,828 s)
la mejora fue mucho menor que entre N=1 y N=4.

**Cómo afectaron la comunicación y las diferencias de duración entre tableros.**

Los 30 tableros no cuestan lo mismo: en serial cada uno tarda entre 2 y 10
segundos aproximadamente. En el reparto por tableros, los IDs se asignan de
forma estática y cíclica antes de empezar, así que un proceso al que le toquen
varios tableros largos termina mucho después que los demás, y el tiempo total
lo fija el proceso más lento mientras el resto espera. A cambio, la
comunicación es mínima: un scatter al principio y un gather al final.

El reparto por ramas elimina ese desbalance, porque todos los procesos trabajan
sobre el mismo tablero a la vez. El costo es el opuesto: hay comunicación en
cada uno de los 30 tableros (envío de ramas, aviso de solución encontrada y
reporte al líder), y una sincronización por tablero que obliga a esperar al más
lento antes de empezar el siguiente. Ademas aparece trabajo desperdiciado: los
procesos exploran ramas que no contienen la solución hasta que alguien avisa,
esfuerzo que la versión secuencial nunca habría hecho.

**Cómo se comparó repartir tableros con resolverlos en orden y repartir las
ramas de cada uno.**

En la primera sesión el reparto por tableros fue claramente mejor que el de
ramas: 75,850 s frente a 89,986 s, un 16% más rápido. En la segunda sesión
quedaron prácticamente empatados (84,800 s y 84,545 s). Tomando las dos en
conjunto, repartir tableros es al menos tan bueno como repartir ramas y es
bastante más simple de implementar, porque solo necesita dos comunicaciones en
toda la ejecución en lugar de varias por tablero.

El híbrido se ubica entre los dos, que es lo esperable dado que combina ambos
mecanismos: reparte IDs entre grupos, con lo que reduce la comunicación frente
a la versión por ramas, y reparte ramas dentro de cada grupo, con lo que suaviza
el desbalance frente a la versión por tableros. Obtuvo el mejor tiempo de la
segunda sesión, pero por un margen dentro del ruido de medición.
