Tema 1
def
def root():

¿Qué significa?

def

viene de
define
o
define function

¿Qué hace?
Le dice a Python:
"Voy a crear una función."

Sintaxis
def nombre():

Ejemplo
def saludar():
    print("Hola")

¿Se ejecuta sola?

No.

Solo queda almacenada en memoria.
Hay que llamarla.

saludar() 

En FastAPI
No la llamamos nosotros.
La llama FastAPI.

Tema 2
return
return {
    "message":"Welcome"
}
¿Qué significa?

Devuelve un valor.
Ejemplo
def sumar():

    return 5+3

Cuando alguien haga:

resultado = sumar()

resultado valdrá:

8

En FastAPI
Todo lo que devuelve una función...
FastAPI lo convierte automáticamente en JSON.

Tema 3
Decoradores
@app.get("/")
¿Qué significa?

Le pone una etiqueta a la función.

Es como decir:

Esta función responde a GET /

¿Qué hace FastAPI?

Internamente guarda algo parecido a esto:

"/"

↓

root()

Cuando llega una petición...
Busca la ruta.
Encuentra la función.
La ejecuta.

Escalabilidad

Definición sencilla:

Diseñar un sistema para que pueda crecer sin tener que rehacerlo.

Un libro mayor o ledger es un registro cronológico de movimientos que aumentan o disminuyen un saldo.
En vez de reemplazar el saldo anterior, conserva todos los movimientos y calcula el resultado. Es mucho más seguro para información financiera.