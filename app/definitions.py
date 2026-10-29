# 25 descriptors, taken from the methodology's Matriz de Análisis Cualitativo.
CATEGORIES = [
    ('edad','Edad'),
    ('estado_civil','Estado civil'),
    ('complexion','Complexión física'),
    ('discapacidad','Referencias a discapacidad'),
    ('vestimenta','Vestimenta / arreglo personal'),
    ('apariencia','Apariencia física / valoración'),
    ('trato','Trato / valoración de candidatura'),
    ('comportamiento_sexual','Comportamientos sexuales'),
    ('maternidad','Roles reproductivos / maternidad'),
    ('dependencia','Roles de dependencia / sumisión'),
    ('exclusion_publica','Negativa de participación pública'),
    ('racismo_clasismo','Prejuicios racistas / clasistas'),
    ('culpabilizacion','Culpabilización / responsabilidad'),
    ('sexismo','Prejuicios sexistas / discriminatorios'),
    ('homofobia','Prejuicios homofóbicos'),
    ('invisibilizacion','Invisibilización'),
    ('cosificacion','Cosificación'),
    ('lenguaje','Lenguaje incluyente / sexista'),
    ('femenino','Uso de femenino'),
    ('plural_femenino','Uso de plurales femeninos'),
    ('titulos','Lenguaje en títulos / encabezados'),
    ('palabras_clave','Palabras clave y su contexto'),
    ('perfil','Valoración del perfil de candidatura'),
    ('discurso','Estudio del discurso político'),
    ('derechos','Rol político de mujeres y derechos'),
]
CATEGORY_IDS = {x[0] for x in CATEGORIES}
STAGES = [('precampana','Precampaña'),('campana','Campaña'),('apoyo','Apoyo de la ciudadanía'),('prueba','Prueba metodológica')]
MEDIA = [('radio','Radio'),('television','Televisión'),('digital','Digital / referencia')]
GENRES = [('nota','Nota informativa'),('entrevista','Entrevista'),('debate','Debate'),('reportaje','Reportaje'),('opinion','Opinión y análisis'),('otro','Otro'),('sin_clasificar','Sin clasificar')]
TOPICS = [('seguridad','Seguridad pública'),('economia','Economía y trabajo'),('educacion','Educación'),('participacion','Participación política'),('derechos','Derechos sociales y culturales'),('violencia_genero','Prevención de violencia contra mujeres'),('ciudadania','Ciudadanía'),('salud','Salud'),('otros','Otros')]

# Resúmenes operativos de las descripciones de la Matriz Cualitativa 2026-2027.
# Ejemplos de palabras clave no constituyen por sí mismos una valoración.
CATEGORY_GUIDANCE = {
 'edad':'Referencias a la edad, especialmente al presentar o caracterizar candidaturas.',
 'estado_civil':'Alusiones al estado civil de la persona y sus efectos en la presentación.',
 'complexion':'Referencias o juicios de valor sobre la complexión física.',
 'discapacidad':'Referencias a discapacidad de una persona, en su contexto.',
 'vestimenta':'Juicios sobre ropa, arreglo personal y cánones de belleza.',
 'apariencia':'Exaltación o desvaloración por imagen o apariencia física.',
 'trato':'Familiaridad, respeto y diferencias de trato de entrevistadores hacia candidaturas.',
 'comportamiento_sexual':'Menciones sobre conducta sexual, vida íntima o partes corporales íntimas.',
 'maternidad':'Imposición de roles reproductivos, maternidad y deber ser doméstico.',
 'dependencia':'Representación de las mujeres en dependencia, sumisión o subordinación.',
 'exclusion_publica':'Negativa o cuestionamiento de participación política de mujeres en lo público.',
 'racismo_clasismo':'Prejuicios ligados a origen, cultura, color de piel, clase o condición social.',
 'culpabilizacion':'Culpabilización de víctimas, minimización de agresiones o atribución impropia de responsabilidad.',
 'sexismo':'Estereotipos de inferioridad o supuesta incapacidad de las mujeres.',
 'homofobia':'Críticas y prejuicios hacia orientación o identidad sexual.',
 'invisibilizacion':'Ausencia de voz o representación de mujeres; la variante visual no puede inferirse del texto.',
 'cosificacion':'Trato de mujeres como objetos o adornos; casos basados en imagen necesitan revisión visual.',
 'lenguaje':'Presencia de lenguaje incluyente o expresiones sexistas/excluyentes en el contexto.',
 'femenino':'Uso de formas gramaticales femeninas en cargos, referencias y nombres.',
 'plural_femenino':'Uso o ausencia relevante de plurales gramaticales femeninos.',
 'titulos':'Lenguaje genérico o inclusivo en titulares y nombres de piezas o programas.',
 'palabras_clave':'Seguimiento de términos ligados a estereotipos o género, siempre en contexto.',
 'perfil':'Aspectos de perfil y candidatura que se destacan: profesión, experiencia, estado civil.',
 'discurso':'Valoración explícita del contenido de propuestas y discurso político.',
 'derechos':'Contenidos que cuestionan el ejercicio de derechos políticos de las mujeres por género.'
}
