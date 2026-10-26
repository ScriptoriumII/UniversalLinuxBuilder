import inspect

from PySide6.QtCore import QThread, Signal

from .wsl import CANCELLED, Cancelled, Control


class Task(QThread):
    """Exécute une fonction hors du thread de l'interface.

    Si la fonction déclare un paramètre `control`, elle reçoit un
    objet Control : journal en direct, progression et annulation.
    """

    done = Signal(object, str)
    log = Signal(str)
    progress = Signal(object)

    def __init__(self, function, *arguments):
        super().__init__()
        self.function = function
        self.arguments = arguments
        self.control = Control(
            log=self.log.emit,
            progress=self.progress.emit
        )

    def wants_control(self):
        try:
            return "control" in inspect.signature(
                self.function
            ).parameters

        except (TypeError, ValueError):
            return False

    def cancel(self):
        self.control.cancel()

    def run(self):
        try:
            if self.wants_control():
                result = self.function(
                    *self.arguments,
                    control=self.control
                )

            else:
                result = self.function(*self.arguments)

            if self.control.cancelled:
                self.done.emit(None, CANCELLED)

            else:
                self.done.emit(result, "")

        except Cancelled:
            self.done.emit(None, CANCELLED)

        except Exception as exc:
            if self.control.cancelled:
                self.done.emit(None, CANCELLED)

            else:
                self.done.emit(None, str(exc))
