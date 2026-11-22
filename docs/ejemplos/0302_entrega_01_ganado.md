# Detección de Ganado en Imágenes de Drones mediante Deep-Learning

### 1. Problema y contexto

Los ganaderos en todo el mundo enfrentan desafíos significativos en el monitoreo y conteo de ganado, tareas esenciales para el manejo efectivo del pastoreo, control de inventario y eficiencia operacional. Los métodos tradicionales de conteo manual involucran a los ganaderos caminando físicamente a través de los pastizales para contar y monitorear su ganado, un proceso que es tanto intensivo en mano de obra como consumidor de tiempo.

### 1.1. Desafíos Clave Enfrentados por los Ganaderos:

#### **_Ineficiencias Operacionales:_**

- El conteo manual de ganado requiere recursos significativos de mano de obra e inversión de tiempo.

- Las grandes áreas de pastoreo hacen que el monitoreo integral sea difícil y costoso.

- La dispersión del ganado a través de tierras extensas complica el conteo preciso.

- Las condiciones climáticas y la accesibilidad del terreno pueden limitar la frecuencia de monitoreo.

#### **_Barreras Económicas y Tecnológicas:_**

- Altos costos de inversión inicial para tecnologías avanzadas de rastreo (GPS, RFID, dispositivos IoT).

- Acceso limitado a conectividad de red confiable en áreas rurales.

- Brechas de conocimiento técnico entre ganaderos para implementar soluciones modernas de monitoreo.

- Costos continuos de mantenimiento y preocupaciones sobre durabilidad del equipo.

#### **_Restricciones de Mano de Obra y Recursos:_**

- Escasez de mano de obra agrícola calificada especializada en monitoreo de ganado.

- Procesos manuales que consumen tiempo y que podrían ser mejor asignados a otras tareas de manejo de la finca.

### 2. Pregunta de negocio y alcance del proyecto

¿Puede la visión por computadora apoyar las operaciones ganaderas reemplazando el conteo manual de ganado?

#### **_Objetivo del proyecto:_**

Desarrollar un sistema basado en visión por computadora capaz de detectar y contar automáticamente ganado en imágenes aéreas capturadas por drones, proporcionando a los ganaderos una alternativa eficiente y costo-efectiva al monitoreo manual de ganado.

#### **_Alcance técnico y operativo del proyecto:_**

1. Desarrollo de un sistema de detección de ganado utilizando modelos de deep learning (e.g., YOLOv8, FCOS, CenterNet), optimizados para objetos pequeños en imágenes de alta resolución.

2. Uso de imágenes de drones (nadirales) con alta resolución y etiquetadas, provenientes de los datasets públicos SKY e ICAERUS.

3. Entrenamiento y validación del modelo sobre los conjuntos de datos mencionados, con métricas clave como precisión, recall, IoU, y error porcentual de conteo.

4. Desarrollo (opcional según viabilidad) de mecanismos de seguimiento (tracking) para evitar contar la misma vaca varias veces debido a la superposición de imágenes.

5. Validación de la solución en escenarios controlados, similares a los datos de entrenamiento: terrenos planos, condiciones climáticas soleadas, y ganado visible como objetos pequeños en las imágenes.

6. Evaluación de la viabilidad comercial del sistema, incluyendo:

   - Velocidad de procesamiento en hardware típico (e.g., laptop con GPU).

   - Escalabilidad para hatos grandes.

   - Experiencia de usuario para ganaderos no técnicos.

   - Capacidad de clasificar el ganado por tamaño (ternero vs. vaca adulta).

### 3. Descripción de conjuntos de datos a emplear

Al tratarse de un microproyecto y dado la corta ventana de tiempo para desarrollarlo, no recolectaremos ni crearemos datos. Usaremos dos fuentes de datos existentes de terceros, a saber:

**_Conjunto de Datos "SKY":_** <u>(https://datasetninja.com/cattle-detection-and-counting-in-</u>

<u>uav-images). Consiste en 670 imágenes fotográficas de drones, canales RGB. Este</u> conjunto de datos, incluyendo datos en formato json que contienen cajas delimitadoras (bounding boxes) marcando 1949 instancias de animales (bovinos). El formato de estas imágenes es JPG, a una resolución de 4,000 x 3,000 pixeles cada una. El tamaño total de este data set es de aproximadamente 3 GB.

Las imágenes del conjunto de datos "SKY" son imágenes tomadas desde drones sobrevolando a una altura de 50 metros y cada una cubre un terreno de aproximadamente 80m x 60m. La superposición de imágenes sucesivas es aproximadamente 80%. Son imágenes de nadir, es decir con la cámara apuntando siempre directamente hacia abajo. Este es el esquema de la estructura de directorios y archivos del dataset:

