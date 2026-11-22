

<!-- Start of picture text -->
Universidad de<br>los Andes<br>Colombia<br><!-- End of picture text -->

# **PulmoIA**

**Detección asistida de enfermedades pulmonares en radiografías de tórax**

_Avance de proyecto_



Maria Isabel Eraso Danilo Duarte        Juan Pablo Luna Erick Pérez

AGOSTO DE 2025





<!-- Start of picture text -->
Universidad de<br>los Andes<br>Colombia<br><!-- End of picture text -->



<!-- Start of picture text -->
°<br>° °<br>e<br><!-- End of picture text -->

## Problema y contexto

La pandemia por COVID-19, declarada en marzo de 2020 por la Organización Mundial de la Salud (OMS), generó una crisis sanitaria global sin precedentes en el siglo XXI. Uno de los principales retos fue el diagnóstico temprano y confiable de la enfermedad, fundamental para contener la propagación del virus y mejorar las tasas de supervivencia de los pacientes.

Si bien la prueba RT-PCR se consolidó como el estándar de referencia para la detección del SARS-CoV2, presentaba limitaciones en términos de disponibilidad, tiempo de respuesta y sensibilidad (Ai et al., 2020). En este contexto, las imágenes médicas, como las radiografías de tórax, se convirtieron en una herramienta complementaria de gran valor para identificar neumonía viral asociada al COVID-19.

La historia del arte médico ha demostrado cómo la imagen ha sido clave en el avance de la medicina: desde los primeros grabados anatómicos del Renacimiento hasta la invención de los rayos X por Wilhelm Röntgen en 1895, el uso de imágenes para visualizar lo invisible ha transformado la práctica clínica (Daston & Galison, 2007). En la pandemia de COVID-19, la radiografía digital se consolidó como un puente entre la tradición médica y la inteligencia artificial aplicada al diagnóstico.

En este marco, surge el COVID-19 Radiography Database (Chowdhury et al., 2020), que compila más de 21.000 imágenes de radiografías de tórax clasificadas en cuatro categorías: COVID-19, neumonía viral, neumonía bacteriana y casos normales. Este recurso ha sido fundamental para el entrenamiento de modelos de aprendizaje automático capaces de apoyar la labor de los radiólogos en la detección rápida de patrones asociados a la enfermedad.

El problema central que aborda este proyecto es el diseño de un sistema de apoyo al diagnóstico basado en radiografías de tórax y técnicas de aprendizaje profundo, que permita no solo la clasificación automática de las imágenes, sino también la visualización clara y accesible de los resultados a través de un dashboard interactivo.

## Pregunta de negocio

El proyecto parte de la siguiente pregunta central:

_¿Es posible utilizar algoritmos de inteligencia artificial entrenados con radiografías de tórax para apoyar el diagnóstico diferencial entre pacientes sanos, con neumonía y con COVID-19, a través de una plataforma accesible?_

Esta pregunta se conecta con una necesidad práctica observada durante la pandemia: la dificultad de contar con herramientas rápidas y confiables que complementen el diagnóstico clínico tradicional.



<!-- Start of picture text -->
Universidad de<br>los Andes<br>Colombia<br><!-- End of picture text -->



<!-- Start of picture text -->
°<br>° °<br>e<br><!-- End of picture text -->

## Alcance del Proyecto

Con fines estrictamente académicos y de investigación, y tiene el siguiente alcance:

##### 1. **Datos**

- Uso del _COVID-19 Radiography Database_ disponible en Kaggle.

- Las categorías a trabajar serán: COVID-19, neumonía y normal

- No se realizará recolección de datos primarios ni intervención en pacientes.

##### 2. **Modelo**

- Entrenamiento y validación de modelos de clasificación de imágenes

- Evaluación con métricas estándar (precisión, recall, F1-score, AUC).

##### 3. **Prototipo Tecnológico**

- Desarrollo de un dashboard en la nube (prototipo en Figma y despliegue básico) que permita:

   - Subir una radiografía.

   - Ingresar datos básicos de usuario

   - Obtener una salida automática del diagnóstico: COVID-19, neumonía o sano, con probabilidades asociadas.

   - Visualizar, de manera opcional, una máscara/heatmap que resalte zonas afectadas en el pulmón.

##### 4. **Limitaciones**

- El sistema no es un producto clínico certificado, sino un prototipo con fines de aprendizaje.

