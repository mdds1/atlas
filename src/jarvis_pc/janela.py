"""Janela de texto da Jarvis e atalho global de teclado (só Windows).

Não tem teste automático: abrir janela e registrar atalho dependem de uma área de
trabalho de verdade. A lógica que importa fica em outros módulos, testados.
Tudo que toca em widgets roda na thread da janela; o agente roda em outra thread
e conversa com a janela por filas.
"""
import queue
import threading
import tkinter as tk
from tkinter import messagebox

from jarvis_pc.agente import perguntar

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000


def registrar_atalho(tecla, ao_apertar):
    """Registra Ctrl+Alt+<tecla> num thread próprio. Devolve True se conseguiu."""
    import ctypes
    from ctypes import wintypes

    resultado = queue.Queue()

    def laco():
        user32 = ctypes.windll.user32
        ok = user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(tecla.upper()))
        resultado.put(bool(ok))
        if not ok:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                ao_apertar()

    threading.Thread(target=laco, daemon=True).start()
    return resultado.get(timeout=5)


class Janela:
    def __init__(self, agente, registro, ponte, tecla):
        self.agente = agente
        self.registro = registro
        self.ponte = ponte
        self._tecla = tecla
        self._eventos = queue.Queue()
        self._ocupado = False

        self.raiz = tk.Tk()
        self.raiz.title("Jarvis")
        self.raiz.geometry("720x520")
        self.raiz.attributes("-topmost", True)
        self.raiz.protocol("WM_DELETE_WINDOW", self.esconder)
        self.raiz.bind("<Escape>", lambda _e: self.esconder())

        self.saida = tk.Text(self.raiz, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.saida.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        linha = tk.Frame(self.raiz)
        linha.pack(fill="x", padx=8, pady=(0, 8))
        self.entrada = tk.Entry(linha, font=("Segoe UI", 11))
        self.entrada.pack(side="left", fill="x", expand=True)
        self.entrada.bind("<Return>", lambda _e: self.enviar())
        tk.Button(linha, text="Enviar", command=self.enviar).pack(side="left", padx=(6, 0))
        tk.Button(linha, text="Encerrar Jarvis", command=self.encerrar).pack(side="left", padx=(6, 0))

        self.raiz.withdraw()
        self.raiz.after(100, self._ciclo)

    # -- vida da janela ----------------------------------------------------
    def iniciar(self):
        if registrar_atalho(self._tecla, lambda: self._eventos.put(("mostrar", None))):
            self._escrever(f"Jarvis pronta. Ctrl+Alt+{self._tecla.upper()} abre esta janela.\n")
        else:
            self._escrever(
                f"Não consegui registrar Ctrl+Alt+{self._tecla.upper()} (outro programa usa). "
                "Troque a tecla no config.json.\n"
            )
            self.mostrar()
        self.raiz.mainloop()

    def mostrar(self):
        self.raiz.deiconify()
        self.raiz.lift()
        self.raiz.focus_force()
        self.entrada.focus_set()

    def esconder(self):
        self.raiz.withdraw()

    def encerrar(self):
        self.raiz.destroy()

    # -- conversa ------------------------------------------------------------
    def _escrever(self, texto):
        self.saida.configure(state="normal")
        self.saida.insert("end", texto)
        self.saida.see("end")
        self.saida.configure(state="disabled")

    def enviar(self):
        texto = self.entrada.get().strip()
        if not texto or self._ocupado:
            return
        self.entrada.delete(0, "end")
        self._ocupado = True
        self._escrever(f"\nVocê: {texto}\nJarvis: pensando...\n")
        threading.Thread(target=self._rodar, args=(texto,), daemon=True).start()

    def _rodar(self, texto):
        try:
            resposta = perguntar(self.agente, self.registro, texto)
            self._eventos.put(("resposta", resposta))
        except Exception as erro:
            self._eventos.put(("erro", f"{type(erro).__name__}: {erro}"))

    def _ciclo(self):
        pedido = self.ponte.proximo()
        if pedido is not None:
            self.mostrar()
            sim = messagebox.askyesno("A Jarvis pede permissão", pedido.texto, parent=self.raiz)
            pedido.responder(sim)
        try:
            while True:
                tipo, dado = self._eventos.get_nowait()
                if tipo == "mostrar":
                    self.mostrar()
                elif tipo == "resposta":
                    self._ocupado = False
                    self._escrever(f"Jarvis: {dado}\n")
                elif tipo == "erro":
                    self._ocupado = False
                    self._escrever(f"Jarvis: não consegui responder ({dado}). O Ollama está rodando?\n")
        except queue.Empty:
            pass
        self.raiz.after(100, self._ciclo)