|Nivel 1 Subdataset|Nivel 2 Tipo de Item|Nivel 3 Archivo individual|
|---|---|---|
|DatasetN|img|DJI_0032.JPG|
|DatasetN|ann|DJI_0032.JPG.kson|



**_Conjunto de datos de ICAERUS:_** <u>(https://zenodo.org/records/11048412). Consiste en</u> 1385 imágenes RGB. Se tomaron en entre junio de 2023 y marzo de 2024, sobre 4 haciendas ganaderas de Francia, El conjunto de datos incluye 4,941 anotaciones (cajas delimitadoras) alrededor de vacas individuales pastando. El formato de las imágenes es JPG a resolución de 4,000 x 3,000 pixeles o 5,280 x 3,956 pixeles y las anotaciones vienen dadas en dos formatos:

- PASCAL_VOC1.1 (xml) un archivo por cada imagen conteniendo 0,1 o más anotaciones, cada uno en un elemento (tag) XML independiente.

- YOLO_V1.1 (txt) un archivo por cada imagen conteniendo 0,1 o más anotaciones, cada una en una línea de texto consistente de varios números de coma flotante correspondiendo a la clase del bounding box las coordenadas del centro de esta, su ancho y alto.

El conjunto de datos ICAERUS también consiste en imágenes de nadir tomadas desde drones a altitudes que variaban entre los 60 y los 100 metros. Este es el esquema de la estructura de directorios y archivos del dataset:

|Nivel 1|Nivel 2|Nivel 3|Nivel 4/5|
|---|---|---|---|
|Hacienda|Id de Formato|Id del sobrevuelo|Archivo individual|
|Sssss|JPGImages|DJI_YYYYMMDDHHMM_XXX|DJI_YYYYMMDDHHMMSS_NNNN_V.JPG|
|Sssss|PASCAL_VOC1.1|DJI_YYYYMMDDHHMM_XXX|DJI_YYYYMMDDHHMMSS_NNNN_V.xml|
|Sssss|YOLO_1.1|DJI_YYYYMMDDHHMM_XXX|obj_train_data/DJI_YYYYMMDDHHMMSS_NNNN_V.txt|



## 4. Exploración de los datos

### 4.1. Objetivo de la exploración de los datos

El objetivo de este análisis exploratorio es comprender en profundidad las características, distribución y particularidades de los conjuntos de datos SKY e ICAERUS caracterizando los datos de imágenes aéreas para conteo y detección de animales, verificando su estructura, calidad, balance y variabilidad (escala, oclusiones, densidad por imagen) y derivando implicaciones para el modelado (detección vs. conteo denso, definición de métricas y particiones robustas de entrenamiento, validación, y prueba).

### 4.2. Alcance de los datos analizados

- **SKY** : 670 imágenes RGB (4000×3000 px) con 1.949 cajas delimitadoras (bovinos), capturadas a ≈50 m de altura, tomas nadir, ≈80 % de superposición entre imágenes sucesivas.

- **ICAERUS** : 1.385 imágenes RGB (4000×3000 o 5280×3956 px) con 4.941 anotaciones (bovinos), archivos en PASCAL VOC y YOLO; vuelos a 60–100 m 4.3.

### 4.3. Estructura y formatos Imágenes

RGB, aéreas, nadir; resoluciones altas. (4000×3000 o 5280×3956 px) .

Anotaciones: SKY: JSON por imagen; ICAERUS: VOC/XML (xmin,ymin,xmax,ymax) y YOLO/TXT (clase, x_c, y_c, w, h normalizados).

Particiones: train/val/test provistas por el dataset principal; mantener estratificación por especie y densidad al integrar datos adicionales.

- 4.4. Plan de limpieza y estandarización para mitigación de desafíos

   - Conversión a COCO con campos como: image_id, width, height, bbox_[x,y,w,h], area, class/species, source.

   - Normalización de clases: mapear taxonomías y unificar labels (bovino vs. especies silvestres).

   - Detección de duplicados/superposición: en SKY existe alrededor de 80 % de solape entre imágenes adyacentes; evitar fuga entre splits.

   - Validación de anotaciones: bboxes con w/h=0, fuera de límites, o clases vacías.

   - Metadatos opcionales: altura de vuelo, fecha/hora, finca/sitio (si disponibles) para análisis estratificado.

## 4.5. Balance y particiones

Verificar equilibrio especie/ densidad en train/val/test (dataset principal ya lo provee). Mantener independencia por sobrevuelo/sitio al integrar SKY/ICAERUS para no inflar métricas.



<!-- Start of picture text -->
Distribucién de instancias por imagen<br>35<br>30<br>a<br>ovc<br>5 25<br>8<br>—<br>3 20<br>2<br>re}<br>2<br>$15<br>rs<br>2<br>iia<br>10<br>5<br>°<br>2.5 5.0 75 10.0 12.5 15.0 17.5 20.0 22.5<br>N° de cajas por imagen<br><!-- End of picture text -->