- No sustituye la evaluación de un profesional de la salud.

- El Dataset usado proviene de fuentes públicas y puede no representar toda la variabilidad clínica real.

##### 5. **Resultados esperados**

- Validar la viabilidad de un modelo de clasificación automática de radiografías.

- Entregar un prototipo funcional de dashboard que sirva como demostración académica de integración entre IA y visualización de resultados médicos.



<!-- Start of picture text -->
Universidad de<br>los Andes<br>Colombia<br><!-- End of picture text -->



<!-- Start of picture text -->
°<br>° °<br>e<br><!-- End of picture text -->

## Descripción de conjuntos de datos

_Rahman, T., Chowdhury, M. E. H., Khandakar, A., Islam, K. R., Islam, K. F., Mahbub, Z. B., ... & Kashem, S. (2021). COVID19 radiography database. arXiv preprint arXiv:2105.10971._

Para el desarrollo de este proyecto se utilizará el COVID-19 Radiography Database (Rahman et al., 2021), un conjunto de datos de acceso público disponible en Kaggle

<u>COVID-19 Radiography Database | Kaggle), y almacenado inicialmente dentro del repositorio del</u> proyecto

<u>(https://github.com/danilo0327/COVID-19-Patient-Classification-from-Chest-X-rays-Using-PublicData/tree/main/data/raw</u>

El conjunto contiene aproximadamente 21,000 imágenes de rayos X de tórax clasificadas en las siguientes categorías:

- COVID-19: ~3,616 imágenes.

- Neumonía viral: ~1,345 imágenes.

- Neumonía bacteriana: ~6,012 imágenes.

- Sanos (Normal): ~10,192 imágenes.

Además, el dataset incluye un subconjunto de máscaras segmentadas correspondientes a las imágenes de COVID-19, lo cual resulta útil para tareas de localización de opacidades pulmonares y para la creación de sistemas de apoyo al diagnóstico basados en segmentación.

A partir de este conjunto solo se tomaron 100 imágenes de cada categoría para el entrenamiento y evaluación del modelo, sin embargo, es posible que la cantidad de imágenes se aumente a medida que se realicen pruebas y evalúen los resultados

### Creación del Dataset

Dentro del repositorio del proyecto se puede encontrar el script  que nos permite construir el dataset con el que se diseñará el modelo (https://github.com/danilo0327/COVID-19-Patient-Classification-from- <u>Chest-X-rays-Using-Public-Data/blob/main/scripts/create_csv.py).</u>



<!-- Start of picture text -->
| Universidad de<br>los AndesColombia<br><!-- End of picture text -->



<!-- Start of picture text -->
iG<br><!-- End of picture text -->

Es importante estructurar la data para que sea usada en el modelo, porque solo con imágenes crudas no es posible, para esto lo que se hizo fue crear un dataset con dos columnas **“img_path”** , la cual contiene la ruta donde esta cargada la imagen dentro del repositorio (o carpeta raiz) del proyecto, y la columna **“label”** , que contiene la etiqueta para la imagen (COVID, Lung_Opacity, Viral Pneumonia, Normal).



<!-- Start of picture text -->
A] img_path ++ §label<br>Missing: 0(0%) Missing: 00%)<br>Distinct 400 (100%) Distinct: 40%)<br>400 covLung. Opacity 25%25%<br>Distinct values OtherNormal 25%25%<br>0 data\raw\COVID\images\COVID-1.pr COVID<br>1 data\raw\COVID\images\COVID-105 COVID<br>2. datalvaw\COVID\images\COVID-100 COvID<br>3. datalvanCOVID\images\COVID-100 cOvID<br>4. data\raw\COVID\images\COVID-100 CovID<br>5. datalvaw\COVID\images\COVID-100 Covi<br>6 data\raw\COVID\images\COVID-100 COVID<br>7 data\vaw\COVID\images\COVID-100 COvID<br>8 datalvanCOVID\images\COVID-100 COvID<br>9 data\raw\COVID\images\COVID-100 COVID<br>10. datalvanCOVID\images\COVID-100 cOvID<br>11 data\raw\COVID\images\COVID-100 COVID<br>12. datalvawCOVID\images\COVID-100 COVID<br>13. datalvamCOVID\images\COVID-101 COVID<br>14  data\raw\COVID\images\COVID-101 COVID<br>15 datalvanCOVID\images\COVID-101 COvID<br>16 datalvan\COVID\images\COVID-101 COVID<br>17 _data\raw\COVID\images\COVID-101 COVID.<br><!-- End of picture text -->

