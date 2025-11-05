from machine import PWM, Pin, SoftI2C
from time import sleep
from math import exp, log
from bh1750 import BH1750
import sys
import select

# --- Configuración del sensor BH1750 ---
i2c = SoftI2C(sda=Pin(20), scl=Pin(21), freq=200000)
bh1750 = BH1750(0x23, i2c)

# --- Configuración del PWM para el LED ---
led = PWM(Pin(15))
led.freq(50000)

# --- Parámetros del decaimiento radiactivo ---
pwm_max = 65025
A0 = 1.0
T12 = 6  # Vida media en segundos
lam = log(2) / T12

# --- Parámetros de simulación ---
pasos = 100
tiempo_total = 5 * T12  # Simular hasta 5 vidas medias
dt = tiempo_total / pasos  # Tiempo entre muestras

print("Esperando comando INICIAR...")

# --- Bucle principal: espera y adquisición ---
while True:
    try:
        if select.select([sys.stdin], [], [], 0.2)[0]:
            comando = sys.stdin.readline().strip()
            print("Comando recibido:", comando)
            if comando == "INICIAR":
                print("Comenzando simulación...")

                for i in range(pasos + 1):
                    t = i * dt
                    A_t = A0 * exp(-lam * t)
                    pwm_val = int(pwm_max * (1 - A_t))  # PWM inverso a A(t)
                    led.duty_u16(pwm_val)
                    sleep(0.01)  # Simulación rápida
                    lux = bh1750.measurement
                    print(f"<{t:.2f},{pwm_val},{lux:.2f}>")
                    sleep(0.01)

                print("Simulación finalizada. Esperando nuevo comando...")
        else:
            pass
    except Exception as e:
        print("Error de lectura:", e)
    sleep(0.1)