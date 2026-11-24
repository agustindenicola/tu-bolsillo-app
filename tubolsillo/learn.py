"""Aprender: conceptos de finanzas personales explicados simple, ordenados por tema.

Tu Bolsillo informa y enseña conceptos generales. No recomienda productos ni dice en qué
invertir (recomendar inversiones está regulado por la CNV). Los ejemplos usan números
redondos para entender la idea; no son tasas reales ni promesas de rendimiento.
"""

TOPICS = [
    {"id": "ordenar", "name": "Ordenar tu plata", "icon": "🧾", "desc": "Saber en qué se te va y armar una base."},
    {"id": "inflacion", "name": "La inflación y tu plata", "icon": "📈", "desc": "Por qué la plata quieta pierde valor y cómo se mide."},
    {"id": "ahorrar", "name": "Dónde dejar tus ahorros", "icon": "🏦", "desc": "Opciones simples y de bajo riesgo para que tu plata trabaje."},
    {"id": "invertir", "name": "Invertir", "icon": "🌱", "desc": "Qué es, qué riesgos tiene y por dónde se empieza."},
    {"id": "cuidarte", "name": "Cuidarte", "icon": "🛡", "desc": "Descuentos, tarjetas y estafas: que no te pase."},
]

ARTICLES = [
    # ---------------------------------------------------------------- ordenar
    {"id": "presupuesto", "topic": "ordenar", "title": "Cómo armar un presupuesto que se pueda cumplir", "min": 4,
     "summary": "Separar lo necesario, lo que te gusta y lo que guardás, sin planillas imposibles.",
     "sections": [
         {"h": "Qué es", "p": [
             "Un presupuesto es simplemente decidir de antemano qué vas a hacer con la plata que entra, en lugar de mirar a fin de mes qué pasó.",
             "No hace falta anotar cada centavo. Alcanza con saber más o menos cuánto entra y en qué grandes grupos se va."]},
         {"h": "Una forma simple: tres partes", "p": [
             "Lo necesario: alquiler o expensas, comida, servicios, transporte, remedios.",
             "Lo que te gusta: salidas, delivery, ropa que no es imprescindible, suscripciones.",
             "Lo que guardás: ahorro para objetivos, para emergencias o para invertir.",
             "Una referencia común es 50% necesario, 30% gustos y 20% ahorro. Es solo un punto de partida: si hoy guardás 5%, ya es un comienzo."]},
         {"h": "El truco que más funciona", "p": [
             "Separá la parte del ahorro apenas cobrás, no lo que sobre a fin de mes. Lo que queda en la cuenta se termina gastando.",
             "Si podés, mandala a otra cuenta o billetera distinta de la que usás para pagar: lo que no se ve, no se gasta."]},
         {"h": "Cómo te ayuda Tu Bolsillo", "p": [
             "En Gastos ves cuánto se te va por rubro y con qué pagás. Cargá también lo que pagás en efectivo: es el gasto que más se escapa.",
             "Los descuentos que usás no son plata «de más» para gastar: si la sumás a tu parte de ahorro, tu presupuesto rinde más sin esfuerzo."]},
     ],
     "example": {"title": "Ejemplo con un ingreso de $ 800.000", "rows": [
         ["Necesario (50%)", "$ 400.000"], ["Gustos (30%)", "$ 240.000"], ["Ahorro (20%)", "$ 160.000"]],
         "note": "Si los necesarios te ocupan más, se achica la parte de gustos, no la de ahorro."}},
    {"id": "fondo-emergencia", "topic": "ordenar", "title": "Fondo de emergencia: tu colchón", "min": 3,
     "summary": "La plata para imprevistos, para no endeudarte cuando algo se rompe.",
     "sections": [
         {"h": "Qué es", "p": [
             "Es un ahorro separado solo para imprevistos: una reparación, un remedio caro, un mes sin trabajo.",
             "Sirve para no tener que pagar con la tarjeta en cuotas con interés o pedir un préstamo justo cuando estás complicado."]},
         {"h": "¿Cuánto conviene tener?", "p": [
             "Una referencia habitual es juntar entre 3 y 6 meses de tus gastos necesarios. Parece mucho: se arma de a poco, empezando por un mes.",
             "Si tu ingreso es variable (por ejemplo, trabajás por tu cuenta), conviene apuntar a la parte alta."]},
         {"h": "Dónde tenerlo", "p": [
             "Tiene que estar disponible rápido y sin riesgo de perder valor de golpe. Por eso se suele dejar en algo líquido, como una cuenta remunerada o un fondo money market.",
             "No es la plata para invertir en algo que sube y baja: el día que la necesitás, puede estar abajo."]},
     ],
     "example": {"title": "Si tus gastos necesarios son $ 400.000 por mes", "rows": [
         ["Primer objetivo (1 mes)", "$ 400.000"], ["Colchón básico (3 meses)", "$ 1.200.000"], ["Colchón amplio (6 meses)", "$ 2.400.000"]],
         "note": "Podés crearlo como objetivo en esta pantalla y ver cómo tu ahorro se acerca."}},
    {"id": "objetivos", "topic": "ordenar", "title": "Objetivos de ahorro que se cumplen", "min": 2,
     "summary": "Ponerle nombre, monto y fecha a lo que querés hace mucho más fácil llegar.",
     "sections": [
         {"h": "Por qué funcionan", "p": [
             "Ahorrar «por las dudas» cuesta. Ahorrar «para las vacaciones de enero» es más fácil, porque sabés para qué es cada peso.",
             "Un buen objetivo tiene tres cosas: qué es, cuánto cuesta y para cuándo lo querés."]},
         {"h": "Cómo calcular cuánto separar", "p": [
             "Dividí el monto por los meses que faltan. Si te da un número imposible, mové la fecha o achicá el objetivo: es mejor uno chico que se cumple que uno grande que se abandona.",
             "Mientras esperás, esa plata puede estar en algo que le gane algo a la inflación, como un plazo fijo o una cuenta remunerada."]},
     ],
     "example": {"title": "Vacaciones de $ 600.000 en 8 meses", "rows": [
         ["Por mes", "$ 75.000"], ["Si los descuentos te ahorran $ 10.000 por mes", "te quedan $ 65.000 por mes"]], "note": None}},

    # ---------------------------------------------------------------- inflación
    {"id": "inflacion", "topic": "inflacion", "title": "Por qué la plata quieta pierde valor", "min": 3,
     "summary": "Qué es la inflación y por qué guardar billetes en un cajón te hace perder.",
     "sections": [
         {"h": "Qué es la inflación", "p": [
             "Es la suba generalizada de los precios. Si la inflación de un mes fue 3%, en promedio las cosas cuestan 3% más que el mes anterior.",
             "En Argentina la mide el INDEC todos los meses con el índice de precios al consumidor (IPC)."]},
         {"h": "Qué le pasa a tu plata", "p": [
             "Los billetes no cambian, pero lo que podés comprar con ellos sí. Si tenés $ 100.000 quietos y los precios suben 3%, a fin de mes esos billetes compran lo que antes costaba unos $ 97.000.",
             "Esa pérdida no se ve en el saldo, pero se siente en el changuito."]},
         {"h": "Qué se puede hacer", "p": [
             "La idea es que la plata que no vas a usar enseguida genere un interés. Si el interés es mayor que la inflación, tu plata gana poder de compra; si es menor, pierde, pero menos que quieta.",
             "No hace falta mucha plata para empezar: las cuentas remuneradas y los fondos money market aceptan montos chicos."]},
         {"h": "Y el efectivo", "p": [
             "Pagar en efectivo no tiene nada de malo, pero el efectivo guardado no rinde nada, y además muchas veces te perdés descuentos que sí tienen las billeteras y tarjetas."]},
     ],
     "example": {"title": "$ 100.000 durante 12 meses con inflación de 3% mensual", "rows": [
         ["Quietos en un cajón", "compran lo que hoy vale ~$ 70.100"], ["Con un interés de 3% mensual reinvertido", "mantienen el poder de compra"]],
         "note": "Números redondos para entender la idea, no son datos reales."}},
    {"id": "tasa-real", "topic": "inflacion", "title": "Tasa real: ¿le estás ganando a la inflación?", "min": 3,
     "summary": "Comparar lo que te pagan con lo que suben los precios.",
     "sections": [
         {"h": "Qué es", "p": [
             "La tasa real es lo que ganás de verdad, descontando la inflación. Es la cuenta que importa, más que la tasa que anuncia el banco.",
             "Si te pagan 2,5% en el mes y la inflación fue 3%, tu tasa real fue negativa: perdiste un poco de poder de compra (aunque menos que con la plata quieta)."]},
         {"h": "Cómo se calcula", "p": [
             "Una cuenta rápida es restar: tasa del período menos inflación del período. La cuenta exacta es (1 + tasa) ÷ (1 + inflación) − 1.",
             "Siempre compará períodos iguales: tasa mensual con inflación mensual, anual con anual."]},
         {"h": "Para tener en cuenta", "p": [
             "La inflación de un mes se conoce después (el INDEC la publica a mediados del mes siguiente). Por eso, cuando elegís dónde dejar la plata, estás comparando con una inflación que todavía no sabés.",
             "Algunos instrumentos ajustan por inflación (por ejemplo, el plazo fijo UVA) para resolver justamente eso."]},
     ],
     "example": {"title": "Un mes con tasa de 2,5% e inflación de 3%", "rows": [
         ["Cuenta rápida", "2,5% − 3% = −0,5%"], ["Cuenta exacta", "1,025 ÷ 1,03 − 1 = −0,49%"]], "note": None}},
    {"id": "tna-tea", "topic": "inflacion", "title": "TNA, TEA e interés compuesto", "min": 4,
     "summary": "Qué significan las siglas de las tasas y por qué reinvertir los intereses hace la diferencia.",
     "sections": [
         {"h": "TNA: tasa nominal anual", "p": [
             "Es la tasa que se anuncia, expresada por año. Para saber cuánto te pagan en un plazo más corto se divide: una TNA de 30% equivale a 2,47% en 30 días (30% × 30 ÷ 365).",
             "La TNA no tiene en cuenta que podés reinvertir los intereses."]},
         {"h": "TEA: tasa efectiva anual", "p": [
             "Es lo que ganarías en un año si cada vez que cobrás intereses los volvés a invertir. Por eso la TEA es mayor que la TNA.",
             "Cuando compares opciones, mirá la misma tasa en las dos (TNA con TNA, o TEA con TEA)."]},
         {"h": "Interés compuesto", "p": [
             "Es justamente ganar intereses sobre los intereses anteriores. Al principio la diferencia es chica, pero con el tiempo crece como una bola de nieve.",
             "Por eso empezar temprano, aunque sea con poco, suele pesar más que empezar tarde con mucho."]},
     ],
     "example": {"title": "TNA de 30%", "rows": [
         ["En 30 días", "2,47%"], ["En un año, sin reinvertir (TNA)", "30%"], ["En un año, reinvirtiendo cada mes (TEA)", "≈ 34,5%"]],
         "note": "Ejemplo con números redondos, no es una tasa real."}},

    # ---------------------------------------------------------------- dónde dejar los ahorros
    {"id": "remunerada", "topic": "ahorrar", "title": "Cuenta remunerada", "min": 3,
     "summary": "Tu plata gana interés todos los días y la podés usar cuando quieras.",
     "sections": [
         {"h": "Qué es", "p": [
             "Es una cuenta (en un banco o en una billetera virtual) que te paga un interés diario por el saldo que tenés. Los intereses se suman a tu saldo y al día siguiente también generan interés.",
             "La plata está disponible siempre: podés pagar o transferir en cualquier momento."]},
         {"h": "Ventajas y límites", "p": [
             "Ventajas: no hay que hacer nada, no inmovilizás la plata y se puede empezar con montos muy chicos.",
             "Límites: suele pagar menos que un plazo fijo, la tasa puede cambiar de un día para otro y muchas veces remunera solo hasta cierto monto."]},
         {"h": "En qué fijarte", "p": [
             "La TNA que ofrece, si tiene un tope de saldo remunerado y si es una cuenta bancaria o un fondo de inversión «por detrás» (algunas billeteras invierten tu saldo en un fondo money market).",
             "Es una buena opción para el fondo de emergencia y para la plata que vas a usar en los próximos días o semanas."]},
     ],
     "example": None},
    {"id": "plazofijo", "topic": "ahorrar", "title": "Plazo fijo tradicional", "min": 4,
     "summary": "Dejás la plata un tiempo y te devuelven lo que pusiste más un interés acordado.",
     "sections": [
         {"h": "Cómo funciona", "p": [
             "Elegís un monto y un plazo (el mínimo habitual es 30 días). El banco te dice de antemano cuánto interés vas a cobrar. Al vencimiento, te devuelve todo junto.",
             "Mientras dura, esa plata no se puede usar."]},
         {"h": "Ventajas", "p": [
             "Sabés exactamente cuánto vas a cobrar: no sube ni baja en el camino.",
             "Los depósitos en bancos tienen una garantía de depósitos hasta cierto monto, que se actualiza cada tanto.",
             "Se arma en pocos minutos desde el home banking o la app del banco."]},
         {"h": "Límites", "p": [
             "Si la inflación termina siendo más alta que la tasa, perdés poder de compra.",
             "Si necesitás la plata antes, en general no la podés sacar. Por eso conviene no poner ahí el fondo de emergencia completo."]},
         {"h": "Renovar o no", "p": [
             "Al vencer, podés renovarlo con los intereses incluidos (así aprovechás el interés compuesto) o retirarlo. Muchos bancos permiten la renovación automática."]},
     ],
     "example": {"title": "$ 100.000 a 30 días con TNA de 30%", "rows": [
         ["Interés", "$ 100.000 × 30% × 30 ÷ 365 = $ 2.466"], ["Cobrás al vencimiento", "$ 102.466"]], "note": "Probalo con tus números en la calculadora de abajo."}},
    {"id": "plazofijo-uva", "topic": "ahorrar", "title": "Plazo fijo UVA (ajustado por inflación)", "min": 3,
     "summary": "Un plazo fijo que acompaña a la inflación, a cambio de un plazo más largo.",
     "sections": [
         {"h": "Qué es", "p": [
             "Es un plazo fijo cuyo capital se ajusta según la UVA, una unidad que sigue a la inflación. Además del ajuste, suele pagar un pequeño interés extra.",
             "Así, si la inflación sube, tu plata sube con ella."]},
         {"h": "Ventajas y límites", "p": [
             "Ventaja: te protege si la inflación termina siendo más alta de lo esperado.",
             "Límites: exige un plazo mínimo más largo que el tradicional, y si la inflación baja, puede rendir menos que un plazo fijo común.",
             "Algunos bancos ofrecen una versión que se puede cancelar antes, con una tasa más baja si la cortás."]},
         {"h": "Cuándo se elige", "p": [
             "Cuando no vas a necesitar esa plata por varios meses y preferís no preocuparte por cuánto va a ser la inflación."]},
     ],
     "example": None},
    {"id": "money-market", "topic": "ahorrar", "title": "Fondos money market", "min": 3,
     "summary": "Un fondo muy tranquilo, parecido a una cuenta remunerada, que se rescata en el día.",
     "sections": [
         {"h": "Qué es", "p": [
             "Es un fondo común de inversión que invierte en cosas de muy corto plazo y bajo riesgo, como depósitos y cauciones.",
             "Rinde todos los días y podés sacar la plata (rescatar) en el momento o en el día."]},
         {"h": "Diferencia con una cuenta remunerada", "p": [
             "En la práctica se usan parecido. La diferencia es que en un fondo no tenés un depósito en un banco: tenés cuotapartes de un fondo, cuyo valor sube de a poco cada día.",
             "No tiene la garantía de depósitos, pero por lo que invierte su riesgo es bajo."]},
         {"h": "Dónde se consigue", "p": [
             "En bancos, sociedades de bolsa y varias billeteras virtuales (muchas veces es lo que hay detrás de «tu saldo rinde»)."]},
     ],
     "example": None},

    # ---------------------------------------------------------------- invertir
    {"id": "riesgo", "topic": "invertir", "title": "Riesgo, plazo y diversificación", "min": 4,
     "summary": "Las tres ideas que conviene entender antes de invertir un peso.",
     "sections": [
         {"h": "Riesgo", "p": [
             "Riesgo es la posibilidad de que una inversión valga menos de lo esperado, al menos por un tiempo.",
             "En general, lo que puede rendir más también puede bajar más. No existe algo con mucho rendimiento y cero riesgo: si alguien te lo promete, desconfiá."]},
         {"h": "Plazo", "p": [
             "La pregunta clave es: ¿cuándo voy a necesitar esta plata? Lo que necesitás pronto conviene tenerlo en algo tranquilo. Lo que no vas a tocar en años puede bancarse subas y bajas.",
             "Muchas pérdidas pasan por tener que vender justo en un mal momento porque se necesitaba la plata."]},
         {"h": "Diversificación", "p": [
             "Es no poner todo en un mismo lugar. Si repartís entre varias inversiones distintas, que a una le vaya mal no te arruina.",
             "Los fondos comunes de inversión ya vienen diversificados: con poca plata tenés un pedacito de muchas cosas."]},
         {"h": "Tu perfil de inversor", "p": [
             "Cuando abrís una cuenta para invertir te hacen un cuestionario para saber cuánto riesgo aceptás. No es un examen: sirve para que te ofrezcan cosas acordes a vos."]},
     ],
     "example": None},
    {"id": "fci", "topic": "invertir", "title": "Fondos comunes de inversión", "min": 4,
     "summary": "Juntar tu plata con la de otras personas para que la invierta un equipo profesional.",
     "sections": [
         {"h": "Cómo funcionan", "p": [
             "Un fondo junta la plata de muchas personas y la invierte según reglas escritas en su reglamento. Vos comprás cuotapartes; si lo que tiene el fondo sube, tu cuotaparte vale más, y si baja, vale menos.",
             "Los administra una sociedad gerente y la plata la custodia otra entidad (un banco), regulados por la CNV."]},
         {"h": "Tipos", "p": [
             "Money market: muy tranquilos, se rescatan en el día.",
             "Renta fija: invierten en bonos y otros instrumentos de deuda; pueden subir y bajar algo más.",
             "Renta variable: invierten en acciones; más riesgo y pensados para plazos largos.",
             "Cada fondo informa su perfil de riesgo y el plazo en el que te devuelven la plata si rescatás."]},
         {"h": "Costos", "p": [
             "Los fondos cobran honorarios que ya vienen descontados del valor de la cuotaparte. Conviene mirarlos al comparar."]},
     ],
     "example": None},
    {"id": "bonos", "topic": "invertir", "title": "Bonos", "min": 3,
     "summary": "Prestarle plata a un gobierno o a una empresa a cambio de intereses.",
     "sections": [
         {"h": "Qué es un bono", "p": [
             "Es un préstamo que le hacés a quien lo emite (un gobierno o una empresa). A cambio te devuelve el capital y te paga intereses en fechas fijas.",
             "Cuando una empresa emite deuda así, se suele llamar obligación negociable (ON)."]},
         {"h": "Riesgos", "p": [
             "El principal es que quien emitió el bono no pueda pagar. Por eso los emisores más riesgosos suelen ofrecer más interés.",
             "Además, el precio de un bono cambia todos los días: si lo vendés antes del vencimiento, podés ganar o perder respecto de lo que pagaste."]},
         {"h": "Moneda y ajuste", "p": [
             "Hay bonos en pesos, en dólares y otros que ajustan por inflación. Cada uno responde distinto según lo que pase en la economía."]},
     ],
     "example": None},
    {"id": "acciones", "topic": "invertir", "title": "Acciones y CEDEARs", "min": 3,
     "summary": "Ser dueño de una parte chiquita de una empresa.",
     "sections": [
         {"h": "Acciones", "p": [
             "Una acción es una parte de una empresa. Si a la empresa le va bien, la acción puede subir y a veces paga dividendos; si le va mal, puede bajar.",
             "Son inversiones de más riesgo, con subas y bajas fuertes, pensadas para plazos largos."]},
         {"h": "CEDEARs", "p": [
             "Son certificados que se compran en pesos en la bolsa argentina y representan acciones de empresas del exterior.",
             "Su precio en pesos depende de la acción de afuera y también del tipo de cambio."]},
         {"h": "La regla básica", "p": [
             "Diversificar: no poner todo en una sola empresa. Y no invertir en acciones la plata que vas a necesitar pronto."]},
     ],
     "example": None},
    {"id": "cuenta-inversion", "topic": "invertir", "title": "Cómo abrir una cuenta para invertir", "min": 3,
     "summary": "Qué te piden, cuánto cuesta y cómo verificar que sea una entidad seria.",
     "sections": [
         {"h": "Dónde", "p": [
             "Para invertir en fondos, bonos o acciones necesitás una cuenta en un agente registrado en la CNV (ALyC). Muchos bancos y apps la abren online.",
             "Al abrirla, te dan una cuenta comitente: es donde quedan tus inversiones a tu nombre."]},
         {"h": "Qué te piden", "p": [
             "DNI, CUIL, una foto o video para validar identidad, datos de contacto y un cuestionario sobre tu perfil de inversor.",
             "Abrirla en general no cuesta nada y no te obliga a invertir."]},
         {"h": "Cómo verificar", "p": [
             "Antes de elegir, buscá la entidad en el registro de agentes del sitio de la CNV. Si no está, no es una opción.",
             "Nunca compartas tus claves ni le transfieras plata a una persona para que «invierta por vos»."]},
     ],
     "example": None},

    # ---------------------------------------------------------------- cuidarte
    {"id": "descuentos", "topic": "cuidarte", "title": "Cómo funcionan los descuentos y reintegros", "min": 3,
     "summary": "Topes, días, reintegros y la letra chica que conviene mirar.",
     "sections": [
         {"h": "Descuento o reintegro", "p": [
             "Un descuento se aplica en el momento de pagar. Un reintegro te devuelve la plata después: en el resumen de la tarjeta o en tu billetera, días o semanas más tarde.",
             "Si es reintegro, en el momento pagás el precio completo: tenelo en cuenta si estás justo de plata."]},
         {"h": "La letra chica", "p": [
             "Tope: el máximo que te devuelven por mes (o por compra). Pasado el tope, la promo ya no te suma.",
             "Días y medios: muchas promos valen solo ciertos días y pagando de una forma puntual (con QR, con débito, en una cuota).",
             "Compra mínima, adhesión previa o primera compra: algunas promos los piden."]},
         {"h": "Cómo te ayuda Tu Bolsillo", "p": [
             "En «Antes de pagar» calculamos cuánto ahorrás con cada medio teniendo en cuenta el tope que te queda este mes.",
             "Si una promo no te la aplicaron, avisanos: así la revisamos y evitamos que le pase a otras personas."]},
     ],
     "example": {"title": "Compra de $ 20.000 con 25% de reintegro y tope de $ 4.000", "rows": [
         ["25% de $ 20.000", "$ 5.000"], ["Te devuelven (por el tope)", "$ 4.000"], ["Ese mes, la promo ya no te suma más", "tope usado"]], "note": None}},
    {"id": "tarjeta", "topic": "cuidarte", "title": "Tarjeta de crédito: pago mínimo y cuotas", "min": 4,
     "summary": "Usarla a favor sin caer en intereses que se comen tu sueldo.",
     "sections": [
         {"h": "Pago total vs. pago mínimo", "p": [
             "Si pagás el total del resumen, no pagás intereses. Si pagás el mínimo, lo que queda se financia con intereses altos (más impuestos) que se suman al próximo resumen.",
             "Pagar el mínimo varios meses seguidos es una de las formas más rápidas de endeudarse."]},
         {"h": "Cuotas", "p": [
             "Las cuotas «sin interés» pueden convenir: pagás lo mismo, pero en partes, y la inflación hace que las últimas cuotas pesen menos.",
             "Las cuotas con interés son un préstamo: mirá el costo financiero total (CFT) antes de aceptarlas."]},
         {"h": "Reglas simples", "p": [
             "Anotá las cuotas que ya tenés comprometidas: es plata de los próximos meses que ya no está.",
             "Si un mes no llegás al total, priorizá no repetirlo y no sumar compras nuevas en cuotas."]},
     ],
     "example": None},
    {"id": "estafas", "topic": "cuidarte", "title": "Cómo no caer en estafas", "min": 3,
     "summary": "Las señales de alerta más comunes y qué hacer si te pasa.",
     "sections": [
         {"h": "Lo que nunca te van a pedir", "p": [
             "Ningún banco, billetera ni app seria te pide tu clave, el código que te llega por SMS o mail, ni los datos completos de tu tarjeta por teléfono, WhatsApp o redes.",
             "Tu Bolsillo nunca te pide claves bancarias."]},
         {"h": "Señales de alerta", "p": [
             "Promesas de ganancias altas y seguras. Urgencia («si no invertís hoy, perdés»). Pedidos de transferir plata para «liberar» un premio o un préstamo.",
             "Links que llegan por mensaje y piden ingresar datos: entrá siempre escribiendo vos la dirección o desde la app oficial."]},
         {"h": "Si te pasa", "p": [
             "Comunicate enseguida con tu banco o billetera por los canales oficiales para bloquear la cuenta o la tarjeta, cambiá tus claves y hacé la denuncia."]},
     ],
     "example": None},
]
ARTICLE_BY_ID = {a["id"]: a for a in ARTICLES}


def suggestions(saved_total, habits, has_goals, read):
    """Qué conceptos sugerir según lo que la persona ahorró y sus hábitos (sin bloquear nada)."""
    order = []
    if habits and habits.get("cash_share", 0) >= 0.25:
        order.append("inflacion")
    if habits and habits.get("missed_month", 0) > 0:
        order.append("descuentos")
    if not has_goals:
        order.append("fondo-emergencia")
    if saved_total >= 5000:
        order += ["remunerada", "plazofijo"]
    if saved_total >= 20000:
        order += ["money-market", "fci"]
    order += ["presupuesto", "inflacion", "tasa-real", "riesgo"]
    out = []
    for aid in order:
        if aid not in read and aid not in out:
            out.append(aid)
    return [ARTICLE_BY_ID[a] for a in out[:3]]