Dataset creado con las columnas img_path y label

## Exploración inicial de los datos (EDA)

Como se mencionó previamente, el dataset utilizado cuenta con una base de aproximadamente 21,000 imágenes en formato Portable Network Graphics (PNG) con una resolución de 299×299 píxeles. Cada imagen tiene un tamaño que oscila entre 27 KB y 42 KB. Las imágenes se clasifican en cuatro categorías: COVID-19, Lung Opacity (opacidad pulmonar), Normal y Neumonía viral.

Para facilitar el procesamiento y manipulación de los datos, se balanceó el dataset seleccionando 100 imágenes por cada clase, tal como se puede observar en la gráfica a continuación.



<!-- Start of picture text -->
: :<br>Universidad de<br>los Andes<br>Colombia<br><!-- End of picture text -->



<!-- Start of picture text -->
e<br>° °<br>e<br><!-- End of picture text -->



<!-- Start of picture text -->
Balance de clases<br>100<br>80<br>20<br>°<br>2 2 3 2<br>clases<br><!-- End of picture text -->

Las imágenes radiográficas del tórax presentan buena nitidez general, permitiendo una clara diferenciación visual entre las regiones afectadas por patologías y el tejido pulmonar sano a través de contrastes bien definidos. El nivel de ruido en las imágenes es mínimo, lo que facilita la identificación de estructuras anatómicas y anomalías. Sin embargo, se observa que algunas radiografías presentan ligeras inclinaciones o desalineaciones debido al movimiento del paciente durante la adquisición de la imagen, lo cual puede representar un desafío para el análisis con las herramientas automatizadas.

Así mismo se muestra a continuación ejemplos para cada una de las categorías:



<!-- Start of picture text -->
Ejemplos de COVID<br>_ =]<br>| . +<br>; '<br><!-- End of picture text -->



<!-- Start of picture text -->
Ejemplos de Lung_Opacity<br>-— 4 .<br>er ?<br><!-- End of picture text -->



<!-- Start of picture text -->
Universidad de<br>los Andes<br>Colombia<br><!-- End of picture text -->



<!-- Start of picture text -->
°<br>° °<br>e<br><!-- End of picture text -->



<!-- Start of picture text -->
Ejemplos de Normal<br><!-- End of picture text -->



<!-- Start of picture text -->
Ejemplos de Viral Pneumonia<br><!-- End of picture text -->

## Maqueta del prototipo

Con el objetivo de materializar la propuesta de solución, se diseñó una maqueta de dashboard en Figma que representa la interacción principal entre el usuario y el sistema. La idea central es ofrecer una interfaz sencilla, intuitiva y de fácil interpretación tanto para médicos especialistas como para personal de apoyo.

El prototipo incluye los siguientes elementos clave:

- Título del sistema: Ubicado en la parte superior, identifica la herramienta como un apoyo diagnóstico para imágenes radiográficas.

- Sección de carga de imagen: Permite al usuario subir una radiografía de tórax en formato digital (JPG, PNG, DICOM).

- Datos del usuario/paciente: Un espacio para ingresar información básica como ID del paciente.

- Salida del modelo:

   - Un panel con el diagnóstico probabilístico (porcentaje de neumonía, COVID-19 o sano).

   - Una máscara segmentada que resalta en la radiografía las áreas afectadas, ofreciendo un nivel adicional de interpretabilidad.

- Botón de exportación: Para descargar el reporte con los resultados obtenidos.

La siguiente figura muestra el prototipo desarrollado:



<!-- Start of picture text -->
. :<br>Universidad de<br>los Andes<br>Colombia<br><!-- End of picture text -->



<!-- Start of picture text -->
e<br>° °<br>e<br><!-- End of picture text -->



<!-- Start of picture text -->
COVID-19 Radiography<br>Classifier<br>plone yourtung redlogepty User Details<br>Diagnosis<br>F COVID-19<br>92%<br>, Normal 2%<br><!-- End of picture text -->

## Repositorios del código y de los datos