Figura 1: Distribución de instancias por imagen



<!-- Start of picture text -->
Distribucién de areas de bbox<br>250<br>200<br>2<br>2<br>5 150<br>Ss3<br>&<br>100<br>50<br>%.0000 0.0005 0.0010 0.0015 0.0020 0.0025 0.0030 0.0035<br>Area relativa del bbox (w*h normalizado)<br><!-- End of picture text -->

_Figura 2: Distribución de áreas de Bounding Boxes_



<!-- Start of picture text -->
Dispersién ancho vs alto de bboxes<br>0.08 oat<br>0.07 feet .<br>E 0.06 nbs Pek a Ee Pi<br>S 1 “ae Te te TS AS ap he “Wa at .<br>s weed ye ig. es eR Se oe ye .<br>S3 0.05 pr egg Sant aeseg Jet oR Sire das . *<br>ye Be Fea Blow yaimetl feds Bee acs ee ont<br>E 0.04 : a oea ore rages aye atesa.oe<br>en te Py (87 tees 3 oa<br>=<2Pied :PesrRONEnti,oerSRD2 fatePeTGAsaeth aghl eeeShee  Qe ETee ih ey . ao5<br>nose hy’ el) teasaba pet st<br>0.02+ eePe a ee "« Lay<br>+ EE eI Te De :<br>*<br>0.01 . we . "ee “att . *<br>“oo se .<br>0.01 0.02 0.03 0.04 0.05 0.06<br>Ancho normalizado (w_norm)<br><!-- End of picture text -->

_Figura 3: Dispersión de ancho vs alto de Bounding Boxes_

4.6. Licencia Se respetarán las condiciones de licencia (CC BY-NC-SA 4.0).

## 5. Maqueta del prototipo



<!-- Start of picture text -->
aae<br>iv)<br>u CowDetect<br>a)<br>Videos<br>C BD nen mere as Ou:<br>° i i Ss Se<br>'<br>*<br>. = = _ "<br>2 Recomido 11082022 Recomao 15.2202 Recomdo 20022022 como :so22021<br><!-- End of picture text -->



<!-- Start of picture text -->
aat<br>tv) 2<br>g CowDetect - Recorrido 1<br>c+]<br>Pred: cow 1.000 Analisis<br>2 Pred: cow 1,000<br>e= bred: cow 0.986 iw) 5 Eneste frame: 4 cabezas<br>* Bred Se Pred: cow 1,000 | conteo contirmado: 10<br>. & Confianza media: 0.90<br>- x Umbral aplicado: 0.60<br>= Posibles ocultas: 1 (revisar)<br>wy ay Ay<br><!-- End of picture text -->



<!-- Start of picture text -->
aar<br>3 CowDetect<br>H Tite 2 owner created # conedo<br>* ©<br>Recorido1 @ s0cob wikins 05 March 2022 10<br>a econo? @ s0c00 wikine 15 0212021 15<br>fm<br>Recorrido3 ® Lavra ken 05 Sep 202 2<br>*<br>©<br>. Recorrido4 © bon simon 05 Moreh 2021 2<br>» Records © 260 simon 10 Feb 2021 »<br>© ecarido @ hon won 8 son 2022 1s<br>tm Recortiso7 ©<br>roches. 05 Jon 2022 2<br>©<br>Recortido8 © Roches 22.300 2021 “<br><!-- End of picture text -->

### 6. Repositorios creados

Dadas las restricciones de seguridad que presenta Aws Labs al momento de querer tener acceso a un bucket S3 compartido para los integrantes del proyecto, decidimos crear una cuenta personal en AWS, aprovechando la capa gratuita que ofrecen por 6 meses, para poder tener control sobre los usuarios y políticas de acceso sobre el bucket S3 que se usara para el DVC (control de versiones de datos).

Por otro lado, se creó un repositorio en Github, en el que se almacenara todo el código y recursos adicionales para el desarrollo del proyecto.

#### **_Repositorio Github_**

<u>https://github.com/maia-2025-vision/proyecto-desarrollo-soluciones</u>



<!-- Start of picture text -->
] proyecto-desarrollo-soluciones Edit Pins ~ —§ © Watch<br>P<br>main~  1Branch © OTag 2G t + | <> Code~<br>@ aleapoveda 3 50980e day ©2Commits<br>B® dve aliza re| esterda\<br>[} dvcignore za c c esterda<br>}) .gitignore<br>[) README.md a t 5 0<br>5) data.dve 3<br><!-- End of picture text -->

