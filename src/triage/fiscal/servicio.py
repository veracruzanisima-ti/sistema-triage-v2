"""Motor fiscal explicable: propone; una persona confirma o corrige."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from triage.comercial.servicio import asegurar_partida_cotizable
from triage.fiscal.modelos import (
    EstadoValidacionFiscal,
    FuenteValidacionFiscal,
    TratamientoIVA,
    ValidacionFiscalPartida,
)
from triage.historico.decisiones_servicio import listar_selecciones_actuales
from triage.historico.modelos import ObservacionPrecio
from triage.historico.servicio import ProductoHistorico, listar_productos_historico
from triage.usuarios.modelos import Usuario

VERSION_MOTOR_FISCAL = "fiscal-prototipo-2026-01"
FUENTE_LIVA_MEDICAMENTOS = "LIVA artículo 2-A, fracción I, inciso b"
URL_LIVA = "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf"
_DOS_DECIMALES = Decimal("0.01")


@dataclass(frozen=True)
class CapaEvidenciaFiscal:
    """Señal concreta que aporta puntos a un tratamiento candidato."""

    capa: str
    descripcion: str
    puntos: int
    fuente: str | None = None


@dataclass(frozen=True)
class CandidatoFiscal:
    tratamiento_iva: TratamientoIVA
    iva_porcentaje: Decimal | None
    puntos: int
    capas: tuple[CapaEvidenciaFiscal, ...]

    @property
    def etiqueta(self) -> str:
        if self.tratamiento_iva == TratamientoIVA.EXENTO:
            return "Exento"
        return f"IVA {self.iva_porcentaje:.2f}%"


@dataclass(frozen=True)
class SugerenciaFiscal:
    principal: CandidatoFiscal | None
    alternativas: tuple[CandidatoFiscal, ...]
    nivel_confianza: str
    hay_conflicto: bool
    version_motor: str = VERSION_MOTOR_FISCAL


@dataclass(frozen=True)
class ValidacionFiscalActual:
    tratamiento_iva: TratamientoIVA
    iva_porcentaje: Decimal | None
    fuente_decision: str
    observacion: str | None
    validada_por_nombre: str | None
    creada_en: datetime

    @property
    def etiqueta(self) -> str:
        if self.tratamiento_iva == TratamientoIVA.EXENTO:
            return "Exento"
        return f"IVA {self.iva_porcentaje:.2f}%"


@dataclass(frozen=True)
class BorradorCalculoFiscal:
    precio_unitario_sin_iva: Decimal
    subtotal: Decimal
    iva: Decimal
    total: Decimal
    tratamiento_iva: TratamientoIVA
    iva_porcentaje: Decimal | None
    validado: bool
    origen_precio: str


def _tasa_normalizada(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


def _clave_candidato(
    tratamiento: TratamientoIVA,
    tasa: Decimal | None,
) -> tuple[str, str | None]:
    return tratamiento.value, str(_tasa_normalizada(tasa)) if tasa is not None else None


def _validaciones_vigentes_por_partida(
    sesion: Session,
) -> dict[tuple[str, str], ValidacionFiscalPartida]:
    """Toma el último evento aun si cambió identidad o retiró una validación."""

    ultimas: dict[tuple[str, str], ValidacionFiscalPartida] = {}
    for evento in sesion.scalars(
        select(ValidacionFiscalPartida).order_by(
            ValidacionFiscalPartida.creada_en.desc(),
            ValidacionFiscalPartida.id.desc(),
        )
    ):
        if evento.partida_documento_id:
            ultimas.setdefault(
                (evento.cotizacion_id, evento.partida_documento_id),
                evento,
            )
    return ultimas


def _validacion_historica(
    sesion: Session,
    *,
    clave_producto: str,
    cotizacion_id: str,
    partida_id: str,
) -> ValidacionFiscalPartida | None:
    candidatas = [
        evento
        for llave, evento in _validaciones_vigentes_por_partida(sesion).items()
        if llave != (cotizacion_id, partida_id)
        and evento.clave_producto == clave_producto
        and evento.estado == EstadoValidacionFiscal.VALIDADA.value
    ]
    return max(candidatas, key=lambda evento: (evento.creada_en, evento.id), default=None)


def _tiene_evidencia_cofepris(producto: ProductoHistorico) -> dict[str, object] | None:
    for observacion in producto.observaciones:
        evidencia = observacion.evidencia_identidad
        if not isinstance(evidencia, dict):
            continue
        if evidencia.get("fuente") == "COFEPRIS" and evidencia.get("estado") == "VIGENTE":
            return evidencia
    return None


def construir_sugerencia_fiscal(
    sesion: Session,
    *,
    cotizacion_id: str,
    producto: ProductoHistorico,
    referencia: ObservacionPrecio | None,
) -> SugerenciaFiscal:
    """Combina señales independientes sin convertirlas en una decisión automática."""

    capas_por_candidato: dict[tuple[str, str | None], list[CapaEvidenciaFiscal]] = {}
    valores: dict[tuple[str, str | None], tuple[TratamientoIVA, Decimal | None]] = {}

    def agregar(
        tratamiento: TratamientoIVA,
        tasa: Decimal | None,
        capa: CapaEvidenciaFiscal,
    ) -> None:
        tasa = _tasa_normalizada(tasa) if tasa is not None else None
        clave = _clave_candidato(tratamiento, tasa)
        valores[clave] = tratamiento, tasa
        capas_por_candidato.setdefault(clave, []).append(capa)

    previa = _validacion_historica(
        sesion,
        clave_producto=producto.clave_producto,
        cotizacion_id=cotizacion_id,
        partida_id=producto.partida.id,
    )
    if previa and previa.tratamiento_iva:
        agregar(
            TratamientoIVA(previa.tratamiento_iva),
            previa.iva_porcentaje,
            CapaEvidenciaFiscal(
                capa="validacion_humana_previa",
                descripcion="Validación humana anterior del mismo producto exacto.",
                puntos=100,
                fuente=f"evento:{previa.id}",
            ),
        )

    proveedores_vistos: set[str] = set()
    if referencia and referencia.iva_porcentaje is not None:
        agregar(
            TratamientoIVA.TASA,
            referencia.iva_porcentaje,
            CapaEvidenciaFiscal(
                capa="referencia_estable",
                descripcion=f"La referencia estable de {referencia.proveedor} reporta esta tasa.",
                puntos=40,
                fuente=referencia.fuente,
            ),
        )
        proveedores_vistos.add(referencia.proveedor.casefold())

    proveedores_agregados = 0
    for observacion in producto.observaciones:
        if observacion.iva_porcentaje is None:
            continue
        proveedor = observacion.proveedor.casefold()
        if proveedor in proveedores_vistos:
            continue
        proveedores_vistos.add(proveedor)
        agregar(
            TratamientoIVA.TASA,
            observacion.iva_porcentaje,
            CapaEvidenciaFiscal(
                capa="proveedor_historico_independiente",
                descripcion=(
                    f"La observación más reciente de {observacion.proveedor} "
                    "reporta esta tasa."
                ),
                puntos=20,
                fuente=observacion.fuente,
            ),
        )
        proveedores_agregados += 1
        if proveedores_agregados == 2:
            break

    evidencia_cofepris = _tiene_evidencia_cofepris(producto)
    if evidencia_cofepris:
        registro = str(evidencia_cofepris.get("numero_registro") or "sin número")
        agregar(
            TratamientoIVA.TASA,
            Decimal("0"),
            CapaEvidenciaFiscal(
                capa="identidad_cofepris_y_regla_legal",
                descripcion=(
                    f"Registro COFEPRIS vigente {registro}; es una señal para revisar 0%, "
                    "no una determinación fiscal."
                ),
                puntos=25,
                fuente=f"{FUENTE_LIVA_MEDICAMENTOS} · {URL_LIVA}",
            ),
        )

    candidatos = []
    for clave, capas in capas_por_candidato.items():
        tratamiento, tasa = valores[clave]
        candidatos.append(
            CandidatoFiscal(
                tratamiento_iva=tratamiento,
                iva_porcentaje=tasa,
                puntos=min(sum(capa.puntos for capa in capas), 100),
                capas=tuple(capas),
            )
        )
    candidatos.sort(
        key=lambda candidato: (
            -candidato.puntos,
            candidato.tratamiento_iva.value,
            candidato.iva_porcentaje or Decimal("0"),
        )
    )
    hay_conflicto = len(candidatos) > 1
    principal = candidatos[0] if candidatos else None
    if principal is None:
        nivel = "SIN_EVIDENCIA"
    elif hay_conflicto:
        nivel = "CONFLICTO"
    elif principal.puntos >= 80:
        nivel = "ALTA"
    elif principal.puntos >= 55:
        nivel = "MEDIA"
    else:
        nivel = "BAJA"
    return SugerenciaFiscal(
        principal=principal,
        alternativas=tuple(candidatos),
        nivel_confianza=nivel,
        hay_conflicto=hay_conflicto,
    )


def listar_validaciones_fiscales_actuales(
    sesion: Session,
    *,
    cotizacion_id: str,
    productos: list[ProductoHistorico],
) -> dict[str, ValidacionFiscalActual]:
    """Sólo reutiliza el último evento si conserva la identidad exacta actual."""

    por_partida = {
        partida_id: evento
        for (evento_cotizacion, partida_id), evento in _validaciones_vigentes_por_partida(
            sesion
        ).items()
        if evento_cotizacion == cotizacion_id
    }
    vigentes = {
        producto.partida.id: por_partida[producto.partida.id]
        for producto in productos
        if producto.partida.id in por_partida
        and por_partida[producto.partida.id].clave_producto == producto.clave_producto
        and por_partida[producto.partida.id].estado == EstadoValidacionFiscal.VALIDADA.value
        and por_partida[producto.partida.id].tratamiento_iva
    }
    usuarios_ids = {evento.validada_por_usuario_id for evento in vigentes.values()}
    nombres = (
        {
            usuario.id: usuario.nombre
            for usuario in sesion.scalars(select(Usuario).where(Usuario.id.in_(usuarios_ids)))
        }
        if usuarios_ids
        else {}
    )
    return {
        partida_id: ValidacionFiscalActual(
            tratamiento_iva=TratamientoIVA(evento.tratamiento_iva),
            iva_porcentaje=evento.iva_porcentaje,
            fuente_decision=evento.fuente_decision,
            observacion=evento.observacion,
            validada_por_nombre=nombres.get(evento.validada_por_usuario_id),
            creada_en=evento.creada_en,
        )
        for partida_id, evento in vigentes.items()
    }


def _contexto_partida(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
) -> tuple[ProductoHistorico, ObservacionPrecio | None]:
    producto = next(
        (
            candidato
            for candidato in listar_productos_historico(sesion, cotizacion_id)
            if candidato.partida.id == partida_id
        ),
        None,
    )
    if producto is None:
        raise ValueError("la partida ya no está preparada o dejó de ser elegible")
    seleccion = listar_selecciones_actuales(sesion, cotizacion_id).get(partida_id)
    referencia = (
        sesion.get(ObservacionPrecio, seleccion.referencia_estable_id)
        if seleccion and seleccion.referencia_estable_id
        else None
    )
    return producto, referencia


def _snapshot_sugerencia(sugerencia: SugerenciaFiscal) -> dict[str, object]:
    return {
        "version_motor": sugerencia.version_motor,
        "nivel_confianza": sugerencia.nivel_confianza,
        "hay_conflicto": sugerencia.hay_conflicto,
        "candidatos": [
            {
                "tratamiento_iva": candidato.tratamiento_iva.value,
                "iva_porcentaje": (
                    str(candidato.iva_porcentaje)
                    if candidato.iva_porcentaje is not None
                    else None
                ),
                "puntos": candidato.puntos,
                "capas": [
                    {
                        "capa": capa.capa,
                        "descripcion": capa.descripcion,
                        "puntos": capa.puntos,
                        "fuente": capa.fuente,
                    }
                    for capa in candidato.capas
                ],
            }
            for candidato in sugerencia.alternativas
        ],
    }


def registrar_validacion_fiscal(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
    tratamiento_iva: TratamientoIVA,
    iva_porcentaje: Decimal | None,
    observacion: str | None,
) -> ValidacionFiscalPartida:
    """Guarda la decisión humana y la propuesta exacta que estaba visible."""

    producto, referencia = _contexto_partida(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    asegurar_partida_cotizable(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    observacion_limpia = " ".join((observacion or "").split()) or None
    if observacion_limpia and len(observacion_limpia) > 500:
        raise ValueError("la observación no puede exceder 500 caracteres")
    if tratamiento_iva == TratamientoIVA.TASA:
        if iva_porcentaje is None:
            raise ValueError("indica el porcentaje para el tratamiento con tasa")
        tasa = _tasa_normalizada(iva_porcentaje)
        if not Decimal("0") <= tasa <= Decimal("100"):
            raise ValueError("el porcentaje de IVA debe estar entre 0 y 100")
    else:
        tasa = None

    sugerencia = construir_sugerencia_fiscal(
        sesion,
        cotizacion_id=cotizacion_id,
        producto=producto,
        referencia=referencia,
    )
    principal = sugerencia.principal
    confirma = bool(
        principal
        and principal.tratamiento_iva == tratamiento_iva
        and principal.iva_porcentaje == tasa
    )
    if not confirma and not observacion_limpia:
        raise ValueError("explica la corrección fiscal para conservar su trazabilidad")

    evento = ValidacionFiscalPartida(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=producto.clave_producto,
        estado=EstadoValidacionFiscal.VALIDADA.value,
        tratamiento_iva=tratamiento_iva.value,
        iva_porcentaje=tasa,
        version_motor=VERSION_MOTOR_FISCAL,
        sugerencia_snapshot=_snapshot_sugerencia(sugerencia),
        observacion=observacion_limpia,
        fuente_decision=(
            FuenteValidacionFiscal.SUGERENCIA_CONFIRMADA.value
            if confirma
            else FuenteValidacionFiscal.CORRECCION_HUMANA.value
        ),
        validada_por_usuario_id=usuario_id,
    )
    sesion.add(evento)
    sesion.commit()
    sesion.refresh(evento)
    return evento


def retirar_validacion_fiscal(
    sesion: Session,
    *,
    cotizacion_id: str,
    partida_id: str,
    usuario_id: str,
) -> ValidacionFiscalPartida:
    """Revierte de forma auditable agregando un evento PENDIENTE."""

    producto, _ = _contexto_partida(
        sesion,
        cotizacion_id=cotizacion_id,
        partida_id=partida_id,
    )
    evento = ValidacionFiscalPartida(
        cotizacion_id=cotizacion_id,
        partida_documento_id=partida_id,
        clave_producto=producto.clave_producto,
        estado=EstadoValidacionFiscal.PENDIENTE.value,
        tratamiento_iva=None,
        iva_porcentaje=None,
        version_motor=VERSION_MOTOR_FISCAL,
        sugerencia_snapshot=None,
        observacion="Validación retirada mediante revisión humana",
        fuente_decision=FuenteValidacionFiscal.RETIRO_HUMANO.value,
        validada_por_usuario_id=usuario_id,
    )
    sesion.add(evento)
    sesion.commit()
    sesion.refresh(evento)
    return evento


def calcular_borrador_fiscal(
    *,
    producto: ProductoHistorico,
    referencia: ObservacionPrecio | None,
    sugerencia: SugerenciaFiscal,
    validacion: ValidacionFiscalActual | None,
) -> BorradorCalculoFiscal | None:
    """Calcula los rubros DIF sin afirmar que la referencia es precio final de venta."""

    cantidad = producto.partida.cantidad
    if referencia is None or cantidad is None or cantidad <= 0:
        return None
    candidato = validacion or sugerencia.principal
    if candidato is None:
        return None
    tratamiento = candidato.tratamiento_iva
    tasa = candidato.iva_porcentaje if tratamiento == TratamientoIVA.TASA else Decimal("0")
    if tasa is None:
        return None

    if referencia.precio_antes_iva is not None:
        unitario = Decimal(referencia.precio_antes_iva)
    elif referencia.precio_total is not None:
        divisor = Decimal("1") + Decimal(tasa) / Decimal("100")
        unitario = Decimal(referencia.precio_total) / divisor
    else:
        return None
    unitario = unitario.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)
    subtotal = (unitario * Decimal(cantidad)).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    iva = (subtotal * Decimal(tasa) / Decimal("100")).quantize(
        _DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )
    return BorradorCalculoFiscal(
        precio_unitario_sin_iva=unitario,
        subtotal=subtotal,
        iva=iva,
        total=(subtotal + iva).quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP),
        tratamiento_iva=tratamiento,
        iva_porcentaje=candidato.iva_porcentaje,
        validado=validacion is not None,
        origen_precio=f"Referencia estable provisional: {referencia.proveedor}",
    )