Con el propósito de manejar los avances y versiones del proyecto relacionados al código del modelo, y de la herramienta que posteriormente será desplegada en la nube, y también los datos que serán utilizados, se creó un repositorio en GitHub y en DVC. A continuación, se presenta la configuración y el procedimiento realizado para agregar el dataset (archivo .csv) al repositorio DVC y como se incluyeron a GitHub.

#### **Creación de instancia EC2**

Dentro de la consola de EC2 de AWS se lanzó la instancia “micro_maia” con las siguientes caracteristicas:

- **<mark>Amazon Machine Image (AMI):</mark>** <mark>Ubuntu Server 24.04 LTS (HVM), SSD Volume Type.</mark>

- **<mark>Tipo de instancia:</mark>** <mark>t3.micro.</mark>

- **<mark>Key Par:</mark>** <mark>maia_key.pem</mark>

- **<mark>Almacenamiento:</mark>** <mark>10GB</mark>



<!-- Start of picture text -->
| Jios And de<br>Colombia<br><!-- End of picture text -->





<!-- Start of picture text -->
i-01a07476fb3c55838 (micro_maia)<br>Details Status and alarms Monitoring Security Networking Storage Tags<br>¥ Instance summary info<br>Instance 1D Public IPv4 address<br>TE i-01207476tb3c55838 TE 54.198.160.9| open address [2<br>IPv6 address Instance state<br>- @ Running<br>Hostname type Private IP DNS name (IPv4 only)<br>IP name: ip-172-31-47-125.ec2.internal 1B ip-172-31-47-125.ec2.intemal<br>IPvaAnswer(A) private resource DNS name Instancemicro type<br>Auto-assigned IP address vec iD<br>ID 54.198.160.9 [Public IP] ID vpc-0d9d1 6208343965 [3<br>1AM Role Subnet10<br>- IEy subnet-0994676776e82206 [2<br>impsve Instance ARN<br>Required IE} arnaws-ec2-us-east-1:155172019688:instance/i-01a07476fb3c55838<br><!-- End of picture text -->

#### **Inicialización de entorno virtual e instalación dependencias DVC**

Para poder realizar el almacenamiento remoto de los datos se seleccionó el servicio S3 de AWS, el cual antes de inicializarlo se inicializó el entorno virtual para poder instalar las dependencias DVC para S3 en la máquina virtual.



<!-- Start of picture text -->
:~$ python3 -m venv /home/ubuntu/env—dvc<br>:~$ source env-dvc/bin/activate<br>Cenv-dvc) :~$ pip install "dvc[s3]"|<br><!-- End of picture text -->

#### **Inicialización del repositorio Git y DVC en la carpeta del proyecto de la máquina virtual**

Para tener de forma organizada el dataset en la máquina virtual se creó una carpeta (llamada dvc-proj) donde se inicializó el repositorio Git y DVC.



<!-- Start of picture text -->
Cenv—dvc) :~$ mkdir dvc—proj<br>Cenv-dve) :~$ cd dve-proj<br>Cenv-dvc) 3 $ git init<br>Initialized empty Git repository in /home/ubuntu/dvc-proj/.git/<br>Cenv—dvc) 5 $ git branch —m main<br>Cenv—dvc) 3 $ dvc init<br>Initialized DVC repository.<br><!-- End of picture text -->



<!-- Start of picture text -->
| Universidad de<br>Colombia<br><!-- End of picture text -->





<!-- Start of picture text -->
Cenv-dvc) : Pp $ git status<br>(On branch main<br>No commits yet<br>Changes to be committed:<br>(use "git rm —cached <file>..." to unstage)<br><!-- End of picture text -->

Archivos que se crean al inicializar DVC

**Creación de subcarpeta “data” donde se añade el dataset “dataset.csv” (creado y cargado previamente al repositorio del proyecto)**

Creamos una subcarpeta donde se almacena el dataset con el que se va a trabajar.



<!-- Start of picture text -->
(env-dve) F $ mkdir -p data && curl https: //github.com/danilo9327/COVID-19-Patient-Class<br>ification—from-Chest-X-rays-Using-Public-Data/blob/main/data/dataframe/dataset.csv -o data/xray_images.csv<br>% Total % Received % Xferd Average Speed Time Time Time Current<br>Dload Upload Total Spent Left Speed<br><!-- End of picture text -->

#### **Agregar dataset (con el nuevo nombre xray_images.csv) en repositorio DVC**

Se agrega el nuevo archivo .csv en el repositorio DVC como respaldo al dataset que ya se había creado en Git.



<!-- Start of picture text -->
Cenv-dvc) : | i$ ls data<br>xray_images.csv xray_images.csv.dvc<br><!-- End of picture text -->

