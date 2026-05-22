from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SessionFormPayload(BaseModel):
    tema: Optional[str] = None
    titulo: Optional[str] = None
    docente: Optional[str] = None
    fecha: Optional[str] = None
    grado: Optional[str] = None
    seccion: Optional[str] = None
    competenciasSeleccionadas: List[str] = Field(default_factory=list)
    capacidades: List[str] = Field(default_factory=list)
    ciclo: Optional[str] = None
    contexto: Optional[str] = None
    duracion: Optional[str] = None
    horasClase: Optional[int] = None
    enfoqueTransversal: Optional[str] = None
    competenciaTransversal: Optional[str] = None
    materialesDisponibles: List[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    session_id: Optional[str] = None
    source: str = "frontend"
    data: Optional[SessionFormPayload] = None


class SessionRecord(BaseModel):
    session_id: str
    status: str
    source: str = "frontend"
    input_data: Optional[Dict[str, Any]] = None
    generated_data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SessionGenerateResponse(BaseModel):
    session_id: str
    status: str
    data: Dict[str, Any]


class DownloadResponse(BaseModel):
    session_id: str
    filename: str


class SecuenciaMetodologica(BaseModel):
    inicio: str
    desarrollo: str
    cierre: str


class CoreLessonPlan(BaseModel):
    tema: str
    ciclo: str
    contexto: str
    horasClase: int
    competenciasSeleccionadas: List[str]
    capacidades: List[str]
    materialesDisponibles: str
    actividades_previas: List[str]
    competenciaDescripcion: str
    desempenos: List[str]
    criteriosEvaluacion: str
    evidenciasAprendizaje: str
    propositoSesion: str
    secuenciaMetodologica: SecuenciaMetodologica
    distribucionHoras: str
    procesosDidacticos: List[str]
    actividadesContextualizadas: List[str]
    materialesDidacticosSugeridos: List[str]
    actitudes_observables: str


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


class RecursosAdicionales(BaseModel):
    fichasDeTrabajo: List[FichaTrabajo]
    problemasYEjercicios: List[ProblemaEjercicio]
    juegoDidactico: JuegoDidactico
    actividadDeActivacion: List[str]
    evaluacionFormativa: EvaluacionFormativa
    comunicadoParaPadres: str
    actividadesDiferenciadas: ActividadesDiferenciadas
