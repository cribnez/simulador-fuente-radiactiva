import sys
import serial
import threading
from math import log, exp
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QTableWidgetItem
from PyQt5 import uic
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

ISOTOPOS = {
    "Tc-99m": {"T12": 6.0, "unidad": "horas"},
    "I-131": {"T12": 8.0, "unidad": "días"},
    "Co-60": {"T12": 5.3, "unidad": "años"},
    "F-18": {"T12": 110.0, "unidad": "minutos"},
}

TIEMPO_SEGUNDOS = {
    "segundos": 1,
    "minutos": 60,
    "horas": 3600,
    "días": 86400,
    "años": 31536000,
}

ESCALAS_TIEMPO_SIMULADO = {
    "minutos": 60,
    "horas": 3600,
    "días": 86400,
    "años": 31536000
}

COLOR_ISOTOPOS = {
    "Tc-99m": "tab:blue",
    "I-131": "tab:orange",
    "Co-60": "tab:green",
    "F-18": "tab:red",
}

class MainWindow(QMainWindow):
    def _init_(self):
        super()._init_()
        uic.loadUi("simulador.ui", self)

        self.combo_isotopo.addItems(ISOTOPOS.keys())
        self.combo_unidad.setCurrentText("Bq")
        self.combo_isotopo.currentIndexChanged.connect(self.cambiar_isotopo)

        self.serial = None
        self.datos_t = []
        self.datos_lux = []
        self.datos_pwm = []
        self.datos_bq = []
        self.A0 = 1000
        self.lam = 0
        self.T12_segundos = 1
        self.escala_tiempo = 1
        self.simulacion_en_curso = False
        self.escala_lux = 0.386

        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(6, 6))
        self.canvas = FigureCanvas(self.fig)
        self.layout_graficas.addWidget(self.canvas)

        self.tabla_datos.setColumnCount(5)
        self.tabla_datos.setHorizontalHeaderLabels(["Tiempo (s)", "PWM", "Lux", "Bq", "Ci"])

        self.label_tiempo_relativo = QLabel("Tiempo relativo: 0 T₁/₂")
        self.layout_graficas.addWidget(self.label_tiempo_relativo)

        self.actualizar_info()
        self.iniciar_simulacion()

    def actualizar_info(self):
        isotopo = self.combo_isotopo.currentText()
        T12 = ISOTOPOS[isotopo]["T12"]
        unidad_tiempo = ISOTOPOS[isotopo]["unidad"]
        factor = TIEMPO_SEGUNDOS[unidad_tiempo]
        self.T12_segundos = T12 * factor
        self.lam = log(2) / self.T12_segundos
        self.escala_tiempo = ESCALAS_TIEMPO_SIMULADO[unidad_tiempo]
        self.label_info.setText(f"Isótopo: {isotopo} | Vida media: {T12} {unidad_tiempo} | λ real: {self.lam:.2e} s⁻¹")
        self.label_lambda_valor.setText(f"{self.lam:.2e}")

    def cambiar_isotopo(self):
        if self.simulacion_en_curso and self.serial and self.serial.is_open:
            self.simulacion_en_curso = False
            self.serial.close()
        self.actualizar_info()
        self.datos_t.clear()
        self.datos_lux.clear()
        self.datos_pwm.clear()
        self.datos_bq.clear()
        self.tabla_datos.setRowCount(0)
        self.ax1.clear()
        self.ax2.clear()
        self.canvas.draw()
        self.iniciar_simulacion()

    def iniciar_simulacion(self):
        try:
            self.serial = serial.Serial('COM3', 115200, timeout=1)
            self.serial.write(b"INICIAR\n")
            self.console.append("Conectado a COM3 y enviado INICIAR")
            self.simulacion_en_curso = True
            threading.Thread(target=self.leer_serial, daemon=True).start()
        except Exception as e:
            self.console.append(f"Error al iniciar serial: {e}")

    def leer_serial(self):
        while self.simulacion_en_curso:
            try:
                if self.serial.in_waiting:
                    linea = self.serial.readline().decode('utf-8').strip()
                    self.console.append(f"Linea: {linea}")

                    if linea == "<FIN>":
                        self.console.append("Simulación finalizada.")
                        self.simulacion_en_curso = False
                        self.serial.close()
                        return

                    if "<" in linea and ">" in linea:
                        try:
                            datos = linea[linea.find("<")+1 : linea.find(">")]
                            t_str, pwm_str, lux_str = datos.split(",")
                            t = float(t_str.strip())
                            pwm = int(pwm_str.strip())
                            lux = float(lux_str.strip())

                            self.datos_t.append(t)
                            self.datos_pwm.append(pwm)
                            self.datos_lux.append(lux)

                            A0_lux = lux * self.escala_lux
                            t_simulado = t * self.escala_tiempo
                            A_t = A0_lux * exp(-self.lam * t_simulado)
                            self.datos_bq.append(A_t)

                            porcentaje = 100 * (1 - A_t / A0_lux)
                            tiempo_relativo = t_simulado / self.T12_segundos

                            self.label_decay.setText(f"Decaimiento: {porcentaje:.1f}%")
                            self.label_tiempo_relativo.setText(f"Tiempo relativo: {tiempo_relativo:.2f} T₁/₂")
                            self.console.append(f"{t:.2f}s | PWM: {pwm} | Lux: {lux:.2f}")

                            self.actualizar_graficas()
                            self.actualizar_tabla(t, pwm, lux, A_t)
                        except ValueError as ve:
                            self.console.append(f"Error de conversión: {ve}")
            except Exception as e:
                self.console.append(f"Error al leer: {e}")

    def actualizar_graficas(self):
        self.ax1.clear()
        self.ax2.clear()
        isotopo = self.combo_isotopo.currentText()
        color_simulada = COLOR_ISOTOPOS.get(isotopo, "tab:blue")
        color_teorica = "tab:gray"

        if self.datos_lux:
            self.ax1.plot(self.datos_t, self.datos_lux, label="Lux", color="tab:purple", linestyle="-", marker="o", markersize=5)
            self.ax1.fill_between(self.datos_t, self.datos_lux, [0]*len(self.datos_lux), color="tab:purple", alpha=0.2)
            self.ax1.set_ylabel("Lux (medido)")
            self.ax1.set_xlabel("Tiempo (s)")
            self.ax1.grid(True, linestyle="--", alpha=0.5)
            self.ax1.legend(fontsize=9)

            t_simulados = [t * self.escala_tiempo for t in self.datos_t]
            t_relativos = [ts / self.T12_segundos for ts in t_simulados]
            A_simulada = self.datos_bq
            A0_teorica = A_simulada[0]
            A_teorica_ideal = [A0_teorica * exp(-self.lam * t) for t in t_simulados]

            self.ax2.plot(t_relativos, A_teorica_ideal, label="A(t) teórica", color=color_teorica, linestyle="--", linewidth=2)
            self.ax2.plot(t_relativos, A_simulada, label="A(t) simulada", color=color_simulada, marker="o", markersize=5, linewidth=2)
            self.ax2.fill_between(t_relativos, A_simulada, A_teorica_ideal, color=color_simulada, alpha=0.15)
            self.ax2.set_ylabel("Actividad (Bq)")
            self.ax2.set_xlabel("Tiempo (vidas medias)")
            self.ax2.grid(True, linestyle="--", alpha=0.5)
            self.ax2.legend(fontsize=9)
            self.ax2.set_title(f"Actividad - {isotopo}")

            self.ax2.set_xlim(0, max(t_relativos)*1.05)
            self.ax2.set_ylim(0, max(max(A_simulada), max(A_teorica_ideal))*1.1)

        self.fig.tight_layout()
        self.canvas.draw()

    def actualizar_tabla(self, t, pwm, lux, A_t):
        unidad = self.combo_unidad.currentText()
        bq_val = A_t
        ci_val = bq_val / 3.7e10

        row = self.tabla_datos.rowCount()
        self.tabla_datos.insertRow(row)
        self.tabla_datos.setItem(row, 0, QTableWidgetItem(f"{t:.2f}"))
        self.tabla_datos.setItem(row, 1, QTableWidgetItem(str(pwm)))
        self.tabla_datos.setItem(row, 2, QTableWidgetItem(f"{lux:.2f}"))
        self.tabla_datos.setItem(row, 3, QTableWidgetItem(f"{bq_val:.2f}"))
        self.tabla_datos.setItem(row, 4, QTableWidgetItem(f"{ci_val:.6e}"))
        self.tabla_datos.scrollToBottom()

if _name_ == '_main_':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())