#### **Inicializar repositorio DVC para cargar datos a GitHub**

Se configuró el repositorio remoto Git  del proyecto (https://github.com/danilo0327/COVID-19-Patient- <u>Classification-from-Chest-X-rays-Using-Public-Data) dentro de la terminal de la maquina virtual para agregar</u> los datos con extensión .dvc al repositorio de GitHub.



<!-- Start of picture text -->
| Jios And de<br>Colombia<br><!-- End of picture text -->





<!-- Start of picture text -->
Cenv-dve) $ git push origin main<br>Username for 'https://github.com': danilo0327<br>Password for ‘https: //danilo0327@github.com':<br>Enumerating objects: 13, done.<br>Counting objects: 106% (13/13), done.<br>Delta compression using up to 2 threads<br>Compressing objects: 100% (8/8), done.<br>Writing objects: 100% (11/11), 1.17 KiB | 1.17 MiB/s, done<br>Total 11 (delta ®), reused 1 (delta 0), pack-reused 0<br>To https: //github. com/danilo®327/COVID-19-Patient-Classification—from-Chest-X-rays-Using-Public-Data.git<br><!-- End of picture text -->

#### **Conexión con S3**

Se establece la conexión con S3 (s3://xray-proj-dvcstore)



<!-- Start of picture text -->
(Cenv-dve) E $ dvc remote add -d aws-remote s3://xray-proj-dvcstore<br>Setting 'aws-remote' as a default remote<br>(env-dve) B r0j$ |<br><!-- End of picture text -->

Luego se puede ver el bucket en la consola de AWS y los datos dentro de el bucket.



<!-- Start of picture text -->
General purpose buckets QU) Directory buckets<br>General purpose buckets (1) inio © Create bucket<br>Buckets are containers for data stored in S3.<br>QF ; 1 cod<br>Name & | AWS Region v | Creation date v<br>oj-dvestor US East (N. Virginia) us-east-1 August22, 2025, 18:32:38 (UTC-05:00)<br><!-- End of picture text -->



<!-- Start of picture text -->
Objects (1 © Cratos+) Ceenetoner) QE<br>a +> @<br>8 post 2, 2085, 185910 UTC-0500 950 Son<br><!-- End of picture text -->

#### **Archivos del repositorio**

Después de conectar S3 y hacerle push a los archivos agregados, finalmente se tienen todos los archivos cargados al repositorio.



<!-- Start of picture text -->
| Jios And de<br>Colombia<br><!-- End of picture text -->





<!-- Start of picture text -->
Q COVID-19-Patient-Classification-from-Chest-X-rays-Using-Public-Data Pin Watch 0<br>man Pt ° + adanie - (eee<br>@ vountu © 7 commits<br>B ave<br>& data<br>®& scripts<br><!-- End of picture text -->

## Colaboradores y tareas específicas

En este primer avance del proyecto las aportaciones del equipo se clasificaron de la siguiente manera:

- Definición de pregunta de negocio (Todos)

- Recolección de datos a utilizar en el proyecto (Erick Pérez)

- Redacción de la problemática y contexto (Maria Isabel Eraso)

- Redacción de pregunta de negocio y alcance del proyecto (Maria Isabel Eraso)

- Diseño del prototipo de la aplicación (Maria Isabel Eraso y Juan Luna)

- Descripción y Exploración de los datos a emplear (Danilo Duarte y Erick Pérez)

- Creación de repositorio GitHub y DVC (Danilo Duarte)

## Referencias

_1. Rahman, T., Chowdhury, M. E. H., Khandakar, A., Islam, K. R., Islam, K. F., Mahbub, Z. B., ... & Kashem, S. (2021). COVID-19 radiography database. arXiv preprint arXiv:2105.10971._

_2. Chowdhury, M.E.H., Rahman, T., Khandakar, A., et al. (2020). Can AI help in screening Viral and COVID-19 pneumonia? arXiv:2003.13145._

_3. Rahman, T., Chowdhury, M.E.H., Khandakar, A., et al. (2020). Exploring the effect of image enhancement techniques on COVID-19 detection using chest X-ray images. Computers in Biology and Medicine, 132, 104319._