#### **_Bucket S3_**



<!-- Start of picture text -->
| = data-deso! o ase<br>data-desol ..<br>Objects Metadata Properties «Permissions —«Metrics_«=«“ Management ~—_Access Points<br>Objects(1<br>Q 1 eS<br>Name a | te > | Last modifies | size<br>o Folder<br><!-- End of picture text -->

#### **_AWS Usuarios y políticas de acceso_**

Las políticas fueron configuradas de acuerdo con los requerimientos de DVC. <u>https://dvc.org/doc/user-guide/data-management/remote-storage/amazon-s3</u>



<!-- Start of picture text -->
ff El usuariode AWS necesita los siguientes permisos: s3:ListBucket,<br>s3:GetObject , s3:PutObject , s3:DeleteObject .<br><!-- End of picture text -->



<!-- Start of picture text -->
= 1AM > Users > dve-user<br>dvc-user nro<br>Permissions Groups Tags _ Security credentials<br>woe we<br>Permissions policies (1)<br>Permissions<br>are defined by policies attached to the user directly or through<br>Filter by Type<br>Sonrch<br>Q Sear All types<br>Policy name [2<br>Hl dveaccess<br>Oe]<br><!-- End of picture text -->



<!-- Start of picture text -->
dvc-access inio<br>Policy details<br>5 Creationation timetim<br>ype August 22, 2025, 23:57 (UTC-05:00)<br>Customer managed<br>Permissions defined in this policy info<br>Permissions defined in this policy document specify which actions are al<br>ae 7"<br>2 Version": "2012-10-17",<br>3a Statement”:{ [<br>65 "Sid":“effect”:"Visualeditore”,“Allow”,<br>7 "action": [<br>8 s3:ListBucket”,<br>9 s3:Putobject”,<br>10 “s3:GetObject”,<br>aa s3:Deletedbject<br>a2 L<br>43 *Resource”: [<br>144s arn:arn: aws:53:::data-desol”,aws: 53: : :data-desol/*<br>46 ]<br>7 }<br>a8 ]<br>19<br><!-- End of picture text -->

#### **_Configuracion DVC_**

Inicializamos dvc en el proyecto y agregamos el folder completo de **_data_** para hacer seguimiento sobre todo su contenido.



Configuramos localmente las credenciales de AWS (compartidas internamente por el equipo).  Estas credenciales quedan asociadas al perfil **dvc-user** , para evitar conflictos con alguna otra credencial de AWS existente.



<!-- Start of picture text -->
(maia) C:\Users\aleap\MAIA\desarrollo-soluciones\proyecto-desarrollo-soluciones>aws configure --profile dvc-user<br>AWS Secret Access Key [None]: iit<br>Default region name [None]: us-east-1<br>Default output format [None<br><!-- End of picture text -->

Definimos el repositorio remoto y el perfil de AWS que debe usar para la conexión el DVC.



<!-- Start of picture text -->
(maia) C:\Users\aleap\ATA\desarrol1o-soluciones\proyecto-desarrollo-soluciones>dvc remote add -d aws-remote s3://data-desol<br>Setting ‘aws-remote’ as a default remote.<br>(maia) C:\Users\aleap\MAIA\desarrol1lo-soluciones\proyecto-desarrollo-soluciones>dvc remote modify aws-remote profile dvc-user<br><!-- End of picture text -->

#### Finalizamos haciendo push de los datos al DVC.



<!-- Start of picture text -->
(naia) C:\users\aleap\AIA\desarrollo-soluciones \proyecto-desarrollo-soluciones>dve push<br>Pushing<br><!-- End of picture text -->

Después de ejecutar dvc push, validamos la carga de los archivos en S3, el estado de la configuración de dvc y el estado actual del archivo data.dvc



<!-- Start of picture text -->
S3  .dvc/config  data.dvc<br>B a E config X F datade x<br>md5/ = config E dat<br>objects | Properties [core] - dS: 4366573#3439bF452b5 fo8afo4F46738.dir<br>— remote = aws-remote ize: 20713580071<br>Objectscoun  (256)nen nso [‘remoteurl = “aws-remote”*s3://data-desol ] hash:ifilestmdsaR<br>a profile = dvc-user path: data<br>a Fel<br>a fet<br><!-- End of picture text -->

## 7. Reporte de trabajo en equipo

|**Actividad**|**Responsable**|
|---|---|
|Problemaycontexto|Todos|
|Pregunta de Negocioyalcance|Todos|
|Descripción de conjuntos de datos|Mateo Restrepo Mejía|
|Exploración de los datos|Jose Daniel Pineda Carvajal|
|Maqueta delprototipo|Míxer Frender Gutiérrez Acevedo|
|Repositorios creados|Andrés Alea|
