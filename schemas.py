from pydantic import BaseModel
from typing import List

class DatosGenerales(BaseModel):
    titulo: str
    docente: str
    fecha: str
    grado: str
    seccion: str

class SecuenciaMetodologica(BaseModel):
    inicio: str
    desarrollo: str
    cierre: str

class CoreLessonPlan(BaseModel):
    datosGenerales: DatosGenerales
    tema: str
    ciclo: str
    contexto: str
    horasClase: int
    competenciasSeleccionadas: List[str]
    capacidades: List[str]
    materialesDisponibles: str
    enfoqueTransversal: str
    competenciaTransversal: str
    competenciaDescripcion: str
    criteriosEvaluacion: str
    evidenciasAprendizaje: str
    propositoSesion: str
    secuenciaMetodologica: SecuenciaMetodologica
    distribucionHoras: str
    procesosDidacticos: List[str]
    actividadesContextualizadas: List[str]
    materialesDidacticosSugeridos: List[str]

class FichaTrabajo(BaseModel):
    titulo: str
    instrucciones: str
    ejercicios: List[str]

class ProblemaEjercicio(BaseModel):
    nivel: str
    enunciado: str
    respuesta_esperada: str

class JuegoDidactico(BaseModel):
    nombre: str
    materiales: List[str]
    instrucciones: List[str]

class EvaluacionFormativa(BaseModel):
    preguntas: List[str]
    respuestas: List[str]
    criterios: List[str]

class ActividadesDiferenciadas(BaseModel):
    refuerzo: List[str]
    consolidacion: List[str]
    profundizacion: List[str]

class InstrumentoEvaluacionGenerado(BaseModel):
    tipo_instrumento: str
    criterios_o_items: List[str]
    escalas_o_niveles: List[str]

class RecursosAdicionales(BaseModel):
    fichasDeTrabajo: List[FichaTrabajo]
    problemasYEjercicios: List[ProblemaEjercicio]
    juegoDidactico: JuegoDidactico
    actividadDeActivacion: List[str]
    evaluacionFormativa: EvaluacionFormativa
    comunicadoParaPadres: str
    actividadesDiferenciadas: ActividadesDiferenciadas
    instrumentoEvaluacionGenerado: InstrumentoEvaluacionGenerado
