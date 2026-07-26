"""Web-Terminal-Schicht: stellt die interaktive CLI über den Browser bereit.

Die eigentliche Coach-Logik bleibt unverändert. Dieses Paket startet die
bestehende Terminalanwendung pro Browser-Sitzung in einer Pseudo-TTY (PTY)
und verbindet sie über WebSocket mit einem xterm.js-Terminal im Browser.

Hinweis: Die PTY-Bridge nutzt ``pty``/``termios``/``fcntl`` und ist damit
Linux-/Unix-only. Das ist bewusst so, weil das Zielsystem ein Linux-VPS im
Docker-Container ist.
"""